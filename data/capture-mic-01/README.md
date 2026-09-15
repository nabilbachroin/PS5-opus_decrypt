# Capture Mic 01

Status: **Candidate** as of 2026-09-14. Extraction and decode are mechanically
validated for both directions; no human listening review has been recorded.

**Superseded by capture-mic-02**, which is Confirmed as of 2026-09-15 and is
the reference microphone capture. This one is kept as evidence: it is where the
Report `0x31` type 2 uplink was first located, and where the PS5 was observed
sending the microphone audio back down. Its audio is the weaker of the two,
with 22.1 % uplink packet loss and 1,872 clipped samples against 8.0 % and zero
in capture-mic-02.

`raw/PM0453_MIC_TEST.cfax` is a microphone test recorded over the air. It
arrived as an analyzer container only, with no CSV export, so it is the first
capture extracted directly from `.cfax`.

## Sources

| File | Origin | Status |
| --- | --- | --- |
| `raw/PM0453_MIC_TEST.cfax` | Vanessa, original container | Immutable evidence |

## Two audio streams, two directions

This capture carries audio in **both** directions, in two different Opus
configurations. The microphone uplink is the point of the capture.

| Direction | Channel | Report | Opus TOC | Config | Frames |
| --- | --- | ---: | ---: | --- | ---: |
| controller to PS5 (**microphone**) | `0xA1` | `0x31` type 2 | `0xD4` | CELT SWB 24 kHz stereo 10 ms | 8,599 |
| PS5 to controller (speaker) | `0xA2` | `0x36` | `0xF4` | CELT FB 48 kHz stereo 10 ms | 10,358 |

`0xA1` is HIDP DATA/INPUT and `0xA2` is DATA/OUTPUT, so the channel byte alone
fixes the direction. Report `0x31` also carries the ordinary controller state
as type 1 (27,661 frames); type 2 is the microphone.

## Report 0x31 type 2: the microphone uplink

Layout, **Confirmed** on 2026-09-14:

```text
offset 0        report id 0x31
offset 1        audio sequence (high nibble) | type (low nibble)
offset 2        Opus packet sequence, 8 bit, one step per 10 ms
offset 3..73    Opus packet, 71 bytes, TOC 0xD4
offset 74..77   Bluetooth CRC-32 over channel prefix 0xA1 and bytes 0..73
```

Type nibble distribution over 36,382 Report `0x31` frames: type 1 = 27,661,
type 2 = 8,599, everything else 3 to 36 frames each. Every remaining value is
a single-bit flip of `1` or `2` on a frame that also fails CRC, so there are
only two real types in this capture.

TOC `0xD4` is `1101 0100`: config 26 (CELT-only, super-wideband, 10 ms), stereo
bit set, one frame per packet. It holds on 8,512 of 8,599 frames; the other 87
values are single-bit flips of `0xD4` on damaged frames.

The exact silence packet is `D4 FF FE` followed by 68 zero bytes, the same
shape as the downlink's `F4 FF FE` plus 197 zeros.

### Evidence that this really is 24 kHz stereo

- **Spectral cutoff.** In two clipping-free windows (44-52 s and 55-63 s) the
  averaged spectrum drops 24 dB between the 11.9-12.3 kHz band and the
  12.3-13 kHz band, and the highest bin within 50 dB of the peak sits at
  12.01 kHz and 11.99 kHz. 12 kHz is the Nyquist frequency of 24 kHz. The
  48 kHz downlink decoded from the same container keeps content to 20 kHz, so
  the cutoff is a property of this stream, not of the measurement.
- **Packet size.** 71 bytes at 100 packets per second is 56.8 kb/s.
- **Decode.** FFmpeg decoded all 6,481 packets with no warnings and no errors.
  PCM sizes are exact: 6,221,760 bytes at 24 kHz (6,481 x 240 x 2 x 2) and
  12,443,520 bytes at 48 kHz (6,481 x 480 x 2 x 2).
- **Channels.** Mean absolute difference between left and right is 1.24 of
  32,768, but the channels are not bit-identical and the difference peaks at
  10,346. The stream is a true 2-channel Opus stream carrying what is
  effectively one microphone signal.

Opus always runs its decoder at 48 kHz internally, so Ogg granule positions
step by 480 per 10 ms packet regardless of the encoded bandwidth. That is why
`--decode` writes two PCM/WAV pairs for one stream:

- `*_24k.*` is the encoded rate and the honest size for this content.
- `*_48k.*` is the decoder's native output rate, kept for parity with the
  Report `0x36` captures and for any tool that expects 48 kHz.

They carry the same information. In clipping-free windows the 48 kHz file holds
-49 to -51 dB of its energy above 12 kHz, which is the noise floor; the
-27 dB figure over the clipped 25-39 s window is distortion created when the
decoder's float output is clamped to 16-bit, not signal. Use the 24 kHz pair
unless a downstream tool needs 48 kHz.

