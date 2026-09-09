# Repository Instructions

This repository contains captured protocol data and derived audio evidence.

- Treat every file under `data/*/raw/` and `reference/` as immutable evidence.
- Never overwrite a raw file. Add a new capture directory when new evidence is
  received.
- Keep generated outputs under the matching capture's `results/` directory.
- Record SHA-256 hashes for raw inputs and important derived outputs.
- Label conclusions as Confirmed, Candidate, Historical, or Invalidated.
- Do not call a decode validated solely because a tool accepts it. Record the
  packet count, framing checks, codec parameters, decoder diagnostics, and an
  audio or hardware review when available.
- Preserve failed experiments with a dated explanation; do not silently reuse
  or relabel them as current results.
- Do not commit dependency caches, temporary work directories, or archived
  invalid extraction trees.
- Do not publish the repository or add a remote without explicit approval.

For Report `0x36`, read `docs/packet-layout.md` before changing extraction
offsets or assumptions.
