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
- Capture mic 01 is a **Candidate** as of 2026-09-14 and carries audio in both
  directions. It is superseded by capture mic 02 and kept as evidence; no
  listening review is recorded for it.
- **The microphone uplink is Report `0x31` type 2**, controller to PS5 on the
  `0xA1` HIDP input channel. Report byte 1 is a sequence number in the high
  nibble and a type in the low nibble; type 1 is controller state, type 2 is
  audio. Each type-2 report carries one 71-byte Opus packet at offsets 3..73
  with TOC `0xD4`: CELT-only, super-wideband, stereo, 10 ms. The encoded rate
  is 24 kHz, confirmed by a measured spectral cutoff at 12.0 kHz on two
  independent captures. Capture mic 02 is the reference for this stream.
- Both microphone captures also carry the speaker downlink, Report `0x36` on
  `0xA2`, the same stream as captures 01 and 02.
- Capture mic 01 arrived as a `.cfax` container only, so it is the first
  capture extracted by `tools/extract_report36_from_cfax.py` and
  `tools/extract_report31_mic_opus.py`. The downlink tool was validated against
  capture 02, where it reproduces the Confirmed result exactly except that it
  does not repeat the retransmitted frame at 31.52 s.
- The variant marker is not fully fixed. Report offset 70 is a per-session
  value and both tools now treat it as a wildcard. The recorded hashes for
  captures 01 and 02 still reproduce byte-for-byte after that change.
- Capture mic 01 is a much noisier recording, and not equally so in both
  directions: the downlink loses 3.6 % to 8.75 % of packets with 6.2 % CRC
  failures, while the uplink loses 22.1 % with 16.7 % CRC failures. Captures 01
  and 02 lose roughly 0.4 %. Neither timeline may be used for timing analysis.
- Capture mic 02 is **Confirmed** as of 2026-09-15, including a human listening
  review, and supersedes capture mic 01 as the reference microphone evidence:
  3,109 uplink packets for 31.09 s and 3,049 downlink packets for 30.49 s, both
  decoded without FFmpeg warnings and both reproducible byte-for-byte. Uplink
  loss drops to 8.0 % and there is **no clipping at all**, against 1,872 clipped
  samples in capture mic 01. Capture mic 01 remains a Candidate.
- The microphone stream is a **stereo bitstream carrying mono content**. The
  TOC stereo bit is set, so a decoder must be configured for 2 channels or the
  packets will not decode; but 84.0 % of 10 ms blocks have left and right
  bit-identical, the channels correlate at 0.99995, and the side channel sits
  45.7 dB below the mid. Downstream code may downmix to mono safely.
- Capture mic 02 also settles a question raised against capture mic 01, where a
  listener heard speaker audio in the microphone file. Band-energy correlation
  between the two directions finds nothing here: margin over baseline +0.000
  and +0.084 for the two uplink runs, against r = 0.39 to 0.66 in every band at
  a steady -130 ms lag in capture mic 01. In that earlier capture the PS5 was
  sending the microphone audio back down; the microphone file itself was never
  contaminated.
- The Report `0x36` per-session marker byte at report offset 70 has now taken
  three values: `0x39`, `0x46` and `0x00`. L2CAP CIDs likewise change per
  connection. Both are matched as wildcards; had they not been, capture mic 02
  would have yielded zero downlink frames.

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
    results/             Validated results, plus the ATS3085 DSP decode
  capture-mic-01/
    raw/                 Microphone test container, no CSV export
    results/             Candidate Opus and decoded audio, both directions
  capture-mic-02/
    raw/                 Second microphone test container, no CSV export
    results/             Confirmed Opus and decoded audio, both directions
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

## Reproduce capture mic 01

This capture has no CSV export, so extraction starts from the analyzer
container. It carries audio in both directions, extracted by two different
tools.

### Microphone uplink, controller to PS5

```powershell
python .\tools\extract_report31_mic_opus.py `
  .\data\capture-mic-01\raw\PM0453_MIC_TEST.cfax `
  --basename mic_uplink_1 `
  --decode
