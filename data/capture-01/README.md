# Capture 01

Status: **Confirmed**.

`raw/opus_1.csv` is the original Vanessa over-the-air export. Corrected derived
files are in `results/`. See `../../docs/packet-layout.md` and the repository
README for framing and reproduction details.

## Sources

| File | Origin |
| --- | --- |
| `opus_1.csv` | Vanessa over-the-air CSV export |
| `TEST_PM1620.cfax` | Analyzer container holding the same session |

`TEST_PM1620.cfax` arrived on 2026-09-08 with the capture-02 material and was
first stored under `data/capture-02/raw/`. It was moved here on 2026-09-09
after it was shown to hold this session rather than a new one. Its SHA-256 is
unchanged by the move.

The proof: exporting it to CSV and running the extractor produces an
`.opus_raw` byte-for-byte identical to
`results/opus_1_corrected_zeroplus.opus_raw` (`3523701431d68f95...`), with the
same 7,191 packets, 4,757 variant A, 2,434 variant B and 2,235 silence packets.
That intermediate CSV and its derived outputs were removed on 2026-09-09 once
the identity was established; they are reproducible from the container at any
time and were not kept as separate evidence.

## Known limitations

- `results/opus_1_corrected.ogg.opus` was built by an earlier version of
  `tools/extract_report36_opus.py`. It carries the OpusTags vendor string
  `Codex corrected DualSense Report 0x36 extraction`, while the current tool
  writes `DualSense Report 0x36 extraction`. The file **cannot be reproduced by
  the current tool**, so its recorded SHA-256 verifies the stored file only.
- The FFmpeg build used for the `.pcm` and `.wav` was never recorded and is no
  longer present on the machine. FFmpeg dithers when converting the decoder's
  float output to signed 16-bit, so PCM output is not bit-reproducible across
  runs or builds; a re-decode differs by at most 1 LSB on about 0.01 % of
  samples. The recorded PCM/WAV hashes verify the stored files, not the decode.
- Sequence-number continuity shows 24 lost packets in variant A (0.50 %) and 7
  in variant B (0.29 %). Because `duration_seconds` counts packets, the
  recorded 71.91 s understates the 72.22 s actually elapsed.
