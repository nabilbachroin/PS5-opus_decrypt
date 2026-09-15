# Capture Mic 02

Status: **Confirmed** on 2026-09-15.

`raw/260915PM1129_MIC_TEST.cfax` is a second microphone test, recorded after
capture-mic-01 showed heavy packet loss and clipping. It is a container-only
capture with no CSV export, extracted by the same two tools.

## Basis for Confirmed

Per `AGENTS.md`, a decode is not validated because a tool accepts it. All of
the following are recorded below:

- Packet counts and framing checks for both directions.
- Codec parameters read from the bitstream and verified by measurement.
- Decoder diagnostics: FFmpeg reported no warnings and no errors, and every
  extracted packet reached the output at the exact expected PCM size.
- Byte-for-byte reproducibility of `.opus_raw`, `.ogg.opus` and the
  intermediate CSV on a second run.
- **Human listening review passed on 2026-09-15**, covering
  `mic_uplink_2_24k.wav` and an aligned stereo comparison carrying the
  microphone uplink on the left and the speaker downlink on the right. The
  review also settled the open question carried over from capture-mic-01, where
  a listener had heard speaker audio in the microphone file.

The microphone uplink layout in `../../docs/packet-layout.md` was already
Confirmed on capture-mic-01 from bitstream evidence. This capture reconfirms it
on a second, independent session with a listening review attached.

This capture is materially better than capture-mic-01 in every respect that
matters, and the microphone uplink shows **no measurable relationship** with the
speaker downlink.

## Sources

| File | Origin | Status |
| --- | --- | --- |
| `raw/260915PM1129_MIC_TEST.cfax` | Vanessa, original container | Immutable evidence |

## Two audio streams, two directions

| Direction | Channel | CID | Report | Opus TOC | Config | Frames |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| controller to PS5 (**microphone**) | `0xA1` | `0xF9` | `0x31` type 2 | `0xD4` | CELT SWB 24 kHz stereo 10 ms | 4,020 |
| PS5 to controller (speaker) | `0xA2` | `0x4A` | `0x36` | `0xF4` | CELT FB 48 kHz stereo 10 ms | 4,420 |

The layout described in `../../docs/packet-layout.md` applies unchanged. Only
the connection-specific values differ, and both were already treated as
variable:

- L2CAP CIDs are `0xF9` and `0x4A` here, against `0xEB` and `0x45` in
  capture-mic-01 and `0x44` in captures 01 and 02.
- The Report `0x36` per-session marker byte at report offset 70 is **`0x00`**
  here, against `0x46` in capture-mic-01 and `0x39` in captures 01 and 02.
  This is the third distinct value and confirms the byte is not a constant.
  Had the tools still matched it literally, this capture would have yielded
  zero downlink frames.

Report `0x31` type distribution over 16,424 frames: type 1 = 12,359,
type 2 = 4,020, every other value 1 to 11 frames and a single-bit flip on a
frame that also fails CRC. TOC `0xD4` holds on 3,991 of 4,020 type-2 frames.

## Microphone uplink

```powershell
python .\tools\extract_report31_mic_opus.py `
  .\data\capture-mic-02\raw\260915PM1129_MIC_TEST.cfax `
  --basename mic_uplink_2 `
  --decode
