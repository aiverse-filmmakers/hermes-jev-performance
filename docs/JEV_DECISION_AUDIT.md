# Jev decision audit

This audit applies the Jev rule from the project brief: Jev handles small, repeatable judgment calls; Python handles deterministic policy; Hermes still writes text, calls tools, and confirms irreversible actions.

## Highest-value opportunities

| Rank | Decision | Current owner and frequency | Jev shape | Safe threshold and fallback | Expected win |
|---|---|---|---|---|---|
| 1 | Which tool family should receive a fresh user turn? | `jevperf/routing.py:13`, once per fresh turn; Jev already owns this in shadow/on mode | Choice: `github`, `apps`, `web`, `terminal`, `files`, `memory`, `skills`, `media`, `none`, `multi`, `none_of_these` | ≥ configured confidence (default 0.70); below it leaves all tools available | Avoids unnecessary tool schemas and failed tool turns; measure locally rather than assume a fixed percentage |
| 2 | Whether an old tool output can leave active context | `jevperf/compaction.py:139`, at compaction; new feature | Yes/no per output | ≥ 0.90 and output ≥ 1,500 chars; otherwise retain or use normal Hermes compression | Shrinks active context while keeping exact recoverability |
| 3 | Whether compaction should be applied for this session | `jevperf/commands.py:137`, operator-controlled; no model call | Choice: `off`, `shadow`, `on` | Operator choice; `shadow` is the fallback for uncertainty | Collects evidence before changing transcript behavior |
| 4 | Whether a mixed request should be restricted to one tool family | `jevperf/routing.py:13`, once per fresh turn | Choice including `multi` and `none_of_these` | Never restrict `multi`/`none_of_these`; preserve all tools | Prevents routing from breaking multi-step tasks |
| 5 | Whether archived output retrieval is authorized | `jevperf/context_engine.py:74`, only when `jev_recover` is called | Fixed yes/no policy | Require an exact reference label in the current transcript; reject everything else | Prevents arbitrary archive reads |

## Full list

| Where | Decision | Current owner | Jev question | What remains with Hermes/Python |
|---|---|---|---|---|
| `jevperf/routing.py:13` | Tool family for the latest request | Jev choice | Choice above, always with `none_of_these` | Tool execution and all writes |
| `jevperf/routing.py:59` | Whether confidence is sufficient | Python threshold | No separate Jev call | Fail-open behavior |
| `jevperf/families.py:184` | Which schemas are known members of a family | Python exact/prefix rules | Not a Jev task | Unknown tools and deferred bridge stay available |
| `jevperf/compaction.py:139` | Archive one old result | Jev yes/no with head/tail preview and rulebook | Preserve exact facts, constraints, errors, configuration, and unresolved evidence; uncertainty means keep | Archive durability, transcript rewrite, and rollback |
| `jevperf/compaction.py:158` | Whether a compaction attempt is safe to publish | Python | Not a Jev task | Token budget, minimum reduction, deadline, archive completion |
| `jevperf/context_engine.py:74` | Whether a recovery reference may be read | Python | Not a Jev task | Exact-reference authorization and path confinement |
| `jevperf/compaction_config.py:32` | Which compaction mode/settings to use | Operator and validated config | Not a Jev task | Invalid settings disable compaction |
| `jevperf/benchmark.py` | Whether a benchmark sample is valid | Python fixture and metric rules | Not a Jev task | Read-only fixture validation and paired comparison |
| `jevperf/doctor.py` | Whether local installation is healthy | Python diagnostics | Not a Jev task | No network calls, no secret printing |
| `jevperf/dashboard_service.py` | Whether a setting write succeeded | Hermes settings writer plus read-back | Not a Jev task | Profile scoping and authenticated dashboard API |

Excluded deliberately: text generation, tool execution, secret handling, filesystem authorization, irreversible actions, fixed family matching, token arithmetic, and benchmark validity. Jev advises on relevance judgments; it is not an executor or security boundary.

## Actual Jev request for the top-ranked decision

```json
{
  "model": "typesafe/jev-1.13",
  "state": "<latest redacted user request only>",
  "questions": {
    "tool_family": {
      "type": "choice",
      "instructions": "Choose the single best tool-routing policy. Choose multi when more than one distinct tool family is genuinely required. Choose none when no tool is needed. Choose none_of_these when the categories do not fit or the evidence is insufficient.",
      "criteria": {
        "github": "Repository, issue, pull request, branch, release, or workflow work.",
        "apps": "Connected external app or service work.",
        "web": "Public web research or browser work.",
        "terminal": "Shell, process, package, or machine work.",
        "files": "Local file reading, searching, writing, or patching.",
        "memory": "Hermes memory retrieval or update.",
        "skills": "Skill discovery or management.",
        "media": "Image, audio, speech, or other media work.",
        "none": "No external tool is needed.",
        "multi": "Two or more distinct families are required.",
        "none_of_these": "No category fits or the evidence is insufficient."
      }
    }
  }
}
```

The request state is redacted and bounded before it leaves Hermes. The plugin stores only decision metadata; it does not persist prompts, tool inputs, output previews, or archive contents in telemetry.
