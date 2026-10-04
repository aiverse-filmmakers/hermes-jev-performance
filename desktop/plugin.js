import { host, useValue, Button } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PAGE = '/jev-performance'
const ID = 'hermes-jev-performance'
const MODES = ['off', 'shadow', 'on']
const OPTIONS = { timeoutMs: 8000 }
export const VERSION = '0.1.0-alpha.12'

const scopeKey = scope => JSON.stringify([scope.connectionId || 'local', scope.profile || 'default'])
const scopeLabel = scope => `${scope.connectionId || 'This computer'} · ${scope.profile || 'default'}`
const currentScope = () => ({ connectionId: host.state.connectionId.get(), profile: host.state.profile.get() })
const compatible = data => data?.health?.plugin_id === ID && data.health.api_schema_version === 1

export function recoveryMessage(reason) {
  const status = Number(reason?.status || reason?.statusCode) || Number(String(reason?.message || '').match(/\b(401|403|404|409|503)\b/)?.[1])
  if (status === 404 || /not found/i.test(reason?.message || '')) return 'The Server component is missing or disabled. Install Server only on this connection, enable it for this profile, then restart its dashboard service and retry.'
  if (status === 401) return 'The selected connection needs authentication. Reconnect in Hermes Desktop, then retry.'
  if (status === 403) return 'Hermes refused this action. Check the selected connection’s authentication and administrator-managed settings. Use the backend’s supported settings workflow.'
  if (status === 409) return 'Hermes could not verify the selected profile or saved setting. Check the profile, update Hermes if profile isolation is unsupported, then retry.'
  if (status === 503) return 'The Server component is present but unavailable. Run /jev doctor in a chat on this connection and check the backend service.'
  return 'Could not reach the selected Hermes backend. Check that your VPS or local Hermes service is running and reconnect in Hermes Desktop, then retry.'
}

// One session owns its scope and timers. Every post-await update verifies that
// scope again; a dispatched write still belongs to its original backend.
export function createPanelSession({ rest, scope, getScope, onChange, schedule = setTimeout, cancel = clearTimeout }) {
  let disposed = false
  let revision = 0
  let timer = null
  let reading = null
  let state = { scopeKey: scopeKey(scope), data: null, error: null, saving: false, feedback: null }
  const alive = () => !disposed && scopeKey(getScope()) === scopeKey(scope)
  const publish = patch => {
    if (!alive()) return
    state = { ...state, ...patch }
    onChange(state)
  }
  const readSnapshot = async () => {
    const [health, status, analytics, benchmarks] = await Promise.all([
      rest('/health', OPTIONS), rest('/status', OPTIONS),
      rest('/analytics?hours=24&limit=20', OPTIONS).catch(() => null),
      rest('/benchmarks?limit=5', OPTIONS).catch(() => null)
    ])
    if (!status || typeof status !== 'object' || Array.isArray(status)) throw { status: 503 }
    return { health, status, analytics, benchmarks }
  }
  const refresh = () => {
    if (!alive() || state.saving) return Promise.resolve()
    if (reading) return reading
    const request = ++revision
    reading = (async () => {
      try {
        const data = await readSnapshot()
        if (alive() && request === revision) publish({ data, error: null })
      } catch (reason) {
        if (alive() && request === revision) publish({ error: recoveryMessage(reason) })
      } finally {
        reading = null
      }
    })()
    return reading
  }
  const poll = async () => {
    await refresh()
    if (alive()) timer = schedule(poll, 20000)
  }
  const chooseMode = async (endpoint, mode) => {
    if (!alive() || state.saving || !compatible(state.data) || !MODES.includes(mode)) return
    const health = state.data.health
    const capability = endpoint === '/mode' ? 'routing_mode_write' : endpoint === '/compaction' ? 'compaction_mode_write' : null
    if (!capability || health.capabilities?.[capability] !== true) return
    if (endpoint === '/compaction' && mode !== 'off' && health.context_engine?.configured !== ID) return
    const request = ++revision
    publish({ saving: true, error: null, feedback: null })
    try {
      await rest(endpoint, { ...OPTIONS, method: 'PUT', body: { mode } })
      if (!alive() || request !== revision) return
      const data = await readSnapshot()
      if (!alive() || request !== revision) return
      const saved = endpoint === '/mode' ? data.health.routing_mode : data.health.compaction_mode
      if (!compatible(data) || saved !== mode) {
        publish({ data, error: 'The requested mode was not confirmed by the backend. Refresh and check /jev status on this connection.' })
        return
      }
      publish({ data, feedback: `${endpoint === '/mode' ? 'Routing' : 'Compaction'} saved as ${mode} on ${scopeLabel(scope)}.` })
    } catch (reason) {
      if (alive() && request === revision) publish({ error: recoveryMessage(reason) })
    } finally {
      if (alive() && request === revision) publish({ saving: false })
    }
  }
  return {
    start() { publish(state); void poll() },
    refresh,
    chooseMode,
    dispose() { disposed = true; revision += 1; if (timer !== null) cancel(timer) }
  }
}

