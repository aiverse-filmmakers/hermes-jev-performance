# Changelog

## 0.1.0-alpha.10 — 4 October 2026

Client evaluation release containing the routing/privacy review corrections. Routing and Jev compaction remain OFF on new installations. Existing routing settings are retained; compaction requires a new, separate external-data opt-in even when an older installation saved ON or SHADOW.

- Redact structured, quoted and environment-style credentials; skip external routing when sensitive content cannot be confidently redacted.
- Preserve skill, file and memory prerequisites, unknown tools and the deferred bridge.
- Invalidate obsolete turn decisions after instruction/configuration changes without another same-turn classification charge. Preserve all tools for forced choices, multimodal requests, incomplete follow-ups and oversized inputs.
- Restrict Jev compaction to complete exact duplicate tool outputs, protect recognized error payloads, and retain session-bound recovery through normal summaries and resume.
- Add external-data consent, bounded archives, partial-write rollback, cancellation checks, and partial provider-usage accounting.
- Update component packages, installation guides and the client handoff to use this version.

Validation: 266 Python unit/package tests, 11 Desktop behavior tests, 5 native loader/API/migration tests and 11 native compaction tests passed. Python 3.11–3.14 are checked in CI. Native reference and reproducible commands are in [TESTING.md](docs/TESTING.md).

This is an alpha, not a production certification. Live provider accuracy/savings, actual Desktop/VPS installation and appearance remain unverified. Jev compaction retains host transaction and recall integration limitations. See [STATUS.md](docs/STATUS.md) and [REVIEW_FIXES.md](docs/REVIEW_FIXES.md).

## 0.1.0-alpha.9 — 3 October 2026

Split Server, Desktop dashboard and combined local packages; corrected profile isolation, Desktop request lifecycle, native loading and deterministic packaging. This version predates the routing/privacy corrections above. Use alpha.10 for new evaluations.