```

Result (`mic_uplink_2_validation.json`):

- Report `0x31` frames: 16,424. Type 2: 4,020.
- CRC-valid: 3,509. CRC-invalid: 511 (12.7 %), dropped. Bad TOC: 29.
- Emitted packets: 3,109, each 71 bytes. Exact silence packets: 0.
- Lost sequence slots: 269 of 3,378 (8.0 %).
- Three runs kept: 1,292, 139 and 1,678 slots. Three shorter bursts dropped.
- Stream: 24 kHz encoded, stereo, 10 ms frames, 31.09 s.
- FFmpeg decoded every packet with no warnings and no errors. PCM sizes are
  exact: 2,984,640 bytes at 24 kHz and 5,969,280 bytes at 48 kHz.
- Re-running rewrote `.opus_raw` and `.ogg.opus` byte-for-byte identically.

### Measurement of the decoded audio

- Total RMS -33.6 dBFS on both channels; peak 19,692, that is -4.4 dBFS.
- **No clipping at all.** Zero full-scale samples, against 1,872 in
  capture-mic-01. The level is well chosen this time.
- Mean absolute difference between left and right is 1.06 of 32,768, peaking at
  371. Capture-mic-01 peaked at 10,346. Effectively one microphone signal
  carried in a true 2-channel stream.
- 2 of 32 one-second blocks fall below -60 dBFS, at 18 s and 19 s. Content runs
  between -27 and -59 dBFS elsewhere, with no long silent stretch.
- Spectral cutoff measured at 12.00 kHz in two windows (5-13 s and 20-28 s),
  confirming the 24 kHz encoding independently of capture-mic-01.

### Channel count: stereo bitstream, mono content

TOC `0xD4` sets the stereo bit, so each packet codes two channels and a decoder
configured for mono will not decode it correctly. The content, however, is one
microphone signal: 84.0 % of 10 ms blocks have left and right bit-identical,
Pearson correlation is 0.99995, and the side channel sits 45.7 dB below the
mid. Where the channels do differ, the mean absolute difference is 6.6 of
32,768 and the maximum is 371.

Capture-mic-01 measures 95.3 % identical blocks and a side channel 37.3 dB
below mid, but 59.4 % of its side energy sits in the 36 blocks containing
clipping, so this capture is the cleaner measurement of the two.

Downstream code may downmix to mono without losing anything audible. The
decoder itself must still be configured for 2 channels.

### Framing for the ATS3085 DSP

`mic_uplink_2_zeroplus.opus_raw` is tightly packed: a 4-byte big-endian length
followed immediately by the 71-byte packet, so records repeat every 75 bytes.
That matches the header the DSP expects, since `pcm_hdr_get_len()` in
`codec_pcm.c` reads a 2-word header as a big-endian 32-bit value.

It does **not** match the slot the DSP reads. `config.h` derives the slot as

```text
OPUS_RX_PKT_WORDS = OPUS_RX_HDR_WORDS + (OPUS_RX_PAYLOAD_BYTES + 1) / 2
```

which rounds an odd payload up to a 16-bit word boundary:

| `OPUS_RX_PAYLOAD_BYTES` | `OPUS_RX_PKT_WORDS` | Slot |
| ---: | ---: | ---: |
| 78 | 40 | 80 B |
| 200 | 102 | 204 B |
| **71** | **38** | **76 B** |

The first two reproduce the values the DSP's own comments record, so the
arithmetic is confirmed. 71 bytes therefore occupy a **76-byte** slot, not 75.
Feeding the tightly packed file to a decoder configured for 71 decodes the
first frame and then desynchronises.

`--dsp-slot` writes the padded form the DSP expects, a 4-byte big-endian
length, the payload, then zero padding to the full slot:

```powershell
python .\tools\extract_report31_mic_opus.py `
  .\data\capture-mic-02\raw\260915PM1129_MIC_TEST.cfax `
  --basename mic_uplink_2 `
  --dsp-slot 200 --dsp-slot 71 `
  --decode
```

| File | Slot | Pad | Use |
| --- | ---: | ---: | --- |
| `mic_uplink_2_dspslot204.opus_raw` | 204 B | 129 B | `OPUS_RX_PAYLOAD_BYTES` left at 200, no DSP rebuild |
| `mic_uplink_2_dspslot76.opus_raw` | 76 B | 1 B | `OPUS_RX_PAYLOAD_BYTES` set to 71 |

The length check in `codec_pcm.c` is `payload_bytes > OPUS_RX_PAYLOAD_BYTES`, so
71 passes against a 200-byte slot unchanged. Both files were verified by
reimplementing `pcm_hdr_get_len()` and `pcm_pkt_unpack()` byte for byte: all
3,109 frames read back length 71, TOC `0xD4`, and a payload identical to the
tightly packed file.

Decoder parameters are runtime arguments to `opus_decoder_create()`, so the MCU
must supply them: **2 channels**, and 24000 or 48000 Hz. Two channels is not
optional, because the TOC stereo bit is set.

## Speaker downlink

```powershell
python .\tools\extract_report36_from_cfax.py `
  .\data\capture-mic-02\raw\260915PM1129_MIC_TEST.cfax

python .\tools\extract_report36_opus.py `
  .\data\capture-mic-02\results\260915PM1129_MIC_TEST_report36.csv `
  --output-dir .\data\capture-mic-02\results `
  --basename mic_2_downlink `
  --decode
```

