import { host, useValue, Button } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PAGE = '/jev-performance'
const MODES = ['off', 'shadow', 'on']

function Card({ children, className = '' }) {
  return jsx('section', { className: `rounded-xl border border-(--ui-stroke-secondary) bg-(--ui-bg-secondary) shadow-sm ${className}`, children })
}

function CardHeader({ children, className = '' }) {
  return jsx('div', { className: `p-4 ${className}`, children })
}

function CardContent({ children, className = '' }) {
  return jsx('div', { className, children })
}

function CardTitle({ children }) {
  return jsx('h2', { className: 'text-sm font-semibold', children })
}

function CardDescription({ children }) {
  return jsx('p', { className: 'mt-1 text-xs text-(--ui-text-secondary)', children })
}

function ModeButtons({ value, disabled, canChoose = () => true, onSelect }) {
  return jsxs('div', {
    className: 'flex flex-wrap gap-2',
    children: MODES.map(mode => jsx(Button, {
      type: 'button',
      size: 'sm',
      variant: mode === value ? 'default' : 'outline',
      disabled: disabled || mode === value || !canChoose(mode),
      onClick: () => onSelect(mode),
      children: mode === 'shadow' ? 'Shadow · sends Jev requests' : mode[0].toUpperCase() + mode.slice(1)
    }, mode))
  })
}

