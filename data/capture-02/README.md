# Capture 02

Status: **Confirmed** on 2026-09-09.

The two `.cfax` files in `raw/` were supplied by Vanessa after confirmation of
the capture-01 result. Preserve them unchanged. Put only reproducible,
validated outputs in `results/`.

## Sources

| File | Origin | Status |
| --- | --- | --- |
| `TEST_PM16_26_35.cfax` | Vanessa, original container | Immutable evidence |
| `opus_2.csv` | Report `0x36` CSV export of `TEST_PM16_26_35.cfax` | Immutable evidence |

`opus_2.csv` was exported locally on 2026-09-09, originally named
`tryopus_1.csv`. Its provenance is **Confirmed** by a payload-slice test: a
40-byte Opus payload slice taken from the CSV occurs in `TEST_PM16_26_35.cfax`
and does not occur in the other container.

Vanessa supplied a second container, `TEST_PM1620.cfax`, alongside this one. It
was shown to hold the capture-01 session rather than new audio and was moved to
`data/capture-01/raw/` on 2026-09-09. See that capture's README.

The `.cfax` container stores each frame with a 5-byte prefix
(`8f 01 44 00 a2`) ahead of the `0x36` report ID. The `a2` byte is the same
channel prefix used by the Bluetooth CRC-32 calculation described in
`../../docs/packet-layout.md`. The CSV export drops that prefix and begins at
the report ID, which is what `tools/extract_report36_opus.py` expects.

## Extraction: `opus_2.csv`

- Accepted Report `0x36` records: 4,861.
- CRC-valid records: 4,861 of 4,861.
- Variant A: 4,861. Variant B: 0.
- Exact silence packets: 0.
- Opus packet size: 200 bytes, every record. TOC byte `0xF4` on every packet.
- Stream: 48,000 Hz, stereo, 10 ms frames.
- Frame range: 2280 to 71162.

## Results

```
python tools/extract_report36_opus.py data/capture-02/raw/opus_2.csv --decode
```

- `opus_2_validation.json`
- `opus_2_corrected_zeroplus.opus_raw`
- `opus_2_corrected.ogg.opus`
- `opus_2_corrected_s16le_stereo.pcm`
- `opus_2_corrected.wav`

## Decode evidence

Decoder: FFmpeg 9.0.1-full_build (gyan.dev), built with `--enable-libopus`,
installed 2026-09-09. This is not the build used for capture 01; that build is
no longer present on the machine and was never recorded.

- FFmpeg reported no warnings and no errors for the whole stream.
- Reported container: Ogg, 48,000 Hz, stereo, 48.61 seconds, 182 kb/s.
- PCM size is exactly 9,333,120 bytes, which equals 4,861 packets x 480
  samples x 2 channels x 2 bytes. Every extracted packet reached the output.
- Re-running the extractor rewrote `.opus_raw` and `.ogg.opus` byte-for-byte
  identically, confirmed against the recorded SHA-256 values.

## Audio review

Human listening review passed on 2026-09-09: the decoded audio sounds correct.

Automated measurement of the decoded PCM:

- Total RMS: left 3,466, right 3,609. The channels are not identical, so the
  stream is true stereo rather than duplicated mono.
- Zero of the 48 one-second blocks fall below -60 dBFS. Content is continuous,
  consistent with `silence_packets` being 0.
- Level sits near -29 dBFS for the first 21 seconds, then steps up to roughly
  -17 dBFS, with peaks near -11 dBFS at 37 seconds.
- No pop or click at any packet-loss boundary. The largest sample-to-sample
  step at the 21 loss points is 2,970, below the 99.99th percentile of 5,798
  and far below the 9,772 reached inside ordinary loud passages.

### Clipping at 38.19 s

187 samples sit at full scale (`32767`), all inside packet 3819 and not at a
packet boundary: left 47 and 8 samples, right 90 and 35 samples. The longest
run is 1.88 ms of flat top on the right channel, followed by a normal decay.

This is clipping present in the source material, not a decode artifact. Capture
01 shows the same trait at lower severity (27 clipped samples). Capture 02 was
recorded roughly 12 dB hotter, which explains the difference.