### Extraction

```powershell
python .\tools\extract_report31_mic_opus.py `
  .\data\capture-mic-01\raw\PM0453_MIC_TEST.cfax `
  --basename mic_uplink_1 `
  --decode
```

Result (`mic_uplink_1_validation.json`):

- Report `0x31` frames: 36,382. Type 2: 8,599.
- CRC-valid: 7,166. CRC-invalid: 1,433 (16.7 %), dropped. Bad TOC: 87.
- Emitted packets: 6,481, each 71 bytes. Exact silence packets: 7.
- Lost sequence slots: 1,840.
- Stream: 24 kHz encoded, stereo, 10 ms frames, 64.81 s.
- Re-running rewrote `.opus_raw` and `.ogg.opus` byte-for-byte identically.

### Measurement of the decoded microphone audio

- Total RMS: -25.5 dBFS on both channels.
- 1,872 full-scale samples (0.060 %), all between 25.26 s and 39.19 s, inside
  the loud passages. This is clipping in the source, as in capture 02.
- 4 of 65 one-second blocks fall below -60 dBFS.
- Level sits between -41 and -59 dBFS for most of the recording, with loud
  bursts reaching -11.6 dBFS at 25-29 s and -13.4 dBFS at 39 s. That shape is
  a room noise floor with speech bursts on top, which is what a microphone
  test should look like. It has not been confirmed by listening.

### The uplink is not contaminated by the downlink

Asked on 2026-09-14 after a listener reported hearing PS5 speaker audio in the
decoded microphone file. Two separate checks.

**Structural.** `mic_uplink_1_zeroplus.opus_raw` holds 6,481 packets, every one
71 bytes with TOC `0xD4`. `mic_1_corrected_zeroplus.opus_raw` holds 7,406
packets, every one 200 bytes with TOC `0xF4`. Zero packets are shared between
the two files. The extractor reads only `0xA1` Report `0x31` frames whose type
nibble is 2 and never opens a `0x36` frame, so the two streams cannot mix.

**Acoustic.** Both streams were rebuilt on their true 10 ms grids with lost
slots filled by the codec's own silence packet, then placed on a shared time
axis using container byte offset, which both directions write into as they are
captured. Correlating 10 ms band energies in eight 1.5 kHz bands, excluding
every filled slot:

| Downlink phase | Best correlation | Lag | Baseline at lags beyond 2 s |
| --- | ---: | ---: | ---: |
| variant B, intermittent | r = 0.39 to 0.66 per band | -130 ms | 0.43 |
| variant A, loud continuous | r = 0.00 to 0.08 per band | none | 0.09 |

During the variant B phase the two directions share content, and **the uplink
leads the downlink by about 130 ms**. That is the signature of the PS5
receiving the microphone audio and sending it back down, as monitoring,
sidetone or a chat mix. Acoustic pickup of the controller's own speaker would
show the opposite sign, the downlink leading by the few milliseconds of an
acoustic path.

During the variant A phase, where the downlink runs continuously near
-30 dBFS, there is no relationship at any lag in any band. Headphones plugged
into the controller would explain it, since that mutes the built-in speaker and
removes the acoustic path, but that has not been checked against the test
setup.

So the shared voice heard in both files is one source captured once. The
microphone file is the original; the downlink carries the PS5's delayed copy.

### Listenable evidence

`mic_1_uplink_vs_downlink_aligned_variantB.wav` and
`..._variantA.wav` carry the microphone uplink on the **left** channel and the
speaker downlink on the **right**, aligned as described above. Variant B is the
phase where the two directions share content; variant A is the phase where they
do not. Each channel is normalised to the same RMS, so relative level between
the directions is not preserved.

Known limitation: both were produced by an ad-hoc analysis script and are **not
regenerated by any committed tool**. Their recorded SHA-256 values verify the
stored files, not a reproducible pipeline.

**The two files do not share a timeline.** The uplink runs 64.81 s and the
downlink 74.06 s, and each concatenates its own lost packets without a marker,
so the same wall-clock moment sits at different positions in the two files.
Comparing them by timestamp is misleading. Rebuild both on their 10 ms grids
first, as above.

### Transport quality on the uplink

1,840 of 8,321 sequence slots are missing, 22.1 %. That is roughly three times
the downlink loss in the same container and twenty times the loss in captures
01 and 02. A plausible explanation is analyzer placement favouring the
console's transmissions over the controller's, but that is a hypothesis and has
not been tested.

The loss figure depends on the offset-2 counter really advancing once per
10 ms, which was checked against the downlink rather than assumed. Container
byte offset serves as a clock: across its main run the uplink spans 5,001
container bytes per sequence slot, while the downlink variant B run recorded
over the same stretch of the container spans 5,057 bytes per slot. The
downlink is known to be 10 ms per slot, and the two agree to 1.1 %, so the
uplink counter runs at the same cadence and the missing slots are real loss
rather than a misread rate.

Three runs survive the 100-packet minimum: 378, 238 and 5,865 slots. Ten
shorter bursts were dropped and are listed in `detached_bursts_dropped`.

`--keep-crc-invalid` raises the yield to 6,893 packets over 39 shorter runs by
admitting damaged frames. It is off by default: a frame with a flipped bit
feeds bit errors straight into the decoder, and a dropped 10 ms frame is the
safer failure.

**Do not use this timeline for timing analysis.** 64.81 s were emitted from
83.21 s of on-air span inside the runs, plus breaks between runs whose length
cannot be recovered from an 8-bit counter.

## Report 0x36: the speaker downlink

The same container also holds the PS5-to-controller stream, identical in layout
to captures 01 and 02. It was extracted first, before the uplink was located,
and is kept because it is valid evidence from the same session.

```powershell
python .\tools\extract_report36_from_cfax.py `
  .\data\capture-mic-01\raw\PM0453_MIC_TEST.cfax

python .\tools\extract_report36_opus.py `
  .\data\capture-mic-01\results\PM0453_MIC_TEST_report36.csv `
  --output-dir .\data\capture-mic-01\results `
  --basename mic_1 `
  --decode
```

