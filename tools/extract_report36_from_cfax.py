#!/usr/bin/env python3
"""Recover Report 0x36 frames from a Zeroplus .cfax container.

The analyzer's CSV export is the normal input for
``tools/extract_report36_opus.py``. When only the container is available this
tool rebuilds an equivalent CSV directly from it.

The container keeps every on-air transmission, including Bluetooth
retransmissions and frames damaged in flight, so a plain byte scan is not a
stream. This tool therefore drops CRC-invalid frames, keeps one frame per
audio sequence number, and emits them in sequence order.
"""

from __future__ import annotations

import argparse
import csv
import json
import zlib
from collections import Counter
from pathlib import Path


REPORT_SIZE = 398
L2CAP_PAYLOAD = REPORT_SIZE + 1      # HID channel byte 0xA2 + report
L2CAP_FRAME = L2CAP_PAYLOAD + 4      # + 2-byte length + 2-byte CID
HID_CHANNEL = 0xA2                   # HIDP DATA/OUTPUT, host -> controller
REPORT_ID = 0x36
OPUS_SIZE = 200
SILENCE_PACKET = b"\xF4\xFF\xFE" + bytes(197)

# Marker at report offsets 67..71. Offset 70 is a per-session value (0x39 in
# captures 01 and 02, 0x46 in capture-mic-01, 0x00 in capture-mic-02) and is
# not part of the variant.
VARIANT_BY_MARKER = {(0x05, 0x6F): ("A", 73, 76), (0x06, 0x7F): ("B", 74, 77)}

SEQ_BACKWARD_WINDOW = 32   # a delta above this counts as a late retransmission
SEQ_SEGMENT_GAP = 64       # a forward jump above this is a capture break, not loss
MIN_SEGMENT_SLOTS = 100    # shorter runs are detached bursts, not part of the stream


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Zeroplus .cfax container")
    parser.add_argument("--output-dir", type=Path, help="output directory (default: sibling of raw/)")
    parser.add_argument("--basename", help="output basename (default: input stem)")
    parser.add_argument(
        "--keep-crc-invalid",
        action="store_true",
        help="use a damaged frame when no valid copy of that sequence exists",
    )
    parser.add_argument(
        "--min-segment",
        type=int,
        default=MIN_SEGMENT_SLOTS,
        help="drop continuous runs shorter than this many packets (default: %d)" % MIN_SEGMENT_SLOTS,
    )
    return parser.parse_args()


def default_output_dir(source: Path) -> Path:
    if source.parent.name.lower() == "raw":
        return source.parent.parent / "results"
    return source.parent / "results"


def classify(report: bytes):
    """Return (variant, sequence offset, payload offset) or None."""
    if report[67] != 0x91 or report[71] != 0x1F:
        return None
    return VARIANT_BY_MARKER.get((report[68], report[69]))


def scan(container: bytes):
    """Every Report 0x36 frame in capture order, with no deduplication."""
    frames = []
    stats = Counter()
    session_bytes = Counter()
    cids = Counter()

    needle = bytes((HID_CHANNEL, REPORT_ID))
    index = container.find(needle)
    while index >= 0:
        offset = index
        index = container.find(needle, index + 1)
        if offset < 6:
            continue
        if int.from_bytes(container[offset - 6 : offset - 4], "little") != L2CAP_FRAME:
            continue
        if int.from_bytes(container[offset - 4 : offset - 2], "little") != L2CAP_PAYLOAD:
            continue

        report = container[offset + 1 : offset + 1 + REPORT_SIZE]
        if len(report) != REPORT_SIZE:
            stats["truncated"] += 1
            continue

        stats["frames"] += 1
        cids[int.from_bytes(container[offset - 2 : offset], "little")] += 1
        expected = (zlib.crc32(b"\xA2" + report[:394]) & 0xFFFFFFFF).to_bytes(4, "little")
        crc_ok = report[394:398] == expected
        stats["crc_valid" if crc_ok else "crc_invalid"] += 1

        info = classify(report)
        if info is None:
            stats["unknown_marker"] += 1
            continue
        variant, sequence_offset, payload_offset = info
        session_bytes[report[70]] += 1

        if report[payload_offset - 1] != OPUS_SIZE:
            stats["bad_length_byte"] += 1
            continue
        packet = report[payload_offset : payload_offset + OPUS_SIZE]
        if len(packet) != OPUS_SIZE or packet[0] != 0xF4:
            stats["bad_opus_toc"] += 1
            continue

        frames.append(
            {
                "offset": offset,
                "variant": variant,
                "sequence": report[sequence_offset],
                "crc_ok": crc_ok,
                "report": report,
                "packet": packet,
            }
        )

    summary = {
        "scanned_frames": stats["frames"],
        "crc_valid": stats["crc_valid"],
        "crc_invalid": stats["crc_invalid"],
        "unknown_marker": stats["unknown_marker"],
        "bad_length_byte": stats["bad_length_byte"],
        "bad_opus_toc": stats["bad_opus_toc"],
        "truncated": stats["truncated"],
        "usable_frames": len(frames),
        "l2cap_cids": dict((hex(k), v) for k, v in cids.most_common()),
        "session_marker_byte": dict((hex(k), v) for k, v in session_bytes.most_common()),
    }
    return frames, summary