## ATS3085 DSP decode: `results/from3085DSP/`

Status: **Candidate**, measured 2026-09-14. `ps5_result_capture02.pcm` is a
hardware decode of this capture produced outside this repository on
2026-09-11. Its provenance beyond the file name is not recorded here.

Compared against `opus_2_corrected_s16le_stereo.pcm`, the FFmpeg reference:

- 9,331,200 bytes against 9,333,120, a difference of exactly 1,920 bytes. The
  DSP emitted 4,860 of the 4,861 packets and stops one 10 ms frame early. It is
  otherwise aligned from sample 0, with no offset.
- Error RMS is 1.07 against a reference RMS of 3,541, so the difference sits
  70.4 dB below the signal.
- 57.86 % of samples are bit-exact, 90.73 % are within 1 LSB, 98.60 % within
  3 LSB.
- The 1.40 % of samples differing by 4 LSB or more begin at 20.68 s and cluster
  from 21.9 s onward. That is where this capture steps up from about -29 dBFS
  to -17 dBFS, so the deviation tracks signal level, which points at
  float-to-int16 conversion rather than a decoder divergence.

This is agreement at the level expected from rounding, not a decode defect. It
is labelled Candidate because the DSP build, its conversion settings and the
reason for the missing final frame are not recorded. Record them before
promoting it.

## Transport losses

Sequence-number continuity was checked per variant on the raw records.

| Capture | Received | Lost | Duplicated |
| --- | ---: | ---: | ---: |
| capture-01 variant A | 4,757 | 24 (0.50 %) | 0 |
| capture-01 variant B | 2,434 | 7 (0.29 %) | 0 |
| capture-02 variant A | 4,861 | 21 (0.43 %) | 1 |

Loss rates are comparable across both captures, so single dropped packets are a
property of the over-the-air capture method rather than a defect of this
export. 20 of the 21 gaps are a single packet.

The duplicate is a Bluetooth retransmission captured twice: frames 46954 and
46963 are byte-identical across all 398 bytes, including sequence number 93 and
the CRC. `tools/extract_report36_opus.py` does not detect this and counts it as
a distinct packet, so the decoded audio repeats one 10 ms frame at 31.52 s.

### Recorded durations are packet counts, not elapsed time

The `duration_seconds` field is derived from the packet count, so lost packets
are concatenated without a marker and the figure understates the recording.

| Capture | Recorded | Elapsed |
| --- | ---: | ---: |
| capture-01 | 71.91 s | 72.22 s |
| capture-02 | 48.61 s | 48.81 s |

This is acceptable for listening but must not be relied on for timing analysis
or for alignment against an external reference.

## Variant B is a phase, not a second stream

This resolves what earlier notes recorded as an unexplained absence.

In capture 01 the two variants never interleave. Variant B covers frames 2301
to 36611, variant A covers frames 36627 to 104444, and the changeover happens
exactly once. The two also differ in content: variant B is 2,233 of 2,434
silence packets (91.7 %), while variant A is 2 of 4,757 (0.0 %).

Variant B is therefore the idle or warm-up phase that precedes real audio, and
variant A is the audio itself. Capture 02 contains variant A only and no
silence packets because its recording began after that changeover, with audio
already flowing. The two facts explain each other and neither is anomalous.

Structurally, variant B carries one extra header byte: its length byte sits at
offset 76 and its payload at 77, against 75 and 76 for variant A. The variants
also differ at offsets 11, 68, 69, 72 and 277.

## Reproducibility limits

FFmpeg dithers when converting the decoder's float output to signed 16-bit, so
`.pcm` and `.wav` are not bit-reproducible across runs or builds; a re-decode
differs by at most 1 LSB on about 0.01 % of samples. The recorded PCM and WAV
hashes verify the stored files, not the decode. The `.opus_raw` and `.ogg.opus`
files are fully deterministic and were confirmed to rebuild identically.

## Housekeeping

Analyzer scratch files (`*.fsc`, `*.cfax-lock`) may appear in `raw/` while the
capture software has a container open. They are tool state, not evidence, and
must not be committed or hashed.
