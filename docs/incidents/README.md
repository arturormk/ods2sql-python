# Curatorial Incident Log

Purpose: Capture non-trivial incidents that produce reusable lessons for software curation (especially AI-assisted code). Incidents are not bugs-for-bugs-sake; they must yield a guardrail, pattern, or policy refinement.

Inclusion criteria:
- CI/build failure with a root cause that could recur.
- Packaging/publishing pitfalls.
- Subtle data loss or contract issues prevented before release.
- Security or integrity risk averted.
- Governance/policy gap discovered & addressed.

Exclusions:
- Simple typos, obvious one-off mistakes, trivial refactors.

Each incident file:
- ID (sequential, `INC-XXXX`), Date (UTC), Status.
- Context / Trigger.
- Symptom (what failed & where observed).
- Root Cause (crisp, one paragraph max).
- Resolution (what changed + commit hash/tag).
- Prevention / Guardrail (new tests, hooks, policies, or rationale if none added).
- References (links to commits, PRs, ADRs, logs).
- Tags (comma-separated taxonomy: ci, packaging, release, governance, etc.).

Maintenance:
- Review quarterly: consolidate repeated patterns into a higher-level "Patterns & Anti-Patterns" doc.
- Close incidents once preventive controls are in place.

See `INC-0001-dynamic-version-resolution.md` for the format.
