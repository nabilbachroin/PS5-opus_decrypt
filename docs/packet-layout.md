# DualSense Report 0x36 Opus Layout

Status: **Confirmed for capture 01** on 2026-09-08.

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

Capture 02 remains **Candidate** until its `.cfax` format is inspected and the
same framing and decode checks are repeated.