function Card({ title, children }) {
  return jsxs('section', {
    className: 'rounded-xl border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) p-4',
    style: { minWidth: 0 },
    children: [title ? jsx('h2', { className: 'mb-3 text-sm font-semibold', children: title }) : null, children]
  })
}
const number = value => Number.isFinite(value) ? value.toLocaleString() : '—'
const milliseconds = value => Number.isFinite(value) ? `${Math.round(value)} ms` : '—'
const money = value => Number.isFinite(value) ? `$${value.toFixed(4)}` : '—'
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
function metric(label, value) {
  return jsx(Card, { children: jsxs('div', { children: [
    jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: label }),
    jsx('p', { className: 'mt-1 text-xl font-semibold tabular-nums', children: value })
  ] }) }, label)
}
function ModeButtons({ value, disabled, canChoose = () => true, onSelect }) {
  return jsx('div', { className: 'flex flex-wrap gap-2', children: MODES.map(mode => jsx(Button, {
    type: 'button', size: 'sm', variant: mode === value ? 'default' : 'outline',
    'aria-pressed': mode === value,
    disabled: disabled || mode === value || !canChoose(mode),
    onClick: () => onSelect(mode), children: mode[0].toUpperCase() + mode.slice(1)
  }, mode)) })
}
function DataTable({ caption, columns, rows, empty }) {
  return jsx('div', { style: { overflowX: 'auto', maxWidth: '100%' }, children: jsxs('table', {
    className: 'w-full text-left text-xs',
    children: [jsx('caption', { className: 'mb-2 text-left text-(--ui-text-secondary)', children: caption }),
      jsx('thead', { children: jsx('tr', { children: columns.map(([key, label]) => jsx('th', { scope: 'col', className: 'p-2', children: label }, key)) }) }),
      jsx('tbody', { children: rows.length ? rows.map((row, index) => jsx('tr', { children: columns.map(([key, , format = value => value ?? '—']) => jsx('td', { className: 'p-2', children: format(row[key]) }, key)) }, index))
        : jsx('tr', { children: jsx('td', { colSpan: columns.length, className: 'p-2 text-(--ui-text-secondary)', children: empty }) }) })]
  }) })
}
const setupText = {
  credential_missing: 'Add OPENROUTER_JEV_API_TOKEN or your existing OPENROUTER_API_KEY through the selected backend’s secure credential settings. Never paste it into chat.',
  context_engine_not_selected: 'For compaction, set context.engine to hermes-jev-performance in this profile’s Hermes settings, restart the agent, then check /jev compaction status. Replacing another custom engine is your choice.',
  settings_read_only: 'Some settings are administrator-managed or this host cannot verify write support. Use the selected backend’s supported settings workflow.',
  plugin_conflict: 'Another Jev plugin is enabled. Review it before enabling optimization here to avoid duplicate routing or compaction. Nothing is disabled automatically.'
}

