# Hermes Jev Performance installed

New installs begin with routing **OFF** and compaction **OFF**. Existing saved settings are retained when updating.

Recommended checks:

```bash
hermes plugins doctor hermes-jev-performance --ci
hermes jev status
hermes jev doctor
```

To use Jev routing, add `OPENROUTER_JEV_API_TOKEN` (preferred) or an existing `OPENROUTER_API_KEY` through Hermes' secure credential settings on the backend. Never paste the key into chat.

When ready, `/jev shadow` sends Jev requests and may incur provider charges while leaving tool choices unchanged. Review the results before using `/jev on`.

Day-to-day controls:

```text
/jev status
/jev shadow
/jev on
/jev off
/jev stats
/jev doctor
/jev compaction status
/jev compaction shadow
```

To disable the plugin itself:

```bash
hermes plugins disable hermes-jev-performance
```

Keep compaction OFF during routing evaluation. Experimental compaction requires native engine selection, restart, and the separate `/jev compaction allow-external` opt-in for paid OpenRouter transmission of redacted conversation history, memory excerpts and tool previews (including Shadow). `/jev compaction deny-external` blocks those transmissions. Only older outputs with a complete exact duplicate retained in context can be archived. Review `docs/REVIEW_FIXES.md` before an isolated trial.

Full install, upgrade, rollback and uninstall instructions are in `docs/INSTALL.md`.
