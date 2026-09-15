#!/usr/bin/env python3
"""Extract fixed 200-byte Opus packets from DualSense Report 0x36 CSV data."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import struct
import subprocess
import zlib
from pathlib import Path


REPORT_SIZE = 398
OPUS_SIZE = 200
SAMPLES_PER_PACKET = 480  # 10 ms at 48 kHz.
SILENCE_PACKET = b"\xF4\xFF\xFE" + bytes(197)
# Marker at report offsets 67..71. Offset 70 carries a per-session value
# (0x39 in captures 01 and 02, 0x46 in capture-mic-01, 0x00 in capture-mic-02)
# and does not select the variant, so it is matched as a wildcard.
VARIANTS = {
    (0x91, 0x05, 0x6F, 0x1F): ("A", 73, 76),
    (0x91, 0x06, 0x7F, 0x1F): ("B", 74, 77),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV export containing a Hex column")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (default: sibling results directory for a raw input)",
    )
    parser.add_argument("--basename", help="output basename (default: input stem)")
    parser.add_argument("--skip-crc", action="store_true", help="do not validate Bluetooth CRC-32")
    parser.add_argument("--decode", action="store_true", help="also produce PCM and WAV with FFmpeg")
    parser.add_argument("--ffmpeg", type=Path, help="explicit FFmpeg executable")
    return parser.parse_args()


def default_output_dir(source: Path) -> Path:
    return source.parent.parent / "results" if source.parent.name.lower() == "raw" else source.parent / "results"


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
    page[22:26] = struct.pack("<I", ogg_crc(page))
    return bytes(page)


def parse_report(value: str) -> bytes | None:
    value = value.strip()
    if value.lower().startswith("0x"):
        value = value[2:]
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


def validate_crc(report: bytes) -> bool:
    expected = zlib.crc32(b"\xA2" + report[:394]) & 0xFFFFFFFF
    return report[394:398] == expected.to_bytes(4, "little")


def read_packets(source: Path, check_crc: bool) -> tuple[list[bytes], dict[str, object]]:
    packets: list[bytes] = []
    variants = {"A": 0, "B": 0}
    silence = 0
    crc_valid = 0
    first_frame = None
    last_frame = None

    with source.open(newline="", encoding="utf-8-sig", errors="replace") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "Hex" not in reader.fieldnames:
            raise ValueError("CSV does not contain a Hex column")

        for row in reader:
            report = parse_report(row.get("Hex", ""))
            if report is None or len(report) != REPORT_SIZE or report[0] != 0x36:
                continue

            frame = row.get("Frame#") or "unknown"
            crc_ok = validate_crc(report)
            if check_crc and not crc_ok:
                raise ValueError(f"CRC mismatch at frame {frame}")
            crc_valid += int(crc_ok)

            variant_info = VARIANTS.get((report[67], report[68], report[69], report[71]))
            if variant_info is None:
                raise ValueError(f"unknown Report 0x36 audio variant at frame {frame}")
            variant, sequence_offset, payload_offset = variant_info

            if report[payload_offset - 1] != OPUS_SIZE:
                raise ValueError(f"unexpected Opus length at frame {frame}")
            packet = report[payload_offset : payload_offset + OPUS_SIZE]
            if len(packet) != OPUS_SIZE or packet[0] != 0xF4:
                raise ValueError(f"unexpected Opus packet at frame {frame}")

            packets.append(packet)
            variants[variant] += 1
            silence += int(packet == SILENCE_PACKET)
            first_frame = first_frame or frame
            last_frame = frame

            # Accessing this byte is intentional: it verifies the offset exists.
            _audio_sequence = report[sequence_offset]

    if not packets:
        raise ValueError("no valid 398-byte Report 0x36 records found")

    summary: dict[str, object] = {
        "source": str(source.resolve()),
        "packets": len(packets),
        "packet_bytes": OPUS_SIZE,
        "variants": variants,
        "silence_packets": silence,
        "crc_valid": crc_valid,
        "crc_checked": check_crc,
        "first_frame": first_frame,
        "last_frame": last_frame,
        "sample_rate_hz": 48000,
        "channels": 2,
        "frame_duration_ms": 10,
        "duration_seconds": len(packets) / 100,
    }
    return packets, summary


def write_zeroplus(path: Path, packets: list[bytes]) -> None:
    prefix = struct.pack(">I", OPUS_SIZE)
    with path.open("wb") as stream:
        for packet in packets:
            stream.write(prefix)
            stream.write(packet)


def write_ogg(path: Path, packets: list[bytes]) -> None:
    serial = 0x50353641
    vendor = b"DualSense Report 0x36 extraction"
    opus_head = b"OpusHead" + bytes((1, 2)) + struct.pack("<H", 0) + struct.pack("<I", 48000) + struct.pack("<hB", 0, 0)
    opus_tags = b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)

    with path.open("wb") as stream:
        stream.write(ogg_page(opus_head, serial, 0, 0, 0x02))
        stream.write(ogg_page(opus_tags, serial, 1, 0, 0x00))
        granule = 0
        for index, packet in enumerate(packets):
            granule += SAMPLES_PER_PACKET
            flags = 0x04 if index == len(packets) - 1 else 0
            stream.write(ogg_page(packet, serial, index + 2, granule, flags))


def find_ffmpeg(explicit: Path | None) -> str:
    if explicit:
        if not explicit.is_file():
            raise FileNotFoundError(f"FFmpeg not found: {explicit}")
        return str(explicit)

    local_dir = Path(__file__).resolve().parent / ".vendor" / "ffmpeg"
    local_names = ("ffmpeg.exe", "ffmpeg")
    for name in local_names:
        local_ffmpeg = local_dir / name
        if local_ffmpeg.is_file():
            return str(local_ffmpeg)

    found = shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError(
            "FFmpeg was not found. Run tools/setup_ffmpeg.ps1, add FFmpeg to PATH, "
            "or pass --ffmpeg C:\\path\\to\\ffmpeg.exe"
        )
    return found


def decode(ffmpeg: str, ogg_path: Path, pcm_path: Path, wav_path: Path) -> None:
    common = [ffmpeg, "-y", "-v", "warning", "-i", str(ogg_path), "-ar", "48000", "-ac", "2"]
    subprocess.run(common + ["-f", "s16le", "-acodec", "pcm_s16le", str(pcm_path)], check=True)
    subprocess.run(common + ["-acodec", "pcm_s16le", str(wav_path)], check=True)


def main() -> None:
    args = parse_args()
    source = args.input.resolve()
    output_dir = (args.output_dir or default_output_dir(source)).resolve()
    basename = args.basename or source.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / f"{basename}_corrected_zeroplus.opus_raw"
    ogg_path = output_dir / f"{basename}_corrected.ogg.opus"
    summary_path = output_dir / f"{basename}_validation.json"

    packets, summary = read_packets(source, check_crc=not args.skip_crc)
    write_zeroplus(raw_path, packets)
    write_ogg(ogg_path, packets)

    outputs = {"opus_raw": str(raw_path), "ogg_opus": str(ogg_path)}
    if args.decode:
        pcm_path = output_dir / f"{basename}_corrected_s16le_stereo.pcm"
        wav_path = output_dir / f"{basename}_corrected.wav"
        decode(find_ffmpeg(args.ffmpeg), ogg_path, pcm_path, wav_path)
        outputs.update({"pcm": str(pcm_path), "wav": str(wav_path)})

    summary["outputs"] = outputs
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