def split_phases(frames):
    """Split on variant changeover, ignoring isolated single-frame flips."""
    if not frames:
        return []
    phases = [[frames[0]]]
    for index, frame in enumerate(frames[1:], start=1):
        previous = phases[-1][-1]
        if frame["variant"] == previous["variant"]:
            phases[-1].append(frame)
            continue
        # A run of one frame that flips straight back is a stray, not a phase.
        following = frames[index + 1 : index + 3]
        if following and all(f["variant"] == previous["variant"] for f in following):
            phases[-1].append(frame)
            continue
        phases.append([frame])
    return phases


def order_by_sequence(phase):
    """Split a phase into continuous runs, then order each run by sequence.

    A frame repeating a sequence number is a Bluetooth retransmission; the
    CRC-valid copy wins. A forward jump wider than SEQ_SEGMENT_GAP is a break
    in the capture rather than packet loss, so it starts a new run.
    """
    segments = []
    slots = {}
    unwrapped = None
    retransmissions = 0

    def close():
        if not slots:
            return
        keys = sorted(slots)
        lost = [k for k in range(keys[0], keys[-1] + 1) if k not in slots]
        segments.append(
            {
                "frames": [slots[k] for k in keys],
                "report": {
                    "variant": phase[0]["variant"],
                    "sequence_slots": len(keys),
                    "retransmissions": retransmissions,
                    "lost_slots": len(lost),
                    "loss_percent": round(100 * len(lost) / (len(keys) + len(lost)), 3),
                    "first_offset": slots[keys[0]]["offset"],
                    "last_offset": slots[keys[-1]]["offset"],
                },
            }
        )

    for frame in phase:
        sequence = frame["sequence"]
        if unwrapped is None:
            unwrapped = sequence
        else:
            delta = (sequence - (unwrapped % 256)) % 256
            if delta > 256 - SEQ_BACKWARD_WINDOW:
                unwrapped = unwrapped - (256 - delta)
            elif delta > SEQ_SEGMENT_GAP:
                close()
                slots = {}
                retransmissions = 0
                unwrapped = sequence
            else:
                unwrapped = unwrapped + delta
        existing = slots.get(unwrapped)
        if existing is None:
            slots[unwrapped] = frame
        else:
            retransmissions += 1
            if frame["crc_ok"] and not existing["crc_ok"]:
                slots[unwrapped] = frame
        unwrapped = max(slots)

    close()
    return segments


def main() -> None:
    args = parse_args()
    source = args.input.resolve()
    output_dir = (args.output_dir or default_output_dir(source)).resolve()
    basename = args.basename or source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    frames, summary = scan(source.read_bytes())
    if not frames:
        raise SystemExit("no Report 0x36 frames found in %s" % source)

    usable = frames if args.keep_crc_invalid else [f for f in frames if f["crc_ok"]]
    if not usable:
        raise SystemExit("every Report 0x36 frame failed the Bluetooth CRC-32 check")

    selected = []
    segment_reports = []
    dropped = []
    for phase in split_phases(usable):
        for segment in order_by_sequence(phase):
            if segment["report"]["sequence_slots"] < args.min_segment:
                dropped.append(segment["report"])
                continue
            selected.extend(segment["frames"])
            segment_reports.append(segment["report"])
    if not selected:
        raise SystemExit("no run reached --min-segment %d packets" % args.min_segment)

    csv_path = output_dir / ("%s_report36.csv" % basename)
    with csv_path.open("w", newline="", encoding="ascii") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Bookmark", "Frame#", "Hex", "ASCII", "Frame Size", "Delta", "Timestamp"])
        for number, frame in enumerate(selected, start=1):
            hex_text = "0x " + " ".join("%02x" % b for b in frame["report"])
            writer.writerow(['=""', number, hex_text, "", REPORT_SIZE, '=""', '="offset %d"' % frame["offset"]])

    summary.update(
        {
            "source": str(source),
            "crc_invalid_dropped": 0 if args.keep_crc_invalid else summary["crc_invalid"],
            "segments": segment_reports,
            "detached_bursts_dropped": dropped,
            "emitted_packets": len(selected),
            "variants": dict(Counter(f["variant"] for f in selected)),
            "silence_packets": sum(1 for f in selected if f["packet"] == SILENCE_PACKET),
            "duration_seconds": len(selected) / 100,
            "outputs": {"csv": str(csv_path)},
        }
    )
    scan_path = output_dir / ("%s_cfax_scan.json" % basename)
    scan_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