```

Expected summary:

```text
packets:                 6481
packet_bytes:            71
silence_packets:         7
lost_slots:              1840
encoded_sample_rate_hz:  24000
channels:                2
frame_duration_ms:       10
duration_seconds:        64.81
```

This writes `.opus_raw`, `.ogg.opus`, a validation JSON, and with `--decode`
both a 24 kHz and a 48 kHz PCM/WAV pair. 24 kHz is the encoded rate; 48 kHz is
the Opus decoder's native output rate and is there for parity with the other
captures.

### Speaker downlink, PS5 to controller

Step 1 rebuilds an analyzer-equivalent CSV; step 2 is the same tool used for
every other capture.

```powershell
python .\tools\extract_report36_from_cfax.py `
  .\data\capture-mic-01\raw\PM0453_MIC_TEST.cfax

python .\tools\extract_report36_opus.py `
  .\data\capture-mic-01\results\PM0453_MIC_TEST_report36.csv `
  --output-dir .\data\capture-mic-01\results `
  --basename mic_1 `
  --decode
```

Expected summary for capture mic 01:

```text
packets:            7406
packet_bytes:       200
variants:           A=2408, B=4998
silence_packets:    2973
crc_valid:          7406
sample_rate_hz:     48000
channels:           2
duration_seconds:   74.06
```

## Reproduce capture mic 02

Same two tools, same order, no new options. This capture is **Confirmed** and
is the one to work from.

```powershell
python .\tools\extract_report31_mic_opus.py `
  .\data\capture-mic-02\raw\260915PM1129_MIC_TEST.cfax `
  --basename mic_uplink_2 `
  --decode

python .\tools\extract_report36_from_cfax.py `
  .\data\capture-mic-02\raw\260915PM1129_MIC_TEST.cfax

python .\tools\extract_report36_opus.py `
  .\data\capture-mic-02\results\260915PM1129_MIC_TEST_report36.csv `
  --output-dir .\data\capture-mic-02\results `
  --basename mic_2_downlink `
  --decode
```

Expected summary:

```text
uplink   packets 3109, 71 bytes each, 24000 Hz encoded, 31.09 s, 269 lost
downlink packets 3049, 200 bytes each, 48000 Hz, 30.49 s, variant A only
```

### Extract from any `.cfax` container

A container holds every on-air transmission, including Bluetooth
retransmissions and frames damaged in flight, so a plain byte scan is not a
stream. `tools/extract_report36_from_cfax.py` drops frames that fail the
Bluetooth CRC-32, keeps one frame per audio sequence number, and emits them in
sequence order. It writes `*_report36.csv` and a `*_cfax_scan.json` report
giving per-segment received, lost and retransmitted counts.

```powershell
python .\tools\extract_report36_from_cfax.py <container.cfax> `
  --output-dir <dir> `
  --basename <name>
```

- `--keep-crc-invalid` uses a damaged frame when no valid copy of that sequence
  exists. Off by default; a damaged frame carries bit errors into the decoder.
- `--min-segment N` sets the shortest run kept, in packets. Default 100.
  Shorter runs are detached bursts, not part of the stream, and are listed in
  the scan JSON.

The tool is validated against capture 02, which has both a container and a
Confirmed CSV-derived result. See `docs/packet-layout.md`.

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

From `tools/extract_report36_from_cfax.py`:

- `*_report36.csv`: analyzer-equivalent CSV rebuilt from a container. A
  reproducible intermediate, not evidence.
- `*_cfax_scan.json`: frames scanned, CRC and marker statistics, L2CAP CIDs
  seen, and per-segment received, lost and retransmitted counts.

From `tools/extract_report31_mic_opus.py` (microphone uplink):

- `*_zeroplus.opus_raw`: 4-byte big-endian payload length followed by one
  71-byte Opus packet, repeated.
- `*.ogg.opus`: the same packets in an Ogg Opus container, `OpusHead` input
  sample rate 24000.
- `*_s16le_stereo_24k.pcm` and `*_24k.wav`: decoded at the encoded rate.
- `*_s16le_stereo_48k.pcm` and `*_48k.wav`: decoded at the Opus decoder's
  native rate.
- `*_dspslot<N>.opus_raw`: written by `--dsp-slot`. The same big-endian length
  and payload, zero padded to the fixed slot the ATS3085 DSP reads. An odd
  payload rounds up to a word boundary, so 71 bytes give a 76-byte slot.
- `*_validation.json`: type distribution, CRC and TOC statistics, per-segment
  loss, codec parameters, duration, and output paths.

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