function PerformancePage({ rest }) {
  const connectionId = useValue(host.state.connectionId)
  const profile = useValue(host.state.focusedSessionProfile)
  const scopeKey = `${connectionId || 'local'}:${profile || 'default'}`
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const generation = useRef(0)

  useEffect(() => {
    const myGeneration = ++generation.current
    let disposed = false

    const refresh = async () => {
      try {
        const [health, status] = await Promise.all([rest('/health'), rest('/status')])
        if (!disposed && myGeneration === generation.current) {
          setData({ health, status, scopeKey })
          setError(null)
        }
      } catch (reason) {
        if (!disposed && myGeneration === generation.current) {
          setError(String(reason?.message || 'Could not reach the selected Hermes backend.'))
        }
      }
    }

    setData(null)
    void refresh()
    const timer = setInterval(refresh, 20000)
    return () => {
      disposed = true
      clearInterval(timer)
      generation.current += 1
    }
  }, [connectionId, profile, rest, scopeKey])

  const chooseMode = async (endpoint, mode) => {
    if (host.state.connectionId.get() !== connectionId || host.state.focusedSessionProfile.get() !== profile) return
    setSaving(true)
    setError(null)
    try {
      await rest(endpoint, { method: 'PUT', body: { mode } })
      if (host.state.connectionId.get() !== connectionId || host.state.focusedSessionProfile.get() !== profile) return
      const [health, status] = await Promise.all([rest('/health'), rest('/status')])
      setData({ health, status, scopeKey })
    } catch (reason) {
      if (host.state.connectionId.get() === connectionId && host.state.focusedSessionProfile.get() === profile) {
        setError(String(reason?.message || 'The setting could not be saved.'))
      }
    } finally {
      setSaving(false)
    }
  }

  const scope = `${connectionId || 'This computer'} · ${profile || 'default profile'}`
  const currentData = data?.scopeKey === scopeKey ? data : null
  if (error && !currentData) {
    return jsx('div', { className: 'mx-auto flex max-w-3xl flex-col gap-4 p-6', children: [
      jsx(Card, { children: jsxs(CardContent, { className: 'space-y-3 p-5', children: [
        jsx('p', { className: 'font-medium', children: 'Jev Performance could not reach this Hermes backend.' }),
        jsx('p', { className: 'text-sm text-(--ui-text-secondary)', children: error }),
        jsx('p', { className: 'text-sm text-(--ui-text-tertiary)', children: `Selected connection: ${scope}` })
      ] }) })
    ] })
  }
  if (!currentData) return jsx('div', { className: 'p-6 text-sm text-(--ui-text-secondary)', children: 'Checking the selected Hermes backend…' })

  const { health, status } = currentData
  if (health.api_schema_version !== 1 || health.plugin_id !== 'hermes-jev-performance') {
    return jsx(Card, { className: 'm-6', children: jsx(CardContent, { className: 'p-5', children: 'This backend has an incompatible Jev Performance version. Update the server plugin, then reload this page.' }) })
  }
  const summary = status.summary_24h || {}
  const compactSummary = status.compaction?.summary_24h || {}
  const canRoute = health.capabilities?.routing_mode_write === true
  const canCompact = health.capabilities?.compaction_mode_write === true
  const engineReady = health.context_engine?.configured === 'hermes-jev-performance'

  return jsxs('main', { className: 'mx-auto flex h-full w-full max-w-5xl flex-col gap-5 overflow-auto p-5 md:p-8', children: [
    jsxs('header', { className: 'flex flex-col gap-1', children: [
      jsx('h1', { className: 'text-xl font-semibold tracking-tight', children: 'Jev Performance' }),
      jsx('p', { className: 'text-sm text-(--ui-text-secondary)', children: `Connected to ${scope}. Settings and metrics belong to this connection.` })
    ] }),
    error ? jsx(Card, { children: jsx(CardContent, { className: 'p-3 text-sm text-(--ui-text-secondary)', children: error }) }) : null,
    health.setup_issues?.length ? jsx(Card, { children: jsxs(CardContent, { className: 'space-y-2 p-4', children: [
      jsx('p', { className: 'font-medium', children: 'Setup checklist' }),
      ...health.setup_issues.map(issue => jsx('p', { className: 'text-sm text-(--ui-text-secondary)', children: issue === 'credential_missing'
        ? 'Add your Jev/OpenRouter credential securely to the selected Hermes backend. Never paste it into chat.'
        : 'Select the Jev Performance context engine in this backend’s Hermes settings, then restart the agent before using compaction.' }, issue))
    ] }) }) : null,
    jsxs('div', { className: 'grid gap-4 md:grid-cols-2', children: [
      jsx(Card, { children: jsxs(CardHeader, { className: 'gap-3', children: [
        jsxs('div', { children: [jsx(CardTitle, { children: 'Tool routing' }), jsx(CardDescription, { children: 'Jev helps choose which tool families Hermes should make available.' })] }),
        jsx(ModeButtons, { value: health.routing_mode, disabled: saving || !canRoute, onSelect: mode => void chooseMode('/mode', mode) }),
        health.routing_mode === 'shadow' ? jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Shadow sends Jev requests and may incur provider charges, while leaving tool choices unchanged.' }) : null
      ] }) }),
      jsx(Card, { children: jsxs(CardHeader, { className: 'gap-3', children: [
        jsxs('div', { children: [jsx(CardTitle, { children: 'Recoverable compaction' }), jsx(CardDescription, { children: 'Archive selected old tool output and recover its exact contents when needed.' })] }),
        jsx(ModeButtons, { value: health.compaction_mode, disabled: saving || !canCompact, canChoose: mode => mode === 'off' || engineReady, onSelect: mode => void chooseMode('/compaction', mode) }),
        !engineReady ? jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: 'Compaction stays off until the Jev Performance context engine is selected in Hermes settings.' }) : null
      ] }) })
    ] }),
    jsxs('div', { className: 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3', children: [
      metric('Decisions · 24 hours', summary.decisions),
      metric('Average Jev time', summary.avg_jev_latency_ms == null ? '—' : `${Math.round(summary.avg_jev_latency_ms)} ms`),
      metric('Jev cost · 24 hours', summary.total_jev_cost_usd == null ? '—' : `$${summary.total_jev_cost_usd.toFixed(4)}`),
      metric('Compactions · 24 hours', compactSummary.applied),
      metric('Estimated tokens saved', compactSummary.estimated_tokens_saved),
      metric('Archived outputs recovered', compactSummary.retrievals)
    ] }),
    jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: `Backend ${health.backend_version} · API ${health.api_schema_version} · Jev credential ${health.credential_present ? 'available' : 'not configured'}` })
  ] })
}

function metric(label, value) {
  return jsx(Card, { children: jsxs(CardContent, { className: 'space-y-1 p-4', children: [
    jsx('p', { className: 'text-xs text-(--ui-text-tertiary)', children: label }),
    jsx('p', { className: 'text-2xl font-semibold tabular-nums', children: value ?? '—' })
  ] }) }, label)
}

export default {
  id: 'hermes-jev-performance',
  name: 'Jev Performance',
  description: 'Jev routing controls, recoverable compaction, and backend performance.',
  defaultEnabled: false,
  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: 'routes', data: { path: PAGE }, render: () => jsx(PerformancePage, { rest: ctx.rest }) },
      { id: 'nav', area: 'sidebar.nav', data: { path: PAGE, label: 'Jev Performance', codicon: 'graph' } },
      { id: 'open', area: 'palette', data: { id: 'jev-performance.open', label: 'Open Jev Performance', keywords: ['jev', 'routing', 'compaction', 'metrics'], run: () => host.navigate(PAGE) } }
    ])
  }
}
