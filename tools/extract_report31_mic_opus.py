#!/usr/bin/env python3
"""Extract the DualSense microphone Opus uplink from a Zeroplus .cfax container.

Report 0x31 travels controller to PS5 on the HIDP DATA/INPUT channel (0xA1).
Report byte 1 splits into a sequence number in the high nibble and a type in
the low nibble. Type 1 is the ordinary controller state report. Type 2 carries
microphone audio as one Opus packet per report:

    offset 0      report id 0x31
    offset 1      audio sequence (high nibble) | type (low nibble)
    offset 2      Opus packet sequence, 8 bit, one step per 10 ms
    offset 3..73  Opus packet, 71 bytes, TOC 0xD4
    offset 74..77 Bluetooth CRC-32 over channel prefix 0xA1 and bytes 0..73

TOC 0xD4 is config 26: CELT-only, super-wideband, 10 ms, with the stereo bit
set. The encoded sample rate is 24 kHz; Opus decoders still run at 48 kHz
internally, so Ogg granule positions step by 480 per packet either way.

A container keeps every on-air transmission, so this tool drops frames that
fail the CRC, keeps one frame per packet sequence number, and emits them in
sequence order. See tools/extract_report36_from_cfax.py for the same treatment
of the downlink.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import zlib
from collections import Counter
from pathlib import Path


REPORT_SIZE = 78
L2CAP_PAYLOAD = REPORT_SIZE + 1      # HID channel byte 0xA1 + report
L2CAP_FRAME = L2CAP_PAYLOAD + 4      # + 2-byte length + 2-byte CID
HID_CHANNEL = 0xA1                   # HIDP DATA/INPUT, controller -> PS5
REPORT_ID = 0x31
TYPE_MIC = 2

CRC_SPAN = 74
SEQ_OFFSET = 2
PAYLOAD_OFFSET = 3
OPUS_SIZE = CRC_SPAN - PAYLOAD_OFFSET     # 71
OPUS_TOC = 0xD4
SILENCE_PACKET = bytes((OPUS_TOC, 0xFF, 0xFE)) + bytes(OPUS_SIZE - 3)

ENCODED_RATE = 24000       # from TOC config 26, super-wideband
DECODER_RATE = 48000       # Opus always runs its decoder here
SAMPLES_PER_PACKET = 480   # 10 ms at 48 kHz, the Ogg granule unit

DSP_HEADER_WORDS = 2       # OPUS_RX_HDR_WORDS on the DSP: 4-byte big-endian length

SEQ_BACKWARD_WINDOW = 32
SEQ_SEGMENT_GAP = 64
MIN_SEGMENT_SLOTS = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Zeroplus .cfax container")
    parser.add_argument("--output-dir", type=Path, help="output directory (default: sibling of raw/)")
    parser.add_argument("--basename", help="output basename (default: input stem)")
    parser.add_argument("--decode", action="store_true", help="also produce PCM and WAV with FFmpeg")
    parser.add_argument("--ffmpeg", type=Path, help="explicit FFmpeg executable")
    parser.add_argument(
        "--keep-crc-invalid",
        action="store_true",
        help="use a damaged frame when no valid copy of that sequence exists",
    )
    parser.add_argument(
        "--dsp-slot",
        type=int,
        action="append",
        metavar="PAYLOAD_BYTES",
        help="also write MCU/DSP slot framing sized for this payload, zero padded "
             "(repeatable; 71 gives a 76-byte slot, 200 gives 204)",
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


def ogg_crc(page: bytes) -> int:
    crc = 0
    for byte in page:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def ogg_page(packet: bytes, serial: int, sequence: int, granule: int, flags: int) -> bytes:
    segments = []
    remaining = len(packet)
    while remaining >= 255:
        segments.append(255)
        remaining -= 255
    segments.append(remaining)

    page = bytearray(b"OggS")
    page += bytes((0, flags))
    page += struct.pack("<QII", granule, serial, sequence)
    page += b"\x00\x00\x00\x00"
    page += bytes((len(segments),))
    page += bytes(segments)
    page += packet
    page[22:26] = struct.pack("<I", ogg_crc(bytes(page)))
    return bytes(page)


def write_zeroplus(path: Path, packets) -> None:
    with path.open("wb") as stream:
        for packet in packets:
            stream.write(struct.pack(">I", len(packet)))
            stream.write(packet)


def dsp_slot_bytes(payload_bytes: int, header_words: int = DSP_HEADER_WORDS) -> int:
    """Slot size the DSP reads per frame, rounded up to a 16-bit word boundary.

    Mirrors OPUS_RX_PKT_WORDS in the DSP's config.h:

        OPUS_RX_PKT_WORDS = OPUS_RX_HDR_WORDS + (OPUS_RX_PAYLOAD_BYTES + 1) / 2

    An odd payload rounds up, so 71 bytes occupy a 76-byte slot, not 75. Feeding
    the tightly packed .opus_raw to a decoder configured for 71 desynchronises
    after the first frame.
    """
    return 2 * (header_words + (payload_bytes + 1) // 2)


def write_dsp_slot(path: Path, packets, payload_bytes: int) -> int:
    """MCU/DSP slot framing: 4-byte big-endian length, payload, zero pad.

    The DSP reads a fixed-size slot per frame and takes the real length from
    the header, so a payload shorter than the slot is padded with zeros.
    """
    slot = dsp_slot_bytes(payload_bytes)
    with path.open("wb") as stream:
        for packet in packets:
            if len(packet) > payload_bytes:
                raise SystemExit(
                    "packet of %d bytes does not fit --dsp-slot %d" % (len(packet), payload_bytes)
                )
            stream.write(struct.pack(">I", len(packet)))
            stream.write(packet)
            stream.write(bytes(slot - 4 - len(packet)))
    return slot


def write_ogg(path: Path, packets) -> None:
    serial = 0x50353141
    vendor = b"DualSense Report 0x31 type 2 microphone extraction"
    opus_head = (
        b"OpusHead"
        + bytes((1, 2))
        + struct.pack("<H", 0)
        + struct.pack("<I", ENCODED_RATE)
        + struct.pack("<hB", 0, 0)
    )
    opus_tags = b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)

    with path.open("wb") as stream:
        stream.write(ogg_page(opus_head, serial, 0, 0, 0x02))
        stream.write(ogg_page(opus_tags, serial, 1, 0, 0x00))
        granule = 0
        for index, packet in enumerate(packets):
            granule += SAMPLES_PER_PACKET
            flags = 0x04 if index == len(packets) - 1 else 0
            stream.write(ogg_page(packet, serial, index + 2, granule, flags))


def scan(container: bytes):
    """Every Report 0x31 type 2 frame in capture order, with no deduplication."""
    frames = []
    stats = Counter()
    types = Counter()
    tocs = Counter()
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

        stats["report31_frames"] += 1
        types[report[1] & 0x0F] += 1
        if (report[1] & 0x0F) != TYPE_MIC:
            continue

        stats["mic_frames"] += 1
        cids[int.from_bytes(container[offset - 2 : offset], "little")] += 1
        expected = (zlib.crc32(bytes((HID_CHANNEL,)) + report[:CRC_SPAN]) & 0xFFFFFFFF).to_bytes(4, "little")
        crc_ok = report[CRC_SPAN : CRC_SPAN + 4] == expected
        stats["crc_valid" if crc_ok else "crc_invalid"] += 1

        packet = report[PAYLOAD_OFFSET : PAYLOAD_OFFSET + OPUS_SIZE]
        tocs[packet[0]] += 1
        if packet[0] != OPUS_TOC:
            stats["bad_opus_toc"] += 1
            continue

        frames.append(
            {
                "offset": offset,
                "sequence": report[SEQ_OFFSET],
                "crc_ok": crc_ok,
                "packet": packet,
            }
        )

    summary = {
        "report31_frames": stats["report31_frames"],
        "report31_types": dict((str(k), v) for k, v in types.most_common()),
        "mic_frames": stats["mic_frames"],
        "crc_valid": stats["crc_valid"],
        "crc_invalid": stats["crc_invalid"],
        "bad_opus_toc": stats["bad_opus_toc"],
        "truncated": stats["truncated"],
        "usable_frames": len(frames),
        "opus_toc": dict((hex(k), v) for k, v in tocs.most_common()),
        "l2cap_cids": dict((hex(k), v) for k, v in cids.most_common()),
    }
    return frames, summary


def order_by_sequence(frames):
    """Continuous runs, each deduplicated by sequence and ordered by sequence."""
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
                    "sequence_slots": len(keys),
                    "retransmissions": retransmissions,
                    "lost_slots": len(lost),
                    "loss_percent": round(100 * len(lost) / (len(keys) + len(lost)), 3),
                    "first_offset": slots[keys[0]]["offset"],
                    "last_offset": slots[keys[-1]]["offset"],
                },
            }
        )

    for frame in frames:
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


def find_ffmpeg(explicit):
    if explicit:
        if not explicit.is_file():
            raise FileNotFoundError("FFmpeg not found: %s" % explicit)
        return str(explicit)
    local_dir = Path(__file__).resolve().parent / ".vendor" / "ffmpeg"
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = local_dir / name
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError(
            "FFmpeg was not found. Run tools/setup_ffmpeg.ps1, add FFmpeg to PATH, "
            "or pass --ffmpeg C:\\path\\to\\ffmpeg.exe"
        )
    return found


def decode(ffmpeg: str, ogg_path: Path, output_dir: Path, basename: str):
    outputs = {}
    for rate, tag in ((ENCODED_RATE, "24k"), (DECODER_RATE, "48k")):
        pcm = output_dir / ("%s_s16le_stereo_%s.pcm" % (basename, tag))
        wav = output_dir / ("%s_%s.wav" % (basename, tag))
        common = [ffmpeg, "-y", "-v", "warning", "-i", str(ogg_path), "-ar", str(rate), "-ac", "2"]
        subprocess.run(common + ["-f", "s16le", "-acodec", "pcm_s16le", str(pcm)], check=True)
        subprocess.run(common + ["-acodec", "pcm_s16le", str(wav)], check=True)
        outputs["pcm_%s" % tag] = str(pcm)
        outputs["wav_%s" % tag] = str(wav)
    return outputs


def main() -> None:
    args = parse_args()
    source = args.input.resolve()
    output_dir = (args.output_dir or default_output_dir(source)).resolve()
    basename = args.basename or source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    frames, summary = scan(source.read_bytes())
    if not frames:
        raise SystemExit("no Report 0x31 type %d frames found in %s" % (TYPE_MIC, source))

    usable = frames if args.keep_crc_invalid else [f for f in frames if f["crc_ok"]]
    if not usable:
        raise SystemExit("every microphone frame failed the Bluetooth CRC-32 check")

    selected = []
    segment_reports = []
    dropped = []
    for segment in order_by_sequence(usable):
        if segment["report"]["sequence_slots"] < args.min_segment:
            dropped.append(segment["report"])
            continue
        selected.extend(segment["frames"])
        segment_reports.append(segment["report"])
    if not selected:
        raise SystemExit("no run reached --min-segment %d packets" % args.min_segment)

    packets = [f["packet"] for f in selected]
    raw_path = output_dir / ("%s_zeroplus.opus_raw" % basename)
    ogg_path = output_dir / ("%s.ogg.opus" % basename)
    write_zeroplus(raw_path, packets)
    write_ogg(ogg_path, packets)

    outputs = {"opus_raw": str(raw_path), "ogg_opus": str(ogg_path)}
    for payload_bytes in args.dsp_slot or []:
        slot = dsp_slot_bytes(payload_bytes)
        slot_path = output_dir / ("%s_dspslot%d.opus_raw" % (basename, slot))
        write_dsp_slot(slot_path, packets, payload_bytes)
        outputs["dsp_slot_%d" % slot] = str(slot_path)
    if args.decode:
        outputs.update(decode(find_ffmpeg(args.ffmpeg), ogg_path, output_dir, basename))

    summary.update(
        {
            "source": str(source),
            "crc_invalid_dropped": 0 if args.keep_crc_invalid else summary["crc_invalid"],
            "segments": segment_reports,
            "detached_bursts_dropped": dropped,
            "packets": len(packets),
            "packet_bytes": OPUS_SIZE,
            "silence_packets": sum(1 for p in packets if p == SILENCE_PACKET),
            "lost_slots": sum(s["lost_slots"] for s in segment_reports),
            "encoded_sample_rate_hz": ENCODED_RATE,
            "decoder_sample_rate_hz": DECODER_RATE,
            "channels": 2,
            "frame_duration_ms": 10,
            "duration_seconds": len(packets) / 100,
            "outputs": outputs,
        }
    )
    summary_path = output_dir / ("%s_validation.json" % basename)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
