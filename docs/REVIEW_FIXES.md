# Review corrections and adoption gate

Source candidate: `0.1.0-alpha.10`. The review inspected `e6ab888762ec3ac3bfb8fd1b6e66a35cf9b27ff2` (`0.1.0-alpha.9`). Previous alpha.9 release ZIPs predate these changes. The source version is not a claim that a new release has been published or installed.

## Routing corrections

| Review finding | Corrected behavior |
|---|---|
| JSON/environment/quoted secret leaks | Structural JSON and quoted-value handling, broader token recognition and URL credential redaction. Recognizable uncertain formats skip external transmission in ON and SHADOW. |
| Mandatory eager tools removed | Skill loading/management, file primitives and memory remain available across every family, along with unknown tools and the deferred bridge. |
| Stale mid-turn/configuration cache | Cached decisions carry a hash of usable user state and routing mode/provider/model/confidence/timeout. Unchanged tool-loop requests reuse the decision; changed or unusable inputs restore all tools for the rest of that turn. A new turn gets a new decision. No additional Jev calls or untracked same-turn charges. |
| Image-only messages reuse old text | Latest user message is authoritative, including empty and multimodal content. No fallback to older messages or another API field. |
| Contextless follow-ups/truncated suffixes | Short continuations and oversized requests fail open. No conversation history is transmitted to guess the earlier task, and suffix instructions cannot be silently cut off. |
| Forced tool choice removed | Explicit named, required, none and unknown tool-choice forms bypass routing without a Jev call. |
| Empty injected cache discarded | An injected cache is retained using an explicit None check. |

Redaction remains a conservative heuristic. It cannot identify every possible secret or private fact. Prerequisite preservation and failing open can reduce schema savings; correctness takes precedence over a savings claim.

## Independent compaction corrections

- `compaction_allow_external` defaults false, even when an upgraded profile saved compaction ON/SHADOW. Mode selection does not grant the separate external-data permission. Routing and compaction remain OFF on new installs.
- Allowed compaction ON/SHADOW may send redacted conversation excerpts (system/user/assistant), bounded memory excerpts, tool identifiers/metadata and tool-output previews to OpenRouter. `/jev compaction allow-external` and `/jev compaction deny-external` control this boundary. Keep it blocked during routing evaluation.
- Only complete exact duplicates from the same tool are eligible. Python retains the newest valid copy, so identical preview ends cannot conceal a unique middle fact. Jev confidence alone never permits archiving unique evidence.
- Recognized JSON/nested error outputs stay verbatim. Memory-provider context is forwarded through the same privacy/budget checks.
- Recovery is authorized by the bound session and private integrity-checked archive index. It survives loss of the tool-role carrier, fresh engine instances and confirmed compression continuations. Foreign chats, branch/delegate edges and unbound engines fail closed. Normal summaries restore owned reference hints deterministically.
- Returned copies mark the unchanged contiguous tail using Hermes' carried-tail contract; modified originals remain searchable. Interior rows must not be tagged as a tail because that would rewind the wrong originals. Arbitrary noncontiguous carried-row integration is still a host API limitation; this change does not claim universal recall deduplication.
- Archive creation fsyncs new ancestor links and leaf/index files. Ordinary partial-batch failures roll back new raw output. A locked 512 MiB per-profile capacity refuses new archives without deleting existing recovery. Live archives have no automatic expiry; clean up only retired sessions whose references are no longer needed.
- Cooperative host cancellation/generation checks guard provider work, archive writes and publishing Jev diagnostics/counters/metrics. The final host transcript commit remains authoritative. Archive publication is not transactionally atomic with the separate host database: a process crash or cancellation after a completed archive write can still leave unpublished files, bounded by the capacity. This remains a production gate.
- Usage from each successful provider response is recorded immediately. Partial failures expose `known_*` costs/tokens while totals stay unknown when a later attempted request has no usage. These are known reported amounts, not estimates of failed-request billing.

## Evidence and remaining gates

Regression coverage uses synthetic data, mocked provider responses and isolated temporary profiles. Native tests execute real Hermes compression assembly and persistence, including summarize-then-recover, session resume/rotation, carried-tail recall and concurrent append. See [TESTING.md](TESTING.md#routing-and-compaction-review-corrections) for the executed commands and counts.

No production plugin was installed, enabled, replaced or switched. No paid provider call was made. Live routing accuracy, real research/file/media/publishing workflows, rendered Desktop/VPS behavior, installer provenance, storage power-loss behavior and archive publication coordinated with host commit remain unverified.

Adoption order: evaluate the server component in an isolated profile with the old router absent; approve a live routing Shadow trial deliberately; exercise complete workflows; replace the old router rather than stack both. Keep compaction OFF until its separate operational/evidence/privacy gates pass. These source fixes do not establish a verified production replacement.