- Report `0x36` frames found: 4,420. CRC-valid 4,203, CRC-invalid 217 (4.9 %).
- Emitted packets: 3,049, all variant A. Exact silence packets: 0.
- One continuous run, 90 lost slots (2.9 %), 1,149 retransmissions.
- Decoded: 48 kHz stereo, 30.49 s, no FFmpeg warnings. PCM size exact.

Variant B does not appear. As in capture 02, the recording began after the
changeover, with audio already flowing.

## The uplink is clean in this capture

Repeating the check that capture-mic-01 failed. Both streams were rebuilt on
their true 10 ms grids with lost slots filled by the codec's own silence
packet, placed on a shared time axis using container byte offset, and
correlated as 10 ms band energies in eight 1.5 kHz bands with every filled slot
excluded.

| Uplink run | Overlap | Best correlation | Lag | Baseline | Margin |
| --- | ---: | ---: | ---: | ---: | ---: |
| run covering 1,430 slots | 12.7 s | r = 0.079 | -3000 ms | 0.079 | **+0.000** |
| run covering 1,802 slots | 17.6 s | r = 0.136 | +590 ms | 0.051 | **+0.084** |

Per-band correlation at plausible loopback lags ranges from -0.05 to 0.16.

Compare capture-mic-01, where the intermittent phase reached r = 0.39 to 0.66
in **every** band at a consistent -130 ms lag with a margin of +0.14 to +0.20.
Nothing of that shape is present here: no broad peak, no consistent lag, and
the one non-zero margin sits at +590 ms, which is not a plausible monitoring
delay.

So in this capture the microphone uplink and the speaker downlink carry
unrelated audio. Whatever loopback or monitoring path was active during
capture-mic-01 is either absent here or inaudible.

### Listenable evidence for the contamination check

`mic_2_uplink_vs_downlink_aligned.wav` carries the microphone uplink on the
**left** channel and the speaker downlink on the **right**, both rebuilt on
their true 10 ms grids and placed on the shared container-offset time axis, so
the same wall-clock moment sits at the same position in both channels. Each
channel is normalised to the same RMS so they can be compared by ear; relative
level between the two directions is therefore not preserved.

Known limitation: this file was produced by an ad-hoc analysis script and is
**not regenerated by any committed tool**. Its recorded SHA-256 verifies the
stored file, not a reproducible pipeline. The method is fully described above.

Structural separation is the same as before and is absolute:
`mic_uplink_2_zeroplus.opus_raw` holds 3,109 packets of 71 bytes with TOC
`0xD4`; `mic_2_downlink_corrected_zeroplus.opus_raw` holds 3,049 packets of
200 bytes with TOC `0xF4`. The extractor reads only `0xA1` Report `0x31`
frames whose type nibble is 2 and never opens a `0x36` frame.

## Transport quality, against capture-mic-01

| Measure | capture-mic-01 | capture-mic-02 |
| --- | ---: | ---: |
| uplink CRC failures | 16.7 % | **12.7 %** |
| uplink lost packets | 22.1 % | **8.0 %** |
| downlink CRC failures | 6.2 % | **4.9 %** |
| downlink lost packets | 3.6 to 8.75 % | **2.9 %** |
| uplink clipped samples | 1,872 | **0** |

Uplink loss is still roughly three times the downlink loss in the same
container, the same asymmetry seen in capture-mic-01. Analyzer placement
favouring the console's transmissions over the controller's would explain it,
but that remains untested.

**Do not use either timeline for timing analysis.** The uplink emitted 31.09 s
from 33.78 s of on-air span inside its runs, plus two breaks between runs whose
length an 8-bit counter cannot recover. The downlink emitted 30.49 s from
31.39 s. The two files therefore do not share a timeline and must be rebuilt on
their 10 ms grids before being compared by timestamp.

## Two decoded sample rates

`--decode` writes both a 24 kHz and a 48 kHz PCM/WAV pair because Opus always
runs its decoder at 48 kHz internally regardless of the encoded bandwidth. The
24 kHz pair is the encoded rate and the honest size for this content; the
48 kHz pair is the decoder's native output, kept for parity with the Report
`0x36` captures. They carry the same information. Prefer the 24 kHz pair.
