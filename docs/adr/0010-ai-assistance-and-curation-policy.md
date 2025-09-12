# 0010 – AI Assistance and Curation Policy

Status: Accepted  
Date: 2025-09-12  
Decision Makers: Software Curator (Arturo R. Montesinos)  
Supersedes: —  
Superseded by: —

## Context
The codebase was produced with extensive AI assistance. While large language models (LLMs) accelerated draft generation of parsing logic, CLI scaffolding, tests, and documentation, raw AI output can contain hidden defects, unclear intent, or licensing ambiguities. The project’s positioning emphasizes the role of a **Software Curator**: a human who selects, validates, edits, and integrates AI-generated artifacts while assuming final responsibility.

Problems to address:
- Transparency: Make provenance and curation explicit to users and contributors.
- Accountability: Ensure a human owns licensing, security posture, and release quality.
- Repeatability: Define a review standard so future AI contributions meet the same bar.
- Traceability: Link behavioral expectations (tests/ADRs) to curated decisions rather than opaque AI output.

## Decision
Adopt a formal AI Curation Policy:
1. Attribution: README will include a section stating the code was AI-generated under human curation (this ADR ID referenced).
2. Ownership: Copyright, authorship, and licensing attribution remain solely with the human curator (and future human contributors), not the AI system.
3. Review Gate: No AI-generated change is merged without:
   - Passing test suite (including new/updated tests for changed behavior).
   - Compliance with style/tooling (ruff, mypy where applied).
   - An explicit diff sanity review by the curator.
4. Provenance Tagging: Commits MAY include a conventional footer `Curated-By: <name>` for major AI-assisted batches (optional).
5. Licensing Safety: Only AI output validated to avoid non-permissive license contamination is accepted (pure-stdlib solution preferred where feasible).
6. Documentation Alignment: Significant behavior changes must update or add an ADR before—or in the same commit as—the code, ensuring intent is recorded first ("docs as runway").
7. Test-First Preference: For non-trivial new behavior, a minimal failing test SHOULD precede the AI-generated implementation.

## Consequences
Positive:
- Users understand provenance and accountability, increasing trust.
- Maintains legal clarity—no ambiguous machine authorship claims.
- Creates a reproducible pattern for future AI-augmented enhancements.
- Encourages disciplined, test-backed evolution rather than ad hoc prompting.

Trade-offs / Risks:
- Additional friction (must write/update ADRs + tests) may slow rapid prototyping.
- Curator review becomes a potential bottleneck.
- Explicit attribution may invite scrutiny of AI quality; mitigated by strong tests.

Follow-ups:
- Add README "Attribution & Curation" section referencing this ADR.
- Optionally add a `CITATION.cff` / `AUTHORS` file clarifying human ownership.
- Consider a pre-commit hook that blocks commits touching `src/` without corresponding ADR/t test changes (future).
