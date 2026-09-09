# DualSense Report 0x36 Opus Layout

Status: **Confirmed** for capture 01 on 2026-09-08 and for capture 02 on
2026-09-09.

## Report framing

- Report length: 398 bytes.
- Report ID: `0x36` at offset 0.
- Bluetooth CRC-32: offsets 394..397, calculated over channel prefix `0xA2`
  followed by report bytes 0..393.
- Audio packet length: 200 bytes for every accepted Report `0x36` record.

## Audio variants

| Variant | Marker at 67..71 | Audio sequence | Length byte | Opus payload |
| --- | --- | ---: | ---: | --- |
| A | `91 05 6F 39 1F` | 73 | 75 (`C8`) | 76..275 |
| B | `91 06 7F 39 1F` | 74 | 76 (`C8`) | 77..276 |

The variants are successive phases of one session, not two concurrent streams.
Confirmed on capture 01: variant B covers frames 2301..36611 and variant A
covers frames 36627..104444, with a single changeover and no interleaving.
Variant B is 91.7 % exact silence packets and variant A is 0.0 %, so variant B
is the idle or warm-up phase and variant A carries the audio. A capture that
starts after the changeover contains variant A only and no silence packets;
capture 02 is such a capture. Besides the one extra header byte, the variants
differ at offsets 11, 68, 69, 72 and 277.

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

Inside the `.cfax` container each frame carries a 5-byte prefix
(`8f 01 44 00 a2`) ahead of the report ID. The trailing `a2` is the same
channel prefix used by the CRC-32 calculation above. CSV exports drop that
prefix and start at the report ID.

Capture 02 is **Confirmed** as of 2026-09-09, including a human listening
review.

## Transport losses and duration

Sequence-number continuity is not checked by
`tools/extract_report36_opus.py`. Checked separately on the raw records:

| Capture | Received | Lost | Duplicated |
| --- | ---: | ---: | ---: |
| capture-01 variant A | 4,757 | 24 (0.50 %) | 0 |
| capture-01 variant B | 2,434 | 7 (0.29 %) | 0 |
| capture-02 variant A | 4,861 | 21 (0.43 %) | 1 |

Single dropped packets are a property of the over-the-air capture method, not
of a particular export. No pop or click is measurable at any loss boundary.

Capture 02 also contains one Bluetooth retransmission captured twice: frames
46954 and 46963 are byte-identical across all 398 bytes, sequence number and
CRC included. The extractor counts it as a distinct packet.

Because `duration_seconds` is derived from the packet count, lost packets are
concatenated without a marker and the recorded duration understates the
recording: 71.91 s against 72.22 s elapsed for capture 01, and 48.61 s against
48.81 s for capture 02. Do not use these figures for timing analysis.
