# Security and Privacy

## 1. Trust boundaries

Components:

- Hermes process;
- plugin code;
- local SQLite metrics store;
- Hermes dashboard/auth layer;
- OpenRouter Jev API;
- user's configured Hermes tools/apps.

The plugin must minimize what crosses each boundary.

## 2. Jev request data

Tool routing requires semantic access to the current user request. The router may send a bounded/redacted representation of the fresh turn to Jev.

Rules:

- send only what is required for the route decision;
- skip oversized requests rather than truncate away suffix requirements;
- do not send conversation history, tool results, local files or memory content for v1 routing;
- redact structured JSON secrets, environment assignments, quoted multiword values, URL credentials and recognized token shapes before transmission;
- skip transmission when recognizable sensitive content cannot be confidently redacted (for example private-key blocks, malformed quotes or ambiguous password prose);
- document that the Jev provider is an external cloud service.

Empty, image/file/audio-bearing latest user messages and short contextual follow-ups leave all tools available. The router never falls back to an older text request or sends history to infer a continuation. Redaction is a conservative heuristic, not a guarantee that arbitrary private data can be identified.

### Independent compaction boundary

Compaction starts OFF. `compaction_allow_external` also defaults to false, including upgrades with previously saved compaction ON/SHADOW modes. Both ON and SHADOW are blocked from sending compaction data until the operator explicitly allows it. `/jev compaction allow-external` permits paid OpenRouter decisions; `/jev compaction deny-external` revokes permission. Selecting a mode from the dashboard never grants this separate permission.

When allowed, compaction can send redacted historical conversation excerpts (including system/user/assistant text), a bounded memory-provider excerpt, tool call identifiers and metadata, and head/tail tool-output previews. This is broader than routing's latest-user-only state. Preview boundaries are applied after redaction; uncertain sensitive formats abort the Jev pass. Global routing OFF suspends all Jev calls.

Jev confidence cannot prove unseen middle facts redundant. Python requires a later valid result from the same tool with exactly the same complete content and keeps the newest copy ineligible for archiving. Unique outputs and recognized JSON/error payloads stay verbatim in the Jev pass. A normal Hermes summary may still run when this pass cannot meet the context budget; its provider/data behavior is governed by Hermes.

Archive recovery uses the host-bound session namespace and the private integrity-checked index, independent of the reference's transcript role. Only host-confirmed compression continuations can inherit an ancestor's references; unrelated chats, branches and delegates cannot authorize them by quoting labels. Normal summarization restores owned references deterministically for discovery. Cloned/resumed engines must be bound to their actual session by Hermes.

Archives are limited to 512 MiB per profile; capacity exhaustion refuses new archives and preserves existing recovery. Ordinary partial-batch failures roll back new raw files. New directory ancestors and leaf files/indexes are fsynced. Live archives are never deleted automatically; after session retirement, operators may remove that session's archive namespace locally only when its recovery is no longer needed. Power-loss durability and archive publication coordinated with a host commit remain live release gates; filesystem fsync tests are not proof against every storage failure.

## 3. Credentials

- Never accept or print API keys in slash commands.
- Never put secrets in plugin config intended for dashboard display.
- Prefer Hermes secret/credential mechanisms.
- Prefer a dedicated OpenRouter Jev key with its own budget/limit.
- Never include credentials in logs, SQLite, exceptions, status output, HTTP query parameters or dashboard payloads.
- Never automatically copy a generic provider key into another file.

## 4. Telemetry privacy

Persist metadata only. See `TELEMETRY.md`.

Forbidden fields include:

- prompt/state text;
- tool call args/results;
- filenames or paths derived from private tasks;
- URLs from private browsing/app data;
- memory text;
- chat IDs/user IDs;
- secrets.

Opaque local correlation keys are sufficient.

## 5. Dashboard security

The dashboard extension must use Hermes' dashboard plugin/auth architecture. It must not independently bind an unauthenticated public HTTP server.

Backend routes:

- return metadata only;
- validate mode/settings writes;
- use POST/PUT for mutation;
- rely on Hermes' authenticated dashboard context;
- preserve the selected Hermes management profile explicitly on plugin API requests;
- never provide a credential-read endpoint;
- avoid destructive metrics-clear actions without explicit confirmation semantics.

Arbitrary local primary model/provider/API identifiers are kept out of benchmark dashboard payloads because custom identifiers can contain private deployment names or filesystem paths.

## 6. Fail-open vs fail-closed

For **agent availability**, Jev routing fails open: normal Hermes continues.

For **secrets and dashboard exposure**, fail closed: do not expose data because a config check failed.

This distinction must be preserved.

## 7. External actions

Jev selects a tool family only. It does not authorize external actions. All normal Hermes tool permissions/approval mechanisms remain authoritative.

The Hermes deferred-tool bridge remains available during Jev family filtering because the current public middleware API cannot safely re-scope its underlying catalog after assembly. Jev filtering therefore narrows known eager schemas but is never an authorization boundary.

## 8. Supply-chain/provenance

- Pin/reference upstream commits when copying code.
- Preserve MIT notices.
- Minimize new dependencies.
- CI must include dependency and secret scanning where available.
- Do not download/execute upstream install scripts in CI merely to test this plugin.

## 9. Logging

Normal logs may include:

- decision family;
- confidence;
- latency;
- normalized reason/error code;
- mode.

Normal logs must not include request state, Authorization headers or raw upstream response bodies that could echo user content.

Debug content logging, if ever introduced, must be explicit opt-in, local, time-bounded, clearly warned, and is outside v1.

## 10. Public repository policy

This repository must remain safe to make public at all times. Synthetic fixtures only. See `SOURCE_OF_TRUTH.md` public-repository hygiene.

## 11. Telemetry corruption and recovery

Telemetry is not allowed to become an agent availability dependency.

If the SQLite metrics store is unreadable or corrupt:

- routing/agent execution continues through existing fail-open boundaries;
- dashboard telemetry may report degraded/unavailable;
- the plugin does not silently delete or replace the database;
- `hermes jev doctor` reports the local failure without exposing paths in dashboard payloads;
- explicit `hermes jev doctor --repair-db` may quarantine the corrupt database and create a clean schema.

Repair is limited to this plugin's local metrics files. It does not modify Hermes conversations, provider credentials, config, or other plugins.

**Concurrency precondition:** database repair must be run only when no other Hermes gateway, dashboard, agent, or automation process is actively using the same profile's telemetry database. SQLite recovery renames the database and any WAL/SHM companions; racing a concurrent writer would be unsafe. Stop the other Hermes processes for that profile, run the repair from a one-off CLI process, verify `hermes jev doctor`, then restart normal services. The repair command is intentionally explicit and is never invoked automatically by routing or dashboard code.

## 12. Public repository CI scan

CI runs `scripts/public_repo_scan.py` on every supported Python matrix job.

The scan blocks known high-risk public-repository patterns including:

- private-key material;
- provider/repository/chat token shapes covered by the scanner;
- non-placeholder credential assignments;
- absolute Linux/macOS/Windows user-home paths;
- non-example email addresses;
- non-documentation IPv4 addresses.

The scanner prints only the file and rule identifier, never the matched value.

This scanner supplements, rather than replaces, manual release review and GitHub's own repository security controls.
