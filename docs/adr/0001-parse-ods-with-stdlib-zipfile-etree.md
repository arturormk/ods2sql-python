## 0001 — Parse ODS with stdlib `zipfile` + `xml.etree`

**Status:** Accepted
**Date:** 2025-09-10

### Context

The tool must be a single-file drop‑in with no third‑party dependencies. LibreOffice `.ods` is a ZIP with `content.xml` (OpenDocument XML).

### Decision

Use `zipfile.ZipFile` to read `content.xml` and `xml.etree.ElementTree` to parse; handle `table:number-columns-repeated`, `table:number-rows-repeated`, and covered cells. Avoid SAX/third‑party libs.

### Consequences

* Zero deps, easy distribution.
* Slightly more XML boilerplate than `lxml`; acceptable.
* Behavior fully deterministic and portable.

### Alternatives

* `odfpy` / `lxml` (richer API; violates zero-deps).
* SAX (more complex state machine for little gain now).
