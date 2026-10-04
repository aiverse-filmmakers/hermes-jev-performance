# Recoverable Jev compaction

Jev can decide which older tool outputs no longer need to occupy the active context. It can archive unique completed logs, research results or diagnostics; outputs do not need to be duplicates. Kept content remains verbatim. Archived content is saved exactly in private profile storage and replaced by a reference the agent can read with `jev_recover`.

The plugin sends each candidate's complete redacted content in bounded chunks. Every chunk must meet the archive threshold (default 0.90). If one chunk is relevant or uncertain, the whole output stays. Outputs that cannot be assessed completely within request/deadline limits stay too. It never authorizes removal from a head/tail preview alone.

User/system instructions, recent complete exchanges, small outputs, recognized errors (including exit/return codes and stderr), multimodal results and invalid tool pairs are protected. Complete textual user/system constraints remain in the decision state; if that state exceeds the budget or contains nontext instructions, Jev falls back instead of silently dropping constraints. Tool arguments are not sent. Redaction is heuristic: ordinary private business data can still be transmitted.

## Enable it on the intended backend/profile

1. Install the Server component and run `/jev doctor`. Configure the Jev/OpenRouter credential through the backend's secure credential settings.
2. In that Hermes profile's configuration, select the native engine and restart its agent/gateway:

   ```yaml
   context:
     engine: hermes-jev-performance
   ```

   If you already use another custom engine, record its setting for rollback before replacing it.
3. Run these commands in a chat served by that backend/profile:

   ```text
   /jev shadow
   /jev compaction allow-external
   /jev compaction shadow
   /jev compaction status
   ```

   Global Shadow leaves routing tools unchanged. Compaction Shadow makes relevance decisions and records estimated savings without replacing output or writing archives. Both modes can incur provider charges. The external-data consent permits redacted conversation/memory context and complete redacted tool-output chunks to go to OpenRouter.
4. To apply recoverable compaction, run `/jev compaction on`. Routing can stay in Shadow; selecting routing On is a separate choice. Compaction runs when Hermes requests compression, rather than on every turn.

Both modes start OFF on a new installation. That prevents installation from silently sending data or creating charges; it does not disable the feature permanently. Upgrades preserve saved modes and external consent. The old preview-size setting is no longer used: `compaction_chunk_chars` controls complete chunks, default 12,000 characters.

## Recovery, fallback and rollback

The agent receives a reference at each archived output and a `jev_recover` tool that supports pagination. It must recover missing evidence before quoting or relying on it, rather than rerunning the original tool. Recovery is authorized by the actual bound session and integrity-checked archive, including verified compression continuations. Quoting a reference from another chat cannot grant access. Reference discovery survives normal summarization and fresh/resumed engine instances in the tested Hermes contracts.

If Jev fails, is uncertain, exceeds its budget, cannot write an archive, or cannot reduce context enough, Hermes' normal compression is used. Its summarization policy remains Hermes' responsibility. A probability threshold is not a guarantee of perfect recall.

Run `/jev compaction off` to stop this feature, or `/jev compaction deny-external` to revoke its transmission consent. Global `/jev off` suspends all Jev calls. Restore the previous context engine and restart before removing the Server plugin. Preserve archive files while their recovery references are needed; they are never deleted automatically. At the 512 MiB profile capacity, new archives are refused while existing recovery remains available.

## Verified behavior and practical limits

Regression fixtures exercise research, file/configuration, media and publishing workflows with facts hidden in the middle of long outputs. Tests verify complete decision coverage, uncertain-chunk retention, protected messages/errors, exact paginated recovery and budget/provider/archive failures. Native Hermes tests exercise actual compression commit, database persistence, carried-tail recall, summaries, resume/session rotation beyond 64 generations and cancellation. Cancelled provider responses retain known billing when telemetry is enabled. Archive lock waits honor the attempt deadline; cancellation detected before plugin publication removes only the new unpublished archives.

The offline replay demonstrates context reduction with critical-fact retention and exact recovery using labelled provider responses. It is not a measurement of live Jev accuracy, cost or speed. No Jev credential was available in the development process for a paid live trial. Use the [evaluation commands](TESTING.md#relevance-compaction-release) on a configured backend to measure your own workflows.

The archive filesystem and Hermes database use separate commits. A process crash, failed filesystem cleanup or interrupted host commit can leave unused durable archive files; they are bounded by the capacity. The tested host marks a contiguous carried suffix; arbitrary interior retained rows can still have duplicate recall representations. These are operational/integration limits, not evidence that raw archive bytes were deleted. Client Desktop/VPS installation and actual provider performance remain deployment-specific checks.
