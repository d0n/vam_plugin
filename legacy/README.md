# Legacy plugin sources

Kept for reference only: not built, checked or packaged, and paths inside them may no longer
resolve.

- `v0.4/`: Session, Person and Person2 plugins of AIBody 0.3/0.4 (protocol v1, character slots
  `person1`/`person2`). Buildable tree: tag `v0.4.0-session`.
- `v0.5/`: Client and Companion plugins of AIBody 0.5.0 (`d0n.AIBody.2.var`, protocol v2, bridge
  through JSONStorableString inbox/outbox params between two plugins). Also its
  `tools/assemble_plugins.py` and `packaging/AIBody.json`. Buildable tree: tag `v0.5.0`.

Since 0.6.0 the shipped plugin is the single `src/AIBody/AIBody.cslist` (see the README).
Deferred features of the old layouts are listed in `docs/BACKLOG.md`.
