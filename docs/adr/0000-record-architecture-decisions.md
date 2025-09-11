## 0000 — Record Architecture Decisions

**Status:** Accepted
**Date:** 2025-09-10

### Context

Small tools drift without a memory of *why* choices were made. ADRs capture trade‑offs so future contributors (including future-you) can reason about changes without guesswork.

### Decision

Adopt short, numbered ADRs under `docs/adr/`. Use a concise template: Context, Decision, Consequences, Alternatives.

### Consequences

* Faster onboarding; safer refactors.
* Minor upfront writing cost per change.
* Clear trail for releases.

### Alternatives

* Implicit knowledge in PRs/chats (risk of loss).
* One monolithic DESIGN.md (becomes stale).