- Report `0x36` frames found: 10,358. CRC-valid 9,715, CRC-invalid 643 (6.2 %).
- Emitted packets: 7,406. Variant A 2,408, variant B 4,998.
- Exact silence packets: 2,973, all in variant B.
- Decoded: 48 kHz stereo, 74.06 s, no FFmpeg warnings. PCM size exact.
- Content: silent to 23 s, intermittent bursts 24-45 s, silent 46-50 s,
  continuous near -30 dBFS from 49.98 s. Peak -14.8 dBFS, no clipping.
- Losses: 55 (7.21 %), 160 (3.60 %) and 231 (8.75 %) across three runs.
  74.06 s emitted from at least 78.52 s of span.

### New in this capture: the variant marker is not fixed

The marker at report offsets 67..71 is `91 05 6F 46 1F` and `91 06 7F 46 1F`
here, against `91 05 6F 39 1F` and `91 06 7F 39 1F` in captures 01 and 02.
Only offset 70 differs, and the same value appears at report offset 8
(`46 64 1F` here, `39 64 1F` in capture 02). It is a per-session value and does
not select the variant. Both downlink tools now match offsets 67, 68, 69 and
71 and treat offset 70 as a wildcard.

### Variant B is not purely idle here

Captures 01 and 02 supported a model in which variant B is the idle phase and
is 91.7 % exact silence. In this capture variant B is only 59.5 % silence
(2,973 of 4,998) and carries about 21 s of intermittent low-level audio, while
variant A remains 0 % silence. The phase ordering is unchanged: B first, then a
single changeover to A. The "B is idle" model holds as a tendency, not a rule.

## Why direct `.cfax` extraction is trusted

`tools/extract_report36_from_cfax.py` was validated against capture 02, which
has both a container and a Confirmed CSV-derived result. Running it on
`data/capture-02/raw/TEST_PM16_26_35.cfax` and feeding its CSV to
`tools/extract_report36_opus.py` produces a packet stream identical to the
Confirmed `opus_2_corrected_zeroplus.opus_raw` except for one packet: the
container-derived stream does not repeat the frame at 31.52 s.

That frame is the Bluetooth retransmission already documented in
`../capture-02/README.md` as being counted twice by the CSV path. Removing it
is a correction, so the container path reproduces the Confirmed result exactly
and repairs its one known defect.

`tools/extract_report31_mic_opus.py` applies the same rules to the uplink:
drop frames failing the CRC, keep one frame per sequence number preferring a
CRC-valid copy, emit in sequence order, and split runs on a forward sequence
jump wider than 64 packets. It cannot be cross-validated the same way, because
no earlier capture contains the uplink.

## Housekeeping

`results/PM0453_MIC_TEST_report36.csv` is a reproducible intermediate, not
evidence. It can be regenerated from the container at any time and may be
deleted once the Opus outputs are accepted.

## Correction log

An earlier pass on 2026-09-14 concluded that this container held no microphone
uplink. That was wrong. The conclusion rested on a per-byte entropy scan of
Report `0x31` that pooled all frames together; type 1 outnumbers type 2 three
to one, so the controller state dominated every byte position and the audio
payload never showed up. Splitting Report `0x31` by the type nibble first is
what makes the uplink visible.
