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
- Capture 02 is confirmed as of 2026-09-09: 4,861 packets from
  `TEST_PM16_26_35.cfax` via `opus_2.csv`, all CRC valid, decoding as 48 kHz
  stereo for 48.61 seconds without FFmpeg warnings, with a passing listening
  review.
- The two audio variants are successive phases of one session, not concurrent
  streams. Variant B is the idle phase and is 91.7 % silence; variant A carries
  the audio. Capture 02 contains variant A only because it began after the
  changeover.
- Recorded durations are packet counts. Lost packets are concatenated without a
  marker, so elapsed time is 72.22 s for capture 01 and 48.81 s for capture 02.
- `TEST_PM1620.cfax`, delivered with the capture-02 material, extracts to a
  stream byte-for-byte identical to capture 01. It is the same session in a
  different container, so it now lives under `data/capture-01/raw/`.
- Capture 01's `.ogg.opus` was built by an earlier version of the extractor and
  cannot be reproduced by the current tool; its OpusTags vendor string differs.

The earlier 199/263-byte interpretation is retained only under
`archive/invalid-extraction-v1/`. It must not be used as decoder input.

## Layout

```text
data/
  capture-01/
    raw/                 Original CSV capture and its analyzer container
    results/             Corrected Opus and decoded audio
  capture-02/
    raw/                 Vanessa's second capture and its CSV export
    results/             Reserved for validated results
reference/zeroplus/      Known Zeroplus Opus reference
tools/                   Extraction and dependency setup tools
docs/                    Protocol notes and validation evidence
archive/                 Superseded local outputs, excluded from Git
```

## Requirements

- Windows 64-bit.
- PowerShell 5.1 or newer.
- Python 3.8 or newer available as `python`.
- Git LFS when cloning the capture and audio files from GitHub.
- Internet access during the one-time FFmpeg setup.

FFmpeg is needed only to create `.pcm` and `.wav`. Extraction to `.opus_raw`
and `.ogg.opus` uses only Python.

## First-time setup

### 1. Clone the repository and retrieve Git LFS files

```powershell
git clone https://github.com/nabilbachroin/PS5-opus_decrypt.git
cd PS5-opus_decrypt
git lfs install
git lfs pull
```

If this repository is already cloned, start PowerShell in the repository root
and skip to step 2.

### 2. Check Python

```powershell
python --version
```

The command must print Python 3.8 or newer. If `python` is not recognized,
install Python and reopen PowerShell.

### 3. Install the repository-local FFmpeg

```powershell
.\tools\setup_ffmpeg.ps1
```

The setup script downloads the pinned Windows x64 wheel for
`imageio-ffmpeg 0.5.1`, verifies its SHA-256, and extracts only `ffmpeg.exe` to:

```text
tools/.vendor/ffmpeg/ffmpeg.exe
```

This local dependency is ignored by Git and must not be committed. Re-running
the setup is safe. Use `-Force` only when the local copy must be replaced:

```powershell
.\tools\setup_ffmpeg.ps1 -Force
```

If PowerShell blocks local scripts, run this once for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\setup_ffmpeg.ps1
```

### 4. Verify FFmpeg

```powershell
& .\tools\.vendor\ffmpeg\ffmpeg.exe -version
```

The command should print the FFmpeg version and exit without an error.

## Reproduce capture 01

### Extract Opus without decoding

```powershell
python .\tools\extract_report36_opus.py `
  .\data\capture-01\raw\opus_1.csv
```

This creates `.opus_raw`, `.ogg.opus`, and a validation JSON file. FFmpeg is not
used by this command.

### Extract and decode to PCM/WAV

```powershell
python .\tools\extract_report36_opus.py `
  .\data\capture-01\raw\opus_1.csv `
  --decode
```

With `--decode`, the tool automatically checks for FFmpeg in this order:

1. The path supplied through `--ffmpeg`.
2. `tools/.vendor/ffmpeg/ffmpeg.exe` installed by the setup script.
3. `ffmpeg` available on the system `PATH`.

The default output directory is `data/capture-01/results/`. Existing files with
the same names are replaced.

Expected validation summary for capture 01:

```text
packets:            7191
packet_bytes:       200
variants:           A=4757, B=2434
silence_packets:    2235
crc_valid:          7191
sample_rate_hz:     48000
channels:           2
duration_seconds:   71.91
```

### Use a different FFmpeg executable

```powershell
python .\tools\extract_report36_opus.py `
  .\data\capture-01\raw\opus_1.csv `
  --decode `
  --ffmpeg C:\path\to\ffmpeg.exe
```

### Use a different output directory

```powershell
python .\tools\extract_report36_opus.py `
  .\data\capture-01\raw\opus_1.csv `
  --output-dir .\work\capture-01 `
  --decode
```

## Generated files

- `*_corrected_zeroplus.opus_raw`: Zeroplus-compatible framing, repeated as a
  4-byte big-endian payload length (`00 00 00 C8`) followed by one 200-byte
  Opus packet.
- `*_corrected.ogg.opus`: the same Opus packets wrapped in the standard Ogg
  Opus container.
- `*_corrected_s16le_stereo.pcm`: signed 16-bit little-endian, stereo, 48 kHz
  PCM without a container header.
- `*_corrected.wav`: the decoded PCM with a WAV header.
- `*_validation.json`: packet counts, CRC result, codec parameters, duration,
  and output paths.

## Troubleshooting

### `FFmpeg was not found`

Run:

```powershell
.\tools\setup_ffmpeg.ps1
```

Then repeat the extraction command with `--decode`.

### `python` is not recognized

Install Python 3.8 or newer and enable the option that adds Python to `PATH`,
then open a new PowerShell window.

### GitHub files contain only LFS pointer text

Install Git LFS and retrieve the real files:

```powershell
git lfs install
git lfs pull
```

### Validate downloaded evidence

Reference SHA-256 values for the raw and derived evidence are stored in
`SHA256SUMS.txt`. Example:

```powershell
Get-FileHash -Algorithm SHA256 `
  .\data\capture-01\raw\opus_1.csv
```

Compare the printed hash with the corresponding line in `SHA256SUMS.txt`.

## Dependency policy

The FFmpeg executable is intentionally downloaded during setup instead of being
committed to this repository. This keeps third-party platform-specific binaries
out of Git while still making the validated decoding workflow reproducible.

Large capture and audio artifacts are managed through Git LFS.
