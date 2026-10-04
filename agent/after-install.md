# Server component installed

New installations start with routing and compaction **OFF**. This server package includes no visual dashboard bundle. A tiny hidden browser-loader shim exists only so Hermes can mount the authenticated plugin API used by the native Desktop panel.

Check the selected Hermes backend/profile:

```text
/jev status
/jev doctor
```

Add the Jev/OpenRouter credential through that backend's secure secret settings. Never paste it into chat. Choose `/jev shadow` only when you are ready for provider requests and possible charges. Shadow leaves routing unchanged while observing decisions.

Keep compaction OFF during routing evaluation. It requires selecting `context.engine: hermes-jev-performance`, restarting the agent and a separate `/jev compaction allow-external` opt-in. That opt-in permits paid OpenRouter calls with redacted conversation history, memory excerpts and tool previews, including in compaction Shadow. Only older outputs with a retained complete exact duplicate can be archived. `/jev compaction deny-external` blocks those transmissions again. Inspect `/jev compaction status` before any isolated trial.

The visual Jev Performance panel is installed separately on the computer running Hermes Desktop. When Hermes runs on a VPS, install this component on that VPS and the Desktop component locally.
