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

  function JevPage() {
    const statePair = hooks.useState(null);
    const data = statePair[0];
    const setData = statePair[1];
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
      return SDK.fetchJSON(API + "/status")
        .then(function (payload) {
          setData(payload);
          setError(null);
        })
        .catch(function (err) {
          setError(String(err && err.message ? err.message : err));
        })
        .finally(function () {
          if (!quiet) setLoading(false);
        });
    }, []);

    hooks.useEffect(function () {
      load(false);
      const id = window.setInterval(function () { load(true); }, 15000);
      return function () { window.clearInterval(id); };
    }, [load]);

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

    return h("div", { className: "jv-page" },
      h("section", { className: "jv-hero" },
        h("div", null,
          h("div", { className: "jv-kicker" }, "HERMES · JEV"),
          h("h1", null, "Jev Performance"),
          h("p", null,
            "See what Jev is deciding, how long it takes, and how Hermes behaves around it. ",
            "These are observational usage metrics until a controlled benchmark is run."
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
            value: n(summary.avg_tool_calls) === null ? "No data" : summary.avg_tool_calls.toFixed(2),
            note: "Average observed Hermes tool calls"
          })
        )
      ),

      h("section", { className: "jv-footnote" },
        h("strong", null, "What this proves today"),
        h("p", null,
          "The page reports real local telemetry. It does not yet claim Jev made Hermes faster. ",
          "Causal ON vs OFF benchmarking is a separate controlled phase."
        )
      )
    );
  }

  registry.register("hermes-jev-performance", JevPage);
})();