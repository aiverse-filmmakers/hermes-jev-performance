(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  const registry = window.__HERMES_PLUGINS__;
  if (!SDK || !registry) {
    console.warn("[hermes-jev-performance] Hermes dashboard SDK unavailable");
    return;
  }

  const React = SDK.React;
  const hooks = SDK.hooks;
  const C = SDK.components;
  const h = React.createElement;
  const API = "/api/plugins/hermes-jev-performance";

  function n(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function fmtMs(value) {
    const num = n(value);
    if (num === null) return "No data";
    if (num >= 1000) return (num / 1000).toFixed(num >= 10000 ? 1 : 2) + "s";
    return Math.round(num) + "ms";
  }

  function fmtPct(value) {
    const num = n(value);
    return num === null ? "No data" : Math.round(num * 100) + "%";
  }

  function fmtCost(value) {
    const num = n(value);
    if (num === null) return "No data";
    if (num === 0) return "$0";
    if (num < 0.001) return "$" + num.toFixed(6);
    return "$" + num.toFixed(4);
  }

  function fmtInt(value) {
    const num = n(value);
    return num === null ? "0" : Math.round(num).toLocaleString();
  }

  function fmtSignedPct(value) {
    const num = n(value);
    return num === null ? "No data" : (num >= 0 ? "+" : "") + num.toFixed(1) + "%";
  }

  function fmtFloat(value, digits) {
    const num = n(value);
    return num === null ? "No data" : num.toFixed(digits == null ? 2 : digits);
  }

  function fmtDate(seconds) {
    const num = n(seconds);
    if (num === null) return "Unknown";
    try {
      return new Date(num * 1000).toLocaleString();
    } catch (_) {
      return "Unknown";
    }
  }

  function badgeClass(state) {
    return "jv-badge jv-badge-" + String(state || "unknown").toLowerCase();
  }

  function MetricCard(props) {
    return h(C.Card, { className: "jv-metric-card" },
      h(C.CardContent, { className: "jv-metric-content" },
        h("div", { className: "jv-metric-label" }, props.label),
        h("div", { className: "jv-metric-value" }, props.value),
        h("div", { className: "jv-metric-note" }, props.note || "")
      )
    );
  }

  function ModeControl(props) {
    const modes = ["off", "shadow", "on"];
    return h("div", { className: "jv-mode-wrap" },
      h("div", { className: "jv-section-label" }, "Routing mode"),
      h("div", { className: "jv-mode-control", role: "group", "aria-label": "Jev routing mode" },
        modes.map(function (mode) {
          const active = props.mode === mode;
          return h("button", {
            key: mode,
            type: "button",
            className: "jv-mode-button" + (active ? " is-active" : ""),
            disabled: props.busy,
            "aria-pressed": active,
            onClick: function () { props.onChange(mode); }
          }, mode.toUpperCase());
        })
      ),
      h("p", { className: "jv-mode-help" },
        props.mode === "off"
          ? "Jev is bypassed. Hermes runs normally and baseline turn telemetry can still be recorded."
          : props.mode === "shadow"
            ? "Jev decides once per turn, but Hermes tools are not changed."
            : "Confident single-family decisions may narrow known tool families. Unsafe or mixed decisions fail open."
      )
    );
  }

  function RangeControl(props) {
    const ranges = [
      { hours: 24, label: "24H" },
      { hours: 168, label: "7D" },
      { hours: 720, label: "30D" }
    ];
    return h("div", { className: "jv-range-control", role: "group", "aria-label": "Analytics period" },
      ranges.map(function (item) {
        return h("button", {
          key: item.hours,
          type: "button",
          className: "jv-range-button" + (props.hours === item.hours ? " is-active" : ""),
          "aria-pressed": props.hours === item.hours,
          onClick: function () { props.onChange(item.hours); }
        }, item.label);
      })
    );
  }

  function StatusPanel(props) {
    const data = props.data;
    const telemetry = data.telemetry || {};
    const summary = data.summary_24h || {};
    return h(C.Card, { className: "jv-status-card" },
      h(C.CardHeader, { className: "jv-card-header" },
        h("div", null,
          h(C.CardTitle, { className: "jv-card-title" }, "Live status"),
          h("p", { className: "jv-card-subtitle" }, "Current Hermes Jev configuration and local metrics health.")
        ),
        h("div", { className: "jv-status-badges" },
          h("span", { className: badgeClass(data.mode) }, String(data.mode || "unknown").toUpperCase()),
          h("span", { className: badgeClass(telemetry.database_state) },
            telemetry.database_state === "ready" ? "METRICS READY" :
            telemetry.database_state === "empty" ? "NO DATA YET" : "METRICS DEGRADED"
          )
        )
      ),
      h(C.CardContent, { className: "jv-status-content" },
        h(ModeControl, {
          mode: data.mode,
          busy: props.busy,
          onChange: props.onModeChange
        }),
        h("div", { className: "jv-config-grid" },
          h("div", null, h("span", null, "Jev model"), h("strong", null, data.model || "unknown")),
          h("div", null, h("span", null, "Provider"), h("strong", null, data.provider || "unknown")),
          h("div", null, h("span", null, "Confidence gate"), h("strong", null, fmtPct(data.min_confidence))),
          h("div", null, h("span", null, "Timeout"), h("strong", null, fmtMs((n(data.timeout_seconds) || 0) * 1000))),
          h("div", null, h("span", null, "Reply notice"), h("strong", null, data.notice ? "On" : "Off")),
          h("div", null, h("span", null, "24h turns"), h("strong", null, fmtInt(summary.turns)))
        )
      )
    );
  }

  function DistributionBars(props) {
    const items = Array.isArray(props.items) ? props.items : [];
    if (!items.length) {
      return h("div", { className: "jv-empty" }, "No data in this period.");
    }
    const max = Math.max.apply(null, items.map(function (item) { return Number(item.count || 0); }).concat([1]));
    return h("div", { className: "jv-bars" },
      items.map(function (item) {
        const value = Number(item.count || 0);
        const pct = Math.max(2, Math.min(100, (value / max) * 100));
        return h("div", { className: "jv-bar-row", key: String(item[props.nameKey]) },
          h("div", { className: "jv-bar-meta" },
            h("span", null, String(item[props.nameKey] || "unknown")),
            h("strong", null, fmtInt(value))
          ),
          h("div", { className: "jv-bar-track" },
            h("div", { className: "jv-bar-fill", style: { width: pct + "%" } })
          )
        );
      })
    );
  }

  function Sparkline(props) {
    const rows = Array.isArray(props.rows) ? props.rows : [];
    const points = [];
    rows.forEach(function (row, index) {
      const value = props.getValue(row);
      if (n(value) !== null) points.push({ index: index, value: Number(value) });
    });
    if (points.length < 2) {
      return h("div", { className: "jv-spark-empty" }, "Not enough samples");
    }
    const values = points.map(function (point) { return point.value; });
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const span = max - min || 1;
    const width = 100;
    const height = 34;
    const lastIndex = Math.max(1, rows.length - 1);
    const polyline = points.map(function (point) {
      const x = (point.index / lastIndex) * width;
      const y = height - (((point.value - min) / span) * (height - 4)) - 2;
      return x.toFixed(2) + "," + y.toFixed(2);
    }).join(" ");
    return h("svg", {
      className: "jv-spark",
      viewBox: "0 0 100 34",
      preserveAspectRatio: "none",
      role: "img",
      "aria-label": props.label
    },
      h("polyline", {
        points: polyline,
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "2",
        vectorEffect: "non-scaling-stroke"
      })
    );
  }

  function TrendCard(props) {
    const rows = props.rows || [];
    let latest = null;
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const value = props.getValue(rows[i]);
      if (n(value) !== null) {
        latest = value;
        break;
      }
    }
    return h(C.Card, { className: "jv-trend-card" },
      h(C.CardContent, { className: "jv-trend-content" },
        h("div", { className: "jv-trend-head" },
          h("span", null, props.label),
          h("strong", null, latest == null ? "No data" : props.format(latest))
        ),
        h(Sparkline, {
          rows: rows,
          getValue: props.getValue,
          label: props.label + " trend"
        }),
        h("div", { className: "jv-trend-note" }, props.note)
      )
    );
  }

  function ModeComparison(props) {
    const rows = Array.isArray(props.rows) ? props.rows : [];
    return h("div", { className: "jv-table-wrap" },
      h("table", { className: "jv-table" },
        h("thead", null,
          h("tr", null,
            h("th", null, "Mode"),
            h("th", null, "Turns"),
            h("th", null, "Avg turn"),
            h("th", null, "Tools"),
            h("th", null, "LLM calls"),
            h("th", null, "Input"),
            h("th", null, "Jev latency"),
            h("th", null, "Jev cost")
          )
        ),
        h("tbody", null,
          rows.map(function (row) {
            return h("tr", { key: row.mode },
              h("td", null, h("span", { className: badgeClass(row.mode) }, String(row.mode).toUpperCase())),
              h("td", null, fmtInt(row.turns)),
              h("td", null, fmtMs(row.avg_duration_ms)),
              h("td", null, fmtFloat(row.avg_tool_calls, 2)),
              h("td", null, fmtFloat(row.avg_llm_requests, 2)),
              h("td", null, fmtInt(row.avg_input_tokens)),
              h("td", null, fmtMs(row.avg_jev_latency_ms)),
              h("td", null, fmtCost(row.total_jev_cost_usd))
            );
          })
        )
      )
    );
  }

  function benchmarkMetricValue(name, value) {
    if (value == null) return "No data";
    if (name === "hermes_duration_ms") return fmtMs(value);
    return fmtFloat(value, 2);
  }

  function ControlledBenchmark(props) {
    const runs = Array.isArray(props.runs) ? props.runs : [];
    if (!runs.length) {
      return h(C.Card, { className: "jv-panel-card" },
        h(C.CardContent, { className: "jv-benchmark-empty" },
          h("strong", null, "No controlled benchmark yet"),
          h("p", null,
            "Run ",
            h("code", null, "hermes jev benchmark"),
            " to preview the read-only suite, then add ",
            h("code", null, "--live"),
            " when you explicitly want to execute it."
          )
        )
      );
    }

    const run = runs[0];
    const comparison = run.comparison || {};
    const metrics = comparison.metrics || {};
    const rows = [
      ["hermes_duration_ms", "Hermes duration"],
      ["tool_calls", "Tool calls"],
      ["llm_requests", "LLM requests"],
      ["total_tokens", "Total tokens"],
      ["input_tokens", "Input tokens"],
      ["output_tokens", "Output tokens"]
    ];
    const env = run.environment || {};

    return h("div", { className: "jv-benchmark-wrap" },
      h(C.Card, { className: "jv-panel-card jv-benchmark-summary" },
        h(C.CardHeader, { className: "jv-card-header" },
          h("div", null,
            h(C.CardTitle, { className: "jv-card-title" }, "Latest controlled run"),
            h("p", { className: "jv-card-subtitle" },
              "Matched fixture + repeat pairs. Warm-ups are excluded from deltas."
            )
          ),
          h("div", { className: "jv-status-badges" },
            h("span", { className: "jv-badge jv-badge-ready" }, "CONTROLLED"),
            h("span", { className: badgeClass(run.status === "complete" ? "ready" : "shadow") },
              String(run.status || "unknown").toUpperCase()
            )
          )
        ),
        h(C.CardContent, null,
          h("div", { className: "jv-benchmark-meta" },
            h("div", null, h("span", null, "Matched pairs"), h("strong", null, fmtInt(comparison.matched_pairs))),
            h("div", null, h("span", null, "Fixtures"), h("strong", null, fmtInt(run.fixture_count))),
            h("div", null, h("span", null, "Repeats"), h("strong", null, fmtInt(run.repeats))),
            h("div", null, h("span", null, "Warmups"), h("strong", null, fmtInt(run.warmups))),
            h("div", null, h("span", null, "Failed samples"), h("strong", null, fmtInt(run.failed_samples))),
            h("div", null, h("span", null, "Hermes"), h("strong", null, env.hermes_version || "unavailable")),
            h("div", null, h("span", null, "Plugin"), h("strong", null, env.plugin_version || "unavailable")),
            h("div", null, h("span", null, "Jev model"), h("strong", null, env.jev_model || "unavailable"))
          ),
          h("div", { className: "jv-benchmark-actions" },
            h("button", {
              className: "jv-secondary-button",
              type: "button",
              onClick: function () { props.onExport(run.run_id); }
            }, "Export anonymized JSON")
          )
        )
      ),
      h("div", { className: "jv-table-wrap" },
        h("table", { className: "jv-table jv-benchmark-table" },
          h("thead", null,
            h("tr", null,
              h("th", null, "Metric"),
              h("th", null, "Pairs"),
              h("th", null, "OFF mean"),
              h("th", null, "ON mean"),
              h("th", null, "Absolute Δ"),
              h("th", null, "% change")
            )
          ),
          h("tbody", null,
            rows.map(function (entry) {
              const name = entry[0];
              const label = entry[1];
              const metric = metrics[name] || {};
              return h("tr", { key: name },
                h("td", null, label),
                h("td", null, fmtInt(metric.pairs)),
                h("td", null, benchmarkMetricValue(name, metric.off_mean)),
                h("td", null, benchmarkMetricValue(name, metric.on_mean)),
                h("td", null, benchmarkMetricValue(name, metric.absolute_delta)),
                h("td", null, fmtSignedPct(metric.percent_change))
              );
            })
          )
        )
      ),
      h("p", { className: "jv-section-copy" },
        "Negative change means ON used less time/resources for that metric; positive means more. ",
        "This table reports measured deltas only and does not score result quality."
      )
    );
  }

  function RecentDecisions(props) {
    const rows = Array.isArray(props.rows) ? props.rows : [];
    if (!rows.length) return h("div", { className: "jv-empty" }, "No Jev decisions in this period.");
    return h("div", { className: "jv-table-wrap" },
      h("table", { className: "jv-table jv-recent-table" },
        h("thead", null,
          h("tr", null,
            h("th", null, "Time"),
            h("th", null, "Mode"),
            h("th", null, "Route"),
            h("th", null, "Confidence"),
            h("th", null, "Latency"),
            h("th", null, "Applied"),
            h("th", null, "Reason"),
            h("th", null, "Cost")
          )
        ),
        h("tbody", null,
          rows.map(function (row, index) {
            return h("tr", { key: String(row.created_at) + "-" + index },
              h("td", null, fmtDate(row.created_at)),
              h("td", null, String(row.mode || "unknown").toUpperCase()),
              h("td", null, row.family || "fallback"),
              h("td", null, fmtPct(row.confidence)),
              h("td", null, fmtMs(row.latency_ms)),
              h("td", null, row.applied ? "Yes" : "No"),
              h("td", null, row.reason || "unknown"),
              h("td", null, fmtCost(row.cost_usd))
            );
          })
        )
      )
    );
  }

  function JevPage() {
    const dataPair = hooks.useState(null);
    const data = dataPair[0];
    const setData = dataPair[1];
    const analyticsPair = hooks.useState(null);
    const analytics = analyticsPair[0];
    const setAnalytics = analyticsPair[1];
    const benchmarkPair = hooks.useState(null);
    const benchmarks = benchmarkPair[0];
    const setBenchmarks = benchmarkPair[1];
    const hoursPair = hooks.useState(24);
    const hours = hoursPair[0];
    const setHours = hoursPair[1];
    const loadingPair = hooks.useState(true);
    const loading = loadingPair[0];
    const setLoading = loadingPair[1];
    const busyPair = hooks.useState(false);
    const busy = busyPair[0];
    const setBusy = busyPair[1];
    const errorPair = hooks.useState(null);
    const error = errorPair[0];
    const setError = errorPair[1];
    const feedbackPair = hooks.useState(null);
    const feedback = feedbackPair[0];
    const setFeedback = feedbackPair[1];

    const load = hooks.useCallback(function (quiet) {
      if (!quiet) setLoading(true);
      return Promise.all([
        SDK.fetchJSON(API + "/status"),
        SDK.fetchJSON(API + "/analytics?hours=" + hours + "&limit=30"),
        SDK.fetchJSON(API + "/benchmarks?limit=10")
      ])
        .then(function (payloads) {
          setData(payloads[0]);
          setAnalytics(payloads[1]);
          setBenchmarks(payloads[2]);
          setError(null);
        })
        .catch(function (err) {
          setError(String(err && err.message ? err.message : err));
        })
        .finally(function () {
          if (!quiet) setLoading(false);
        });
    }, [hours]);

    hooks.useEffect(function () {
      load(false);
      const id = window.setInterval(function () { load(true); }, 15000);
      return function () { window.clearInterval(id); };
    }, [load]);

    function exportBenchmark(runId) {
      SDK.fetchJSON(API + "/benchmarks/" + encodeURIComponent(runId) + "/export")
        .then(function (payload) {
          const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = "hermes-jev-benchmark-" + runId + ".json";
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
          setFeedback("Anonymized benchmark JSON exported.");
        })
        .catch(function (err) {
          setError(String(err && err.message ? err.message : err));
        });
    }

    function changeMode(mode) {
      if (!data || mode === data.mode || busy) return;
      setBusy(true);
      setFeedback(null);
      SDK.fetchJSON(API + "/mode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: mode })
      })
        .then(function (result) {
          if (!result || result.mode !== mode) {
            throw new Error("Mode read-back did not match requested value");
          }
          setFeedback("Mode changed to " + mode.toUpperCase() + ".");
          return load(true);
        })
        .catch(function (err) {
          setError(String(err && err.message ? err.message : err));
        })
        .finally(function () {
          setBusy(false);
        });
    }

    if (loading && !data) {
      return h("div", { className: "jv-page" },
        h("div", { className: "jv-loading" },
          h("div", { className: "jv-spinner", "aria-hidden": "true" }),
          h("span", null, "Loading Jev performance data…")
        )
      );
    }

    if (!data) {
      return h("div", { className: "jv-page" },
        h(C.Card, { className: "jv-error-card" },
          h(C.CardContent, { className: "jv-error-content" },
            h("strong", null, "Jev dashboard unavailable"),
            h("p", null, error || "The dashboard backend could not be reached."),
            h("button", { className: "jv-secondary-button", onClick: function () { load(false); } }, "Retry")
          )
        )
      );
    }

    const summary = data.summary_24h || {};
    const appliedPct = n(summary.decisions) && summary.decisions > 0
      ? summary.applied / summary.decisions
      : null;
    const routeRows = analytics && analytics.routes ? analytics.routes : [];
    const reasonRows = analytics && analytics.reasons ? analytics.reasons : [];
    const seriesRows = analytics && analytics.series ? analytics.series : [];
    const comparisonRows = analytics && analytics.comparison ? analytics.comparison : [];
    const recentRows = analytics && analytics.recent ? analytics.recent : [];

    return h("div", { className: "jv-page" },
      h("section", { className: "jv-hero" },
        h("div", null,
          h("div", { className: "jv-kicker" }, "HERMES · JEV"),
          h("h1", null, "Jev Performance"),
          h("p", null,
            "See what Jev is deciding, how long it takes, and how Hermes behaves around it. ",
            "Organic mode comparisons stay observational; controlled matched runs are shown separately below."
          )
        ),
        h("div", { className: "jv-hero-actions" },
          h("span", { className: "jv-version" }, data.plugin && data.plugin.version ? data.plugin.version : "plugin"),
          h("button", {
            className: "jv-secondary-button",
            disabled: loading,
            onClick: function () { load(false); }
          }, loading ? "Refreshing…" : "Refresh")
        )
      ),

      error && h("div", { className: "jv-alert jv-alert-error", role: "alert" }, error),
      feedback && h("div", { className: "jv-alert jv-alert-success", role: "status" }, feedback),

      h(StatusPanel, {
        data: data,
        busy: busy,
        onModeChange: changeMode
      }),

      h("section", { className: "jv-section" },
        h("div", { className: "jv-section-head" },
          h("div", null,
            h("div", { className: "jv-section-label" }, "Last 24 hours"),
            h("h2", null, "Performance snapshot")
          ),
          h("span", { className: "jv-observational" }, "OBSERVATIONAL")
        ),
        h("div", { className: "jv-metric-grid" },
          h(MetricCard, {
            label: "Jev decision latency",
            value: fmtMs(summary.avg_jev_latency_ms),
            note: "Average decision round-trip"
          }),
          h(MetricCard, {
            label: "Jev confidence",
            value: fmtPct(summary.avg_confidence),
            note: "Average provider-returned confidence"
          }),
          h(MetricCard, {
            label: "Jev cost",
            value: fmtCost(summary.total_jev_cost_usd),
            note: "Provider-reported total"
          }),
          h(MetricCard, {
            label: "Routes applied",
            value: fmtPct(appliedPct),
            note: fmtInt(summary.applied) + " of " + fmtInt(summary.decisions) + " decisions"
          }),
          h(MetricCard, {
            label: "Hermes turn time",
            value: fmtMs(summary.avg_turn_duration_ms),
            note: "Average end-to-end observed turn"
          }),
          h(MetricCard, {
            label: "Tool calls / turn",
            value: fmtFloat(summary.avg_tool_calls, 2),
            note: "Average observed Hermes tool calls"
          })
        )
      ),

      h("section", { className: "jv-section" },
        h("div", { className: "jv-section-head" },
          h("div", null,
            h("div", { className: "jv-section-label" }, "Explore telemetry"),
            h("h2", null, "Routing and Hermes trends")
          ),
          h(RangeControl, { hours: hours, onChange: setHours })
        ),
        h("div", { className: "jv-two-col" },
          h(C.Card, { className: "jv-panel-card" },
            h(C.CardHeader, null, h(C.CardTitle, { className: "jv-card-title" }, "Route distribution")),
            h(C.CardContent, null,
              h(DistributionBars, { items: routeRows, nameKey: "family" })
            )
          ),
          h(C.Card, { className: "jv-panel-card" },
            h(C.CardHeader, null, h(C.CardTitle, { className: "jv-card-title" }, "Routing outcomes")),
            h(C.CardContent, null,
              h(DistributionBars, { items: reasonRows, nameKey: "reason" })
            )
          )
        ),

        h("div", { className: "jv-trend-grid" },
          h(TrendCard, {
            label: "Turn duration",
            rows: seriesRows,
            getValue: function (row) { return row.avg_duration_ms; },
            format: fmtMs,
            note: "Average Hermes turn duration by time bucket"
          }),
          h(TrendCard, {
            label: "Tool calls",
            rows: seriesRows,
            getValue: function (row) { return row.avg_tool_calls; },
            format: function (value) { return fmtFloat(value, 2); },
            note: "Average tool calls per turn"
          }),
          h(TrendCard, {
            label: "LLM requests",
            rows: seriesRows,
            getValue: function (row) { return row.avg_llm_requests; },
            format: function (value) { return fmtFloat(value, 2); },
            note: "Average provider requests per turn"
          }),
          h(TrendCard, {
            label: "Tokens",
            rows: seriesRows,
            getValue: function (row) {
              return Number(row.input_tokens || 0) + Number(row.output_tokens || 0);
            },
            format: fmtInt,
            note: "Input + output tokens per bucket"
          })
        )
      ),

      h("section", { className: "jv-section" },
        h("div", { className: "jv-section-head" },
          h("div", null,
            h("div", { className: "jv-section-label" }, "Controlled benchmark"),
            h("h2", null, "Matched OFF vs ON")
          ),
          h("span", { className: "jv-controlled-label" }, "MATCHED WORKLOADS")
        ),
        h("p", { className: "jv-section-copy" },
          "These results come only from explicit benchmark runs using the same fixture/repeat pairs under OFF and ON. ",
          "Warm-ups are excluded from the comparison."
        ),
        h(ControlledBenchmark, {
          runs: benchmarks && benchmarks.runs ? benchmarks.runs : [],
          onExport: exportBenchmark
        })
      ),

      h("section", { className: "jv-section" },
        h("div", { className: "jv-section-head" },
          h("div", null,
            h("div", { className: "jv-section-label" }, "Mode comparison"),
            h("h2", null, "OFF vs SHADOW vs ON")
          ),
          h("span", { className: "jv-observational" }, "NOT CAUSAL")
        ),
        h("p", { className: "jv-section-copy" },
          "These rows compare ordinary usage under each mode. Workloads are not matched, so differences cannot yet be attributed to Jev."
        ),
        h(ModeComparison, { rows: comparisonRows })
      ),

      h("section", { className: "jv-section" },
        h("div", { className: "jv-section-head" },
          h("div", null,
            h("div", { className: "jv-section-label" }, "Decision log"),
            h("h2", null, "Recent Jev decisions")
          ),
          h("span", { className: "jv-observational" }, "METADATA ONLY")
        ),
        h(RecentDecisions, { rows: recentRows })
      ),

      h("section", { className: "jv-footnote" },
        h("strong", null, "What this proves today"),
        h("p", null,
          "Organic mode data remains observational. Controlled benchmark rows use matched OFF/ON fixture pairs, ",
          "but the dashboard reports deltas rather than turning them into a quality or capability verdict."
        )
      )
    );
  }

  registry.register("hermes-jev-performance", JevPage);
})();