# DualSense Opus Packet Layout

Covers the PS5-to-controller downlink in Report `0x36` and the
controller-to-PS5 microphone uplink in Report `0x31` type 2.

Status: **Confirmed** for capture 01 on 2026-09-08 and for capture 02 on
2026-09-09. Amended on 2026-09-14 with capture-mic-01: the microphone uplink
layout is added, the Report `0x36` variant marker carries one per-session byte,
and variant B is not always idle. **Confirmed** again on capture-mic-02 on
2026-09-15, including a human listening review; that capture needed no
adjustment beyond the values already treated as per-connection.

## Report 0x36 framing (downlink, PS5 to controller)

- Report length: 398 bytes.
- Report ID: `0x36` at offset 0.
- Bluetooth CRC-32: offsets 394..397, calculated over channel prefix `0xA2`
  followed by report bytes 0..393.
- Audio packet length: 200 bytes for every accepted Report `0x36` record.

## Report 0x36 audio variants

| Variant | Marker at 67..71 | Audio sequence | Length byte | Opus payload |
| --- | --- | ---: | ---: | --- |
| A | `91 05 6F ** 1F` | 73 | 75 (`C8`) | 76..275 |
| B | `91 06 7F ** 1F` | 74 | 76 (`C8`) | 77..276 |

Offset 70 (`**`) does **not** select the variant. It is a per-session value,
with three distinct values observed so far: `0x39` in captures 01 and 02,
`0x46` in capture-mic-01, `0x00` in capture-mic-02. The same value appears at
report offset 8, ahead of the fixed `64 1F` (`39 64 1F` against `46 64 1F`).
Both extraction tools match offsets 67, 68, 69 and 71 only. Treating offset 70
as fixed rejects every frame of a different session: matching it literally
would have yielded zero downlink frames from capture-mic-02.

The variants are successive phases of one session, not two concurrent streams.
Confirmed on capture 01: variant B covers frames 2301..36611 and variant A
covers frames 36627..104444, with a single changeover and no interleaving.
Capture-mic-01 shows the same ordering: variant B, one changeover, then
variant A. A capture that starts after the changeover contains variant A only;
capture 02 is such a capture. Besides the one extra header byte, the variants
differ at offsets 11, 68, 69, 72 and 277.

Variant B tends to be the idle or warm-up phase, but that is a tendency and not
a rule. It is 91.7 % exact silence in capture 01 and only 59.5 % in
capture-mic-01, where it carries about 21 s of intermittent low-level audio.
Variant A is 0.0 % silence in every capture measured so far. Do not treat
variant B as discardable.

The first payload byte is `0xF4`. For these packets it identifies an Opus
CELT-only fullband stereo frame with 10 ms duration. The exact silence packet
is `F4 FF FE` followed by 197 zero bytes.

## Corrected interpretation

The former dynamic 199/263-byte model was an offset error, not variable Opus
framing. It skipped the first three Opus bytes and then included bytes belonging
to the following transport area:

- 199 bytes = 197 remaining Opus bytes plus `92 40`.
- 263 bytes = the same 199 bytes plus the following 64-byte subpacket.

Decoder input is one complete 200-byte Opus packet. File or DSP transport
prefixes are not part of the Opus packet:

- Zeroplus file framing: 4-byte big-endian length + 200-byte packet.
- Observed MCU/DSP framing: 2-byte little-endian length + 200-byte packet.
- Ogg Opus: packets are stored in Ogg pages with `OpusHead` and `OpusTags`.

## Capture 01 evidence

- Accepted Report `0x36` records: 7,191.
- CRC-valid records: 7,191.
- Exact silence packets: 2,235.
- Decoded stream: Opus, 48,000 Hz, stereo, 71.91 seconds.
- FFmpeg decoded every packet without warnings or errors.

## Capture 02 evidence

The same layout applies unchanged; no offset or assumption needed adjustment.

- Accepted Report `0x36` records: 4,861.
- CRC-valid records: 4,861.
- Variant A: 4,861. Variant B: 0.
- Exact silence packets: 0.
- Decoded stream: Opus, 48,000 Hz, stereo, 48.61 seconds.
- FFmpeg 9.0.1 decoded every packet without warnings or errors.
- Human listening review passed on 2026-09-09.

Capture 02 is **Confirmed** as of 2026-09-09, including a human listening
review.

## Capture mic 01 evidence

Status: **Candidate**, 2026-09-14, superseded by capture-mic-02. Extracted
from the container, with no CSV export available. This capture carries audio in
both directions and is where the Report `0x31` type 2 uplink was first located.

### Microphone uplink, Report `0x31` type 2

- Report `0x31` frames: 36,382. Type 1: 27,661. Type 2: 8,599.
- CRC-valid type 2: 7,166. CRC-invalid: 1,433 (16.7 %). Bad TOC: 87.
- TOC `0xD4` on 8,512 of 8,599 frames; the other 87 are single-bit flips.
- Emitted packets: 6,481, each 71 bytes. Exact silence packets: 7.
- Lost sequence slots: 1,840 of 8,321 (22.1 %).
- Decoded stream: Opus CELT SWB, 24 kHz encoded, stereo, 64.81 seconds.
- FFmpeg decoded every packet without warnings or errors; PCM sizes match
  6,481 x 240 x 2 x 2 at 24 kHz and 6,481 x 480 x 2 x 2 at 48 kHz exactly.
- Spectral cutoff measured at 12.0 kHz, confirming the 24 kHz encoding.
- 1,872 full-scale samples (0.060 %), all between 25.26 s and 39.19 s, inside
  the loud passages. Source clipping, as in capture 02.
- No human listening review yet.

### Speaker downlink, Report `0x36`

The layout applies unchanged apart from the per-session marker byte described
under Report 0x36 audio variants.

- Report `0x36` frames found: 10,358. CRC-valid 9,715, CRC-invalid 643 (6.2 %).
- Emitted packets after deduplication: 7,406. Variant A 2,408, variant B 4,998.
- Exact silence packets: 2,973, all in variant B.
- Decoded stream: Opus, 48,000 Hz, stereo, 74.06 seconds.
- FFmpeg decoded every packet without warnings or errors; PCM size matches
  7,406 x 480 x 2 x 2 bytes exactly.
- No human listening review yet.

The same container also carries the microphone uplink on `0xA1` as Report
`0x31` type 2. See the next section and `../data/capture-mic-01/README.md`.

## Capture mic 02 evidence

Status: **Confirmed** on 2026-09-15, including a human listening review. A
second, much cleaner microphone test. Container-only, both directions present,
layout unchanged. This is the reference microphone capture; capture-mic-01
remains Candidate.

### Microphone uplink, Report `0x31` type 2

- Report `0x31` frames: 16,424. Type 1: 12,359. Type 2: 4,020.
- CRC-valid type 2: 3,509. CRC-invalid: 511 (12.7 %). Bad TOC: 29.
- TOC `0xD4` on 3,991 of 4,020 frames.
- Emitted packets: 3,109, each 71 bytes. Exact silence packets: 0.
- Lost sequence slots: 269 of 3,378 (8.0 %), across three runs.
- Decoded stream: Opus CELT SWB, 24 kHz encoded, stereo, 31.09 seconds.
- FFmpeg decoded every packet without warnings or errors; PCM sizes exact.
- Spectral cutoff measured at 12.00 kHz in two windows, independently
  reconfirming the 24 kHz encoding.
- **No clipping**: zero full-scale samples, peak -4.4 dBFS.
- Human listening review passed on 2026-09-15.

### Speaker downlink, Report `0x36`

- Report `0x36` frames found: 4,420. CRC-valid 4,203, CRC-invalid 217 (4.9 %).
- Emitted packets: 3,049, all variant A. Exact silence packets: 0.
- One continuous run, 90 lost slots (2.9 %).
- Decoded stream: Opus, 48,000 Hz, stereo, 30.49 seconds, no FFmpeg warnings.
- Per-session marker byte at report offset 70 is `0x00`, a third distinct
  value. L2CAP CIDs are `0xF9` uplink and `0x4A` downlink.

### The uplink carries no trace of the downlink here

The band-energy correlation that flagged capture-mic-01 finds nothing in this
capture: margin over baseline is +0.000 for one uplink run and +0.084 for the
other, with per-band correlation between -0.05 and 0.16 and no consistent lag.
Capture-mic-01 reached r = 0.39 to 0.66 in every band at a steady -130 ms.
Whatever monitoring or loopback path was active then is absent or inaudible
here. See `../data/capture-mic-02/README.md`.

## DualSense Report 0x31 microphone uplink

Status: **Confirmed** for capture-mic-01 on 2026-09-14 from bitstream evidence,
and again for capture-mic-02 on 2026-09-15 with a human listening review
attached. Two independent sessions, identical layout.

Report `0x31` travels controller to PS5 on the HIDP DATA/INPUT channel
(`0xA1`). Report byte 1 splits into a sequence number in the high nibble and a
type in the low nibble. Type 1 is the ordinary controller state report; type 2
carries microphone audio, one Opus packet per report.

```text
offset 0        report id 0x31
offset 1        audio sequence (high nibble) | type (low nibble)
offset 2        Opus packet sequence, 8 bit, one step per 10 ms
offset 3..73    Opus packet, 71 bytes, TOC 0xD4
offset 74..77   Bluetooth CRC-32 over channel prefix 0xA1 and bytes 0..73
```

- Report length: 79 bytes of L2CAP payload, that is `0xA1` plus 78 report bytes.
- CRC span is bytes 0..73, against 0..393 for Report `0x36`.
- TOC `0xD4` is `1101 0100`: config 26 (CELT-only, super-wideband, 10 ms),
  stereo bit set, one frame per packet. Encoded sample rate is 24 kHz.
- The exact silence packet is `D4 FF FE` followed by 68 zero bytes.
- 71 bytes at 100 packets per second is 56.8 kb/s.

The offset-2 counter advances once per 10 ms, checked rather than assumed.
Using container byte offset as a clock, the uplink spans 5,001 container bytes
per sequence slot across its main run, against 5,057 for the downlink variant B
run recorded over the same stretch of container. The downlink is known to be
10 ms per slot and the two agree to 1.1 %.

The two directions therefore differ in codec configuration:

| Direction | Channel | Report | TOC | Config | Packet |
| --- | ---: | ---: | ---: | --- | ---: |
| PS5 to controller | `0xA2` | `0x36` | `0xF4` | CELT fullband 48 kHz stereo 10 ms | 200 B |
| controller to PS5 | `0xA1` | `0x31` type 2 | `0xD4` | CELT SWB 24 kHz stereo 10 ms | 71 B |

Opus always runs its decoder at 48 kHz internally, so Ogg granule positions
step by 480 per 10 ms packet for both streams. The 24 kHz figure is the encoded
bandwidth, confirmed by measurement: in clipping-free windows the decoded
uplink spectrum drops 24 dB between 11.9-12.3 kHz and 12.3-13 kHz, with the
highest bin within 50 dB of the peak at 12.0 kHz. That is the Nyquist frequency
of 24 kHz. The downlink decoded from the same container keeps content to
20 kHz.

### 24 kHz: confirmed. 2 channels: real in the bitstream, mono in content

Both halves of the codec description hold, but they hold differently, and a
decoder implementation has to respect the difference.

**24 kHz is the encoded rate.** TOC `0xD4` decomposes as config 26, stereo bit
set, one frame per packet. Config 26 is CELT-only at super-wideband, which
codes bands up to 12 kHz, the bandwidth a 24 kHz sample rate carries. Measured
independently on both captures, the decoded spectrum drops off at exactly
12.00 kHz.

**2 channels is real at the bitstream level.** The stereo bit is set, so each
packet codes two channels and a decoder configured for mono will not decode it
correctly. Configure for 2 channels.

**The content is one microphone signal.** Measured on the decoded 24 kHz PCM:

| Measure | capture-mic-01 | capture-mic-02 |
| --- | ---: | ---: |
| 10 ms blocks where L and R are bit-identical | 95.3 % | 84.0 % |
| Pearson correlation L against R | 0.99963 | 0.99995 |
| side (L-R)/2 below mid (L+R)/2 | 37.3 dB | 45.7 dB |
| mean \|L-R\| in the blocks that differ | 26.4 | 6.6 |
| max \|L-R\| | 10,346 | 371 |

In capture-mic-01, 59.4 % of all side-channel energy sits in the 36 blocks that
contain clipping, where clamping the decoder's float output to 16-bit hits the
two channels differently. That inflates its figures; capture-mic-02 does not
clip and is the better measurement.

So downstream code may downmix to mono without losing anything audible, but the
decoder itself must still be told the stream is stereo.

Only types 1 and 2 are real. Over 36,382 Report `0x31` frames in
capture-mic-01, type 1 has 27,661 and type 2 has 8,599; every other type value
appears 1 to 36 times, is a single-bit flip of `1` or `2`, and fails CRC.

`tools/extract_report31_mic_opus.py` extracts this stream. It applies the same
retransmission and sequencing rules as the downlink container tool described
below. It cannot be cross-validated against an analyzer CSV, because no earlier
capture contains the uplink.

### A per-byte entropy scan does not find this stream

Recorded because it cost a wrong conclusion on 2026-09-14. Pooling every Report
`0x31` frame and measuring entropy per byte position shows only controller
state: type 1 outnumbers type 2 three to one, so the state report dominates
every byte position and the audio payload is invisible. Split Report `0x31` by
the type nibble before looking at content.

## `.cfax` container framing

Amended on 2026-09-14. The earlier note described the prefix as the fixed
5 bytes `8f 01 44 00 a2`. Only the last byte is fixed. The prefix is Bluetooth
L2CAP framing, and the channel identifier changes per connection:

```text
<frame size, 2 B LE> <L2CAP payload length, 2 B LE> <CID, 2 B LE> <0xA2> <report>
        403                        399                  varies
```

`0x44` in captures 01 and 02, `0x45` in capture-mic-01. Matching the CID as a
constant finds nothing in a container from a different connection. The trailing
`0xA2` is the HIDP DATA/OUTPUT channel byte and is the same prefix used by the
CRC-32 calculation above. CSV exports drop the whole prefix and start at the
report ID.

`0xA2` means host to controller, so Report `0x36` is audio the PS5 sends to the
controller. Microphone audio travels the other way, on `0xA1` (DATA/INPUT), as
Report `0x31` type 2. Its L2CAP framing is the same shape with a payload length
of 79 instead of 399.

Records are not stored contiguously; the container is an analyzer database, so
a record walk by length does not work. A byte scan anchored on the framing
above is what both tools use.

### The container is not a stream

A container holds every on-air transmission. A plain scan of capture 02 yields
7,068 Report `0x36` frames against the 4,861 records in its CSV export. The
surplus is Bluetooth retransmissions, and they are not adjacent: the observed
order around one loss is 76, 76, 78, 77, 78, 78, 78, 79, so capture order is
not sequence order.

`tools/extract_report36_from_cfax.py` therefore rebuilds a stream by:

1. dropping frames that fail the Bluetooth CRC-32, because a damaged frame can
   otherwise win a slot — one capture-02 slot has a first copy with a single
   bit flipped at payload offset 36 and two valid retransmissions after it;
2. keeping one frame per audio sequence number, preferring a CRC-valid copy;
3. emitting frames in sequence order, not capture order;
4. starting a new segment on a forward sequence jump wider than 64 packets,
   which is a break in the capture rather than packet loss, and dropping runs
   shorter than 100 packets as detached bursts.

Validated against capture 02 on 2026-09-14: the container path reproduces the
Confirmed `opus_2_corrected_zeroplus.opus_raw` exactly, except that it does not
repeat the frame at 31.52 s. That frame is the retransmission the CSV path is
documented to count twice, so the container path is the CSV result with its one
known defect repaired.

## Transport losses and duration

Sequence-number continuity is not checked by
`tools/extract_report36_opus.py`. Checked separately on the raw records:

| Capture | Received | Lost | Duplicated |
| --- | ---: | ---: | ---: |
| capture-01 variant A | 4,757 | 24 (0.50 %) | 0 |
| capture-01 variant B | 2,434 | 7 (0.29 %) | 0 |
| capture-02 variant A | 4,861 | 21 (0.43 %) | 1 |
| capture-mic-01 variant B, run 1 | 708 | 55 (7.21 %) | 0 |
| capture-mic-01 variant B, run 2 | 4,290 | 160 (3.60 %) | 0 |
| capture-mic-01 variant A | 2,408 | 231 (8.75 %) | 0 |
| capture-mic-01 uplink, Report `0x31` type 2 | 6,481 | 1,840 (22.1 %) | 0 |
| capture-mic-02 variant A | 3,049 | 90 (2.9 %) | 0 |
| capture-mic-02 uplink, Report `0x31` type 2 | 3,109 | 269 (8.0 %) | 0 |

Single dropped packets are a property of the over-the-air capture method, not
of a particular export. No pop or click is measurable at any loss boundary in
captures 01 and 02.

Loss rate is a property of the individual recording, not a constant.
Capture-mic-01 loses roughly ten times as many packets as captures 01 and 02
and fails CRC on 6.2 % of frames against 0.34 % for capture 02. Gaps stay
short: 179 of its 204 variant A gaps are a single packet and the longest is 3.
Quantify loss per capture rather than assuming the sub-1 % figures above.

Loss is also not symmetric between directions. In capture-mic-01 the uplink
loses 22.1 % of packets and fails CRC on 16.7 % of frames, roughly three times
the downlink rate in the same container. Capture-mic-02 is a much cleaner
recording, 8.0 % uplink loss against 2.9 % downlink, but the same
uplink-to-downlink ratio persists. Analyzer placement favouring the console's
transmissions over the controller's would explain it, but that is a hypothesis
and has not been tested.

`tools/extract_report36_from_cfax.py` reports received, lost and retransmitted
counts per segment. `tools/extract_report36_opus.py` still does not check
sequence continuity, so a CSV-derived result needs the check done separately.

Capture 02 also contains one Bluetooth retransmission captured twice: frames
46954 and 46963 are byte-identical across all 398 bytes, sequence number and
CRC included. The extractor counts it as a distinct packet.

Because `duration_seconds` is derived from the packet count, lost packets are
concatenated without a marker and the recorded duration understates the
recording: 71.91 s against 72.22 s elapsed for capture 01, and 48.61 s against
48.81 s for capture 02. Do not use these figures for timing analysis.

For capture-mic-01 the understatement is larger and only partly measurable:
74.06 s recorded against at least 78.52 s of on-air span inside its segments,
plus two breaks between segments whose length cannot be recovered, because the
audio sequence counter is 8 bit and both jumps exceed it.
