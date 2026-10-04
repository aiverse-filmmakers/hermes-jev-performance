# Server component installed

New installations start with routing and compaction **OFF**. This server package includes no visual dashboard bundle. A tiny hidden browser-loader shim exists only so Hermes can mount the authenticated plugin API used by the native Desktop panel.

Check the selected Hermes backend/profile:

```text
/jev status
/jev doctor
```

Add the Jev/OpenRouter credential through that backend's secure secret settings. Never paste it into chat. Choose `/jev shadow` only when you are ready for provider requests and possible charges. Shadow leaves routing unchanged while observing decisions.

Compaction starts OFF; enable it deliberately using the compaction guide. It requires selecting `context.engine: hermes-jev-performance`, restarting the agent and a separate `/jev compaction allow-external` opt-in. That opt-in permits paid OpenRouter calls with redacted conversation history, memory excerpts and complete redacted tool-output chunks, including in compaction Shadow. Older unique outputs can be archived when every complete redacted chunk passes the relevance threshold; uncertain output stays. `/jev compaction deny-external` blocks those transmissions again. Inspect `/jev compaction status` before any isolated trial.

The visual Jev Performance panel is installed separately on the computer running Hermes Desktop. When Hermes runs on a VPS, install this component on that VPS and the Desktop component locally.
