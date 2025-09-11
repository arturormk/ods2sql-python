## 0009 — Output Contract (stdout vs stderr) & Versioning

**Status:** Accepted
**Date:** 2025-09-10

### Context

The main use case pipes SQL into `sqlite3`. Noise on stdout would corrupt the stream. We also need a compatibility story.

### Decision

* Emit **only SQL** on stdout. All diagnostics/warnings go to stderr.
* Provide `--list` for discovery to stderr.
* Add `--version` and set initial version **0.1.0** (SemVer).
* Backward‑compatible marker aliases preserved; breaking changes will bump the major version.

### Consequences

* Pipe‑safe UX and clear CLI stability expectations.

### Alternatives

* Mixed stdout logging (unsafe), or environment-driven verbosity (unnecessary complexity).
