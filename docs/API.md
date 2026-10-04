# Backend API contract

API schema version: **1**. Plugin ID: `hermes-jev-performance`. Hermes mounts these routes at `/api/plugins/hermes-jev-performance`. The native Desktop panel calls `ctx.rest`; Hermes owns connection routing, profile routing, and authentication. No gateway token is requested by this plugin.

Every route accepts Hermes' optional `profile` query parameter. A named profile must match the host's effective request home; otherwise the response is 409, or 404 if it does not exist. Older hosts that cannot prove isolation reject the request. No route falls back to another named profile.

## Health and setup

`GET /health` makes no provider call and does not write settings. Example for a newly installed, writable backend:

```json
{
  "plugin_id": "hermes-jev-performance",
  "backend_version": "0.1.0-alpha.12",
  "api_schema_version": 1,
  "routing_mode": "off",
  "compaction_mode": "off",
  "credential_present": false,
  "context_engine": {"configured": null, "active": null, "restart_required": null},
  "capabilities": {"routing_mode_write": true, "compaction_mode_write": true, "context_engine_setup": false},
  "setup_issues": ["credential_missing", "context_engine_not_selected"],
  "conflicting_plugins": [],
  "compaction_suspended": true
}
```

Modes are exactly `off`, `shadow`, or `on`. Credential presence is a boolean; credentials themselves are never returned. `configured` is the saved context engine string or null. `active` and `restart_required` remain null because the dashboard cannot prove the running agent's engine from saved configuration.

Write capabilities are booleans obtained from the host's supported settings writer and managed-install/key checks. Unknown write support is false. Additional setup issues are `settings_read_only` and `plugin_conflict`. Conflict checking reports the known overlapping plugins `jev-router` and `jev-compaction-plus` if explicitly enabled and not disabled; it never changes them. This is a known-plugin check, not a promise to discover every third-party middleware implementation.

Automatic context-engine selection is unavailable (`context_engine_setup: false`). There is no arbitrary config-write endpoint or automatic engine-replacement button. Select the engine through Hermes' settings, restart the backend agent, and verify `/jev compaction status`.

## Mode writes

`PUT /mode` and `PUT /compaction` require exactly one string field:

```json
{"mode": "shadow"}
```

Extra/missing fields, lists, booleans, uppercase strings, and unknown values are rejected with 422 before any write. Both routes use Hermes' persistent plugin-settings writer and verify the saved mode by reading it back. Routing returns `{"ok": true, "previous_mode": "off", "mode": "shadow"}`; compaction returns `{"mode": "shadow", "engine_selection_required": true}`.

Compaction has its own saved mode, but global routing Off suspends Jev calls. Changing a saved compaction mode does not select the context engine or restart the agent. Shadow and On can make paid provider requests.

The Desktop reads health/status again to verify the displayed result. A write already dispatched before switching connections belongs to the original connection; switching does not reverse it. Delayed responses cannot update the newly selected connection's view.

## Metrics and benchmarks

| Request | Response contract |
|---|---|
| `GET /status` | Plugin ID/version, settings, configuration warnings, `telemetry` state, `summary_24h`, and `compaction` mode, suspension, warnings, and aggregate summary. |
| `GET /summary?hours=24` | Aggregate decisions/turns/applied/fallback counts, route counts, latency/confidence/cost, observed Hermes turn/tool/request/token metrics, database state, and telemetry schema version. |
| `GET /analytics?hours=24&limit=20` | `hours`, database state, `routes`, `reasons`, observational `comparison` by mode, bounded activity `series`, and safe `recent` decision metadata. |
| `GET /benchmarks?limit=5` | Database state and `runs`; each run has status, safe environment/methodology, sample/failure counts, and matched-pair `comparison.metrics`. |
| `GET /benchmarks/{run_id}/export` | Anonymized benchmark JSON; unknown run returns 404. No archive or conversation content. |

`hours` is bounded from 1 to 87600; analytics `limit` from 1 to 200; benchmark `limit` from 1 to 50. Existing response fields retain their meanings. Unavailable numerical measurements are null, not inferred zero. Empty count histories may be zero. Telemetry errors carry safe identifiers rather than raw exceptions. Estimated compaction token savings remain labeled estimates.

Ordinary mode comparisons are observational. Benchmark methodology `controlled_matched_benchmark` identifies measured matched runs; `synthetic_ci` is explicitly synthetic test data. Unknown methodology is labeled unverified. Valid sample pairs and failed runs must be reviewed before claiming improvement. API reads never launch benchmarks.

## Errors and host gates

- **401:** missing/invalid Hermes dashboard authentication.
- **403:** administrator-managed setting or denied action.
- **404:** absent/disabled plugin, unknown profile, or unknown benchmark.
- **409:** profile isolation or persisted mode could not be verified.
- **422:** malformed mode body or out-of-range query.
- **503:** safe service-unavailable message.

Hermes performs authentication and enabled-plugin admission before these handlers. The native host contract test mounts the delivered API using the actual Hermes mount function and checks unauthenticated 401, disabled-plugin 404, and real FastAPI body validation. No secrets, transcript text, archived tool output, or private file paths are exposed by these endpoints.
