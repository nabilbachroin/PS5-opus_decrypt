# PS5 DualSense Opus Capture Analysis

This repository keeps raw PS5/DualSense captures, reproducible extraction tools,
and derived Opus audio grouped by capture. Raw inputs must not be edited in
place.

## Current status

- Capture 01 contains 7,191 valid 398-byte DualSense Report `0x36` records.
- Every extracted Opus packet is exactly 200 bytes and starts with TOC byte
  `0xF4` (CELT-only, fullband, stereo, 10 ms).
- The corrected stream decodes as 48 kHz stereo audio for 71.91 seconds.
- The silence packet is `F4 FF FE` followed by 197 zero bytes and matches the
  Zeroplus reference byte-for-byte.
- Vanessa confirmed the capture-01 interpretation and result on 2026-09-08.
- Capture 02 has been received as two `.cfax` files and has not yet been
  extracted or validated.

The earlier 199/263-byte interpretation is retained only under
`archive/invalid-extraction-v1/`. It must not be used as decoder input.

## Layout

```text
data/
  capture-01/
    raw/                 Original CSV capture
    results/             Corrected Opus and decoded audio
  capture-02/
    raw/                 Vanessa's second capture
    results/             Reserved for validated results
reference/zeroplus/      Known Zeroplus Opus reference
tools/                   Reproducible extraction tools
docs/                    Protocol notes and validation evidence
archive/                 Superseded local outputs, excluded from Git
```

## Reproduce capture 01

Python 3 is sufficient to build the `.opus_raw` and `.ogg.opus` files. FFmpeg
is required only for PCM/WAV decoding.

```powershell
python tools/extract_report36_opus.py data/capture-01/raw/opus_1.csv --decode
```

The default output directory is the capture's sibling `results` directory.
Use `--ffmpeg C:\path\to\ffmpeg.exe` if FFmpeg is not on `PATH`.

## File conventions

- `.opus_raw`: Zeroplus-compatible framing, repeated as a 4-byte big-endian
  payload length (`00 00 00 C8`) followed by one 200-byte Opus packet.
- `.ogg.opus`: the same Opus packets wrapped in the standard Ogg Opus
  container.
- `.pcm`: signed 16-bit little-endian, stereo, 48 kHz PCM.
- `.wav`: the same decoded PCM with a WAV header.

Large binary artifacts are configured for Git LFS. This repository is local
until a remote and publication policy are explicitly chosen.