export function PerformancePage({ rest }) {
  const connectionId = useValue(host.state.connectionId)
  const profile = useValue(host.state.profile)
  const scope = { connectionId, profile }
  const key = scopeKey(scope)
  const [snapshot, setSnapshot] = useState(null)
  const session = useRef(null)
  useEffect(() => {
    const next = createPanelSession({ rest, scope: { connectionId, profile }, getScope: currentScope, onChange: setSnapshot })
    session.current = next
    next.start()
    return () => { next.dispose(); if (session.current === next) session.current = null }
  }, [connectionId, profile, rest])
  const view = snapshot?.scopeKey === key ? snapshot : null
  const data = view?.data
  const title = jsxs('header', { children: [
    jsx('h1', { className: 'text-xl font-semibold', children: 'Jev Performance' }),
    jsx('p', { className: 'mt-1 text-sm text-(--ui-text-secondary)', children: `Connected to ${scopeLabel(scope)}. Settings and metrics belong to this connection.` })
  ] })
  const refresh = jsx(Button, { type: 'button', size: 'sm', variant: 'outline', disabled: view?.saving, onClick: () => void session.current?.refresh(), children: 'Refresh' })
  const layout = children => jsxs('main', { className: 'mx-auto flex h-full w-full max-w-5xl flex-col gap-5 overflow-auto p-5', style: { minWidth: 0 }, children: [title, ...children] })
  if (!data) return layout([
    jsx('div', { role: view?.error ? 'alert' : 'status', children: view?.error || 'Checking the selected Hermes backend…' }),
    jsx('a', { href: `hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1`, children: 'Install Server only on this connection' }), refresh
  ])
  if (!compatible(data)) return layout([jsx('p', { role: 'alert', children: 'This backend has an incompatible Jev Performance version. Update the Server component on this connection, then refresh. Controls are disabled.' }), refresh])
  const { health, status, analytics, benchmarks } = data
  const summary = status.summary_24h || {}
  const compact = status.compaction?.summary_24h || {}
  const saving = view.saving
  const engineReady = health.context_engine?.configured === ID
  const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 210px), 1fr))', gap: 16 }
  const routes = analytics?.routes || []
  const recent = analytics?.recent || []
  const runs = benchmarks?.runs || []
  return layout([
    view.error ? jsx('p', { role: 'alert', children: view.error }) : null,
    view.feedback ? jsx('p', { role: 'status', 'aria-live': 'polite', children: view.feedback }) : null,
    refresh,
    jsx(Card, { title: 'Setup checklist', children: jsxs('div', { className: 'space-y-2 text-sm', children: [
      jsx('p', { children: `Server ${health.backend_version} · Jev credential ${health.credential_present ? 'available' : 'not configured'}` }),
      ...(health.setup_issues || []).map(issue => jsx('p', { children: setupText[issue] || 'Run /jev doctor on this connection for the remaining setup step.' }, issue)),
      health.conflicting_plugins?.length ? jsx('p', { children: `Review enabled plugins: ${health.conflicting_plugins.join(', ')}.` }) : null,
      engineReady ? jsx('p', { children: 'The compaction engine is configured. A saved selection does not prove it is active in an existing chat; restart and check /jev compaction status.' }) : null,
      jsx('p', { children: 'Off makes no Jev calls. Shadow sends paid Jev requests without applying decisions. On applies accepted decisions and also sends paid requests.' })
    ] }) }),
    jsxs('div', { style: gridStyle, children: [
      jsx(Card, { title: 'Tool routing', children: jsx(ModeButtons, { value: health.routing_mode, disabled: saving || health.capabilities?.routing_mode_write !== true, onSelect: mode => void session.current?.chooseMode('/mode', mode) }) }),
      jsx(Card, { title: 'Recoverable compaction', children: jsxs('div', { className: 'space-y-3', children: [
        jsx(ModeButtons, { value: health.compaction_mode, disabled: saving || health.capabilities?.compaction_mode_write !== true, canChoose: mode => mode === 'off' || engineReady, onSelect: mode => void session.current?.chooseMode('/compaction', mode) }),
        jsx('p', { className: 'text-xs', children: status.compaction?.external_transmission_allowed === true
          ? 'Compaction On and Shadow may send redacted history, memory excerpts and complete redacted tool-output chunks to OpenRouter and incur charges. Older unique outputs can be archived only when every complete chunk passes the relevance threshold; uncertain output stays.'
          : 'External compaction transmission is blocked. Compaction starts Off; select the native engine and allow external data to enable it. To allow paid history, memory and tool-output transmission, explicitly opt in with /jev compaction allow-external.' }),
        status.compaction?.suspended_by_global_off ? jsx('p', { className: 'text-xs', children: 'Compaction is suspended while tool routing is Off. Its saved mode resumes when global routing is enabled.' }) : null,
        !engineReady ? jsx('p', { className: 'text-xs', children: 'Choose the Jev Performance context engine and restart the agent before enabling compaction.' }) : null
      ] }) })
    ] }),
    jsx('div', { style: gridStyle, children: [
      metric('Decisions · 24 hours', number(summary.decisions)), metric('Applied routes', number(summary.applied)),
      metric('Unapplied / fallback decisions', number(summary.fallback)), metric('Average Jev time', milliseconds(summary.avg_jev_latency_ms)),
      metric('Jev time · median / p95', `${milliseconds(summary.p50_jev_latency_ms)} / ${milliseconds(summary.p95_jev_latency_ms)}`),
      metric('Average confidence', percent(summary.avg_confidence)), metric('Jev cost · 24 hours', money(summary.total_jev_cost_usd)),
      metric('Hermes turns', number(summary.turns)), metric('Average Hermes turn', milliseconds(summary.avg_turn_duration_ms)),
      metric('Average tool calls', number(summary.avg_tool_calls)), metric('Average LLM requests', number(summary.avg_llm_requests)),
      metric('Hermes input tokens', number(summary.input_tokens)), metric('Hermes output tokens', number(summary.output_tokens)),
      metric('Compactions applied', number(compact.applied)), metric('Compaction fallbacks', number(compact.fallback)),
      metric('Estimated tokens saved', number(compact.estimated_tokens_saved)), metric('Archived outputs recovered', number(compact.retrievals)),
      metric('Compaction Jev cost', money(compact.cost_usd))
    ] }),
    status.telemetry?.database_state === 'empty' ? jsx('p', { children: 'No performance history yet. Chat normally on this backend to collect baseline metrics; routing can stay Off.' }) : null,
    status.telemetry?.error ? jsx('p', { role: 'alert', children: 'Performance history is unavailable. Run /jev doctor; unavailable measurements are shown as —.' }) : null,
    jsx(Card, { title: 'Routing details · 24 hours', children: jsxs('div', { children: [
      !analytics ? jsx('p', { children: 'Detailed analytics are unavailable on this backend. Update Server or check /jev doctor.' }) : null,
      jsx(DataTable, { caption: 'Tool families', columns: [['family', 'Family'], ['count', 'Decisions', number]], rows: routes, empty: 'No routing decisions yet.' }),
      jsx(DataTable, { caption: 'Fallback and skipped reasons', columns: [['reason', 'Reason'], ['count', 'Turns', number]], rows: analytics?.reasons || [], empty: 'No reason history yet.' }),
      jsx(DataTable, { caption: 'Recent decisions', columns: [['mode', 'Mode'], ['family', 'Family'], ['confidence', 'Confidence', percent], ['latency_ms', 'Jev time', milliseconds], ['cost_usd', 'Cost', money], ['reason', 'Outcome']], rows: recent, empty: 'No recent decisions.' })
    ] }) }),
    jsx(Card, { title: 'Observed Off / Shadow / On', children: jsx(DataTable, {
      caption: 'Ordinary conversation totals are observational; different workloads are not a controlled A/B test.',
      columns: [['mode', 'Mode'], ['turns', 'Turns', number], ['avg_duration_ms', 'Average turn', milliseconds], ['avg_tool_calls', 'Tools', number], ['avg_input_tokens', 'Input tokens', number], ['avg_output_tokens', 'Output tokens', number], ['total_jev_cost_usd', 'Jev cost', money]],
      rows: analytics?.comparison || [], empty: 'No mode comparison yet.'
    }) }),
    jsx(Card, { title: 'Activity over time', children: jsx(DataTable, { caption: 'Observed activity for the last 24 hours.', columns: [['started_at', 'From', value => Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : '—'], ['turns', 'Turns', number], ['avg_duration_ms', 'Average turn', milliseconds]], rows: analytics?.series || [], empty: 'No activity history yet.' }) }),
    jsx(Card, { title: 'Controlled benchmarks', children: !benchmarks ? jsx('p', { children: 'Benchmark history is unavailable on this backend.' }) : !runs.length ? jsx('p', { children: 'No controlled benchmark yet. A benchmark is an optional developer action with paid provider calls; normal conversation data does not prove savings.' }) : runs.map(run => {
      const kind = run.methodology?.kind
      const measured = kind === 'controlled_matched_benchmark'
      const label = kind === 'synthetic_ci' ? 'Synthetic test data · not measured performance' : measured ? 'Measured matched workloads' : 'Methodology unverified · do not claim measured savings'
      const rows = Object.entries(run.comparison?.metrics || {}).map(([name, values]) => ({ name, ...values }))
      return jsxs('div', { className: 'mb-4', children: [
        jsx('p', { children: `${label} · ${run.status} · ${number(run.comparison?.matched_pairs)} matched pairs · ${number(run.failed_samples)} failed samples` }),
        jsx(DataTable, { caption: 'ON minus OFF; review sample count, failed runs, and methodology before interpreting changes.', columns: [['name', 'Metric'], ['pairs', 'Pairs', number], ['off_mean', 'Off average', number], ['on_mean', 'On average', number], ['percent_change', 'Change %', value => Number.isFinite(value) ? `${value.toFixed(1)}%` : '—']], rows, empty: 'No valid matched pairs.' })
      ] }, run.run_id)
    }) }),
    jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: `Dashboard ${VERSION} · Backend ${health.backend_version} · API ${health.api_schema_version}` })
  ])
}

export default {
  id: ID, name: 'Jev Performance', description: 'Jev routing, recoverable compaction, and backend performance.', defaultEnabled: false,
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: 'routes', data: { path: PAGE }, render: () => jsx(PerformancePage, { rest: ctx.rest }) },
      { id: 'nav', area: 'sidebar.nav', data: { path: PAGE, label: 'Jev Performance', codicon: 'graph' } },
      { id: 'open', area: 'palette', data: { id: 'jev-performance.open', label: 'Open Jev Performance', keywords: ['jev', 'routing', 'compaction', 'metrics'], run: () => host.navigate(PAGE) } }
    ])
  }
}
