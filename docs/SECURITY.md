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
- cap length;
- do not send conversation history, tool results, local files or memory content for v1 routing;
- redact obvious credentials/tokens where practical before transmission;
- skip or fail open when content is clearly unsafe to transmit under configured policy;
- document that the Jev provider is an external cloud service.

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
