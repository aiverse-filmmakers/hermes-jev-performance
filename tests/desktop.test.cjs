const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { test } = require('node:test')
const path = require('node:path')

async function load() {
  const state = { connectionId: 'vps-a', profile: 'default', focusedSessionProfile: 'other-profile' }
  let snapshot = null
  const host = { state: Object.fromEntries(Object.keys(state).map(key => [key, { get: () => state[key] }])), navigate() {} }
  const context = vm.createContext({ setTimeout, clearTimeout, console, Date })
  const hook = {
    useState: () => [snapshot, next => { snapshot = next }],
    useRef: () => ({ current: null }), useEffect() {}
  }
  const element = (type, props) => ({ type, props })
  const modules = {
    '@hermes/plugin-sdk': { host, useValue: atom => atom.get(), Button: 'button' },
    react: hook, 'react/jsx-runtime': { jsx: element, jsxs: element }
  }
  const source = fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8')
  const plugin = new vm.SourceTextModule(source, { context })
  await plugin.link(async name => {
    assert.ok(modules[name], `Undocumented import: ${name}`)
    const values = modules[name]
    return new vm.SyntheticModule(Object.keys(values), function () {
      for (const [key, value] of Object.entries(values)) this.setExport(key, value)
    }, { context })
  })
  await plugin.evaluate()
  return { api: plugin.namespace, state, scope: () => ({ connectionId: state.connectionId, profile: state.profile }), setSnapshot: value => { snapshot = value } }
}
const health = extra => ({ plugin_id: 'hermes-jev-performance', api_schema_version: 1, backend_version: 'test', routing_mode: 'off', compaction_mode: 'off', context_engine: { configured: 'hermes-jev-performance' }, capabilities: { routing_mode_write: true, compaction_mode_write: true }, setup_issues: [], ...extra })
const status = () => ({ summary_24h: { decisions: 0, input_tokens: null }, telemetry: { database_state: 'empty' }, compaction: { suspended_by_global_off: true, summary_24h: {} } })
const fixture = p => p === '/health' ? health() : p === '/status' ? status() : p.startsWith('/analytics') ? { routes: [], reasons: [], series: [], comparison: [], recent: [] } : { runs: [] }
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const settle = () => new Promise(resolve => setImmediate(resolve))
function setup(api, scope, rest) {
  const events = [], timers = new Map()
  let id = 0
  const session = api.createPanelSession({ rest, scope: scope(), getScope: scope, onChange: event => events.push(event), schedule: callback => { timers.set(++id, callback); return id }, cancel: key => timers.delete(key) })
  return { session, events, timers, latest: () => events.at(-1) }
}
function renderTree(node) {
  if (Array.isArray(node)) return node.map(renderTree)
  if (!node || typeof node !== 'object') return node
  if (typeof node.type === 'function') return renderTree(node.type(node.props))
  const children = node.props?.children
  return { ...node, props: { ...node.props, children: Array.isArray(children) ? children.map(renderTree) : renderTree(children) } }
}
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes)
  if (!tree || typeof tree !== 'object') return []
  const children = tree.props?.children
  return [tree, ...(Array.isArray(children) ? children : [children]).flatMap(nodes)]
}
function text(tree) { return nodes(tree).flatMap(node => Array.isArray(node.props?.children) ? node.props.children : [node.props?.children]).filter(x => typeof x === 'string').join('\n') }

test('native entry registers sidebar, route and palette using SDK contributions', async () => {
  const { api } = await load()
  let contributions
  api.default.register({ registerMany: value => { contributions = value }, rest: async () => ({}) })
  assert.equal(api.default.id, 'hermes-jev-performance')
  assert.deepEqual(Array.from(contributions, c => c.area), ['routes', 'sidebar.nav', 'palette'])
})

test('display uses REST gateway profile rather than focused-chat profile', async () => {
  const { api } = await load()
  const output = text(renderTree(api.PerformancePage({ rest: async () => ({}) })))
  assert.match(output, /Connected to vps-a · default/)
  assert.doesNotMatch(output, /other-profile/)
})

test('old refresh responses never repaint a new scope and requests have timeouts', async () => {
  const { api, state, scope } = await load()
  const requests = []
  const h = setup(api, scope, (p, opts) => { assert.equal(opts.timeoutMs, 8000); const d = deferred(); requests.push({ p, ...d }); return d.promise })
  h.session.start()
  const count = h.events.length
  state.connectionId = 'vps-b'
  requests.forEach(d => d.resolve(fixture(d.p)))
  await settle()
  assert.equal(h.events.length, count)
  assert.equal(h.timers.size, 0)
  h.session.dispose()
})

test('read-back and saving updates from an old write do not reach a new scope', async () => {
  const { api, state, scope } = await load()
  let pending = false
  const requests = []
  const h = setup(api, scope, async (p, opts) => {
    if (opts.method === 'PUT') { pending = true; return { mode: 'on' } }
    if (pending) { const d = deferred(); requests.push({ p, ...d }); return d.promise }
    return fixture(p)
  })
  await h.session.refresh()
  const write = h.session.chooseMode('/mode', 'on')
  await settle()
  state.connectionId = 'vps-b'
  const count = h.events.length
  requests.forEach(d => d.resolve(d.p === '/health' ? health({ routing_mode: 'on' }) : fixture(d.p)))
  await write
  assert.equal(h.events.length, count)
  h.session.dispose()
})

test('a write supersedes a pending poll and verifies persistence', async () => {
  const { api, scope } = await load()
  let mode = 'off', hold = false
  const requests = []
  const h = setup(api, scope, async (p, opts) => {
    if (opts.method === 'PUT') { mode = opts.body.mode; hold = false; return { mode } }
    if (hold) { const d = deferred(); requests.push({ p, ...d }); return d.promise }
    return p === '/health' ? health({ routing_mode: mode }) : fixture(p)
  })
  await h.session.refresh()
  hold = true
  const poll = h.session.refresh()
  await h.session.chooseMode('/mode', 'on')
  requests.forEach(d => d.resolve(fixture(d.p)))
  await poll
  assert.equal(h.latest().data.health.routing_mode, 'on')
  assert.match(h.latest().feedback, /saved as on on vps-a · default/)
  assert.equal(h.latest().saving, false)
  h.session.dispose()
})

test('writes require compatible schema, permission and compaction engine', async () => {
  for (const extra of [{ api_schema_version: 2 }, { capabilities: { routing_mode_write: false } }, { context_engine: { configured: null } }]) {
    const { api, scope } = await load()
    let writes = 0
    const h = setup(api, scope, async (p, opts) => { if (opts.method === 'PUT') writes++; return p === '/health' ? health(extra) : fixture(p) })
    await h.session.refresh()
    await h.session.chooseMode(extra.context_engine ? '/compaction' : '/mode', 'on')
    assert.equal(writes, 0)
    h.session.dispose()
  }
})

test('unload clears timers and pending requests cannot update state', async () => {
  const { api, scope } = await load()
  let waiting = false
  const requests = []
  const h = setup(api, scope, async p => { if (!waiting) return fixture(p); const d = deferred(); requests.push({ p, ...d }); return d.promise })
  h.session.start()
  await settle()
  assert.equal(h.timers.size, 1)
  waiting = true
  const poll = h.session.refresh()
  h.session.dispose()
  const count = h.events.length
  requests.forEach(d => d.resolve(fixture(d.p)))
  await poll
  assert.equal(h.timers.size, 0)
  assert.equal(h.events.length, count)
})

test('slow polling is single-flight and failed persistence produces guidance', async () => {
  const { api, scope } = await load()
  let calls = 0
  const d = deferred()
  const h = setup(api, scope, p => { calls++; return d.promise.then(() => fixture(p)) })
  const first = h.session.refresh()
  const second = h.session.refresh()
  assert.equal(first, second)
  assert.equal(calls, 4)
  d.resolve()
  await first
  await h.session.chooseMode('/mode', 'on')
  assert.match(h.latest().error, /not confirmed/)
  h.session.dispose()
})

test('missing, disabled, unauthorized, profile and offline states give specific recovery', async () => {
  const { api } = await load()
  for (const [status, match] of [[404, /missing or disabled/], [401, /authentication/], [403, /administrator/], [409, /profile/], [503, /doctor/], [0, /Reconnect|reconnect/]]) {
    assert.match(api.recoveryMessage({ status, message: 'PRIVATE_DETAIL' }), match)
    assert.doesNotMatch(api.recoveryMessage({ status, message: 'PRIVATE_DETAIL' }), /PRIVATE_DETAIL/)
  }
})

test('malformed status and unavailable analytics fail safely', async () => {
  const { api, scope } = await load()
  const h = setup(api, scope, async p => p === '/health' ? health() : p === '/status' ? null : fixture(p))
  await h.session.refresh()
  assert.match(h.latest().error, /Server component is present but unavailable/)
  assert.equal(h.latest().data, null)
  h.session.dispose()
})

test('empty metrics, setup, suspended compaction and benchmark methodology are rendered honestly', async () => {
  const { api, scope, setSnapshot } = await load()
  const data = { health: health({ setup_issues: ['credential_missing', 'context_engine_not_selected', 'plugin_conflict'], conflicting_plugins: ['jev-router'] }), status: status(), analytics: fixture('/analytics'), benchmarks: { runs: [{ run_id: 'synthetic', status: 'complete', methodology: { kind: 'synthetic_ci' }, comparison: { matched_pairs: 2, metrics: {} } }] } }
  setSnapshot({ scopeKey: JSON.stringify(['vps-a', 'default']), data, saving: false })
  const tree = renderTree(api.PerformancePage({ rest: async () => ({}) }))
  const output = text(tree)
  assert.match(output, /No performance history yet/)
  assert.match(output, /suspended while tool routing is Off/)
  assert.match(output, /Synthetic test data · not measured/)
  assert.match(output, /another custom engine is your choice/)
  assert.match(output, /Review enabled plugins: jev-router/)
  assert.match(output, /Hermes input tokens/)
  assert.match(output, /—/)
  const on = nodes(tree).filter(node => node.type === 'button' && node.props.children === 'On')
  assert.ok(on.length > 0)
  assert.equal(scope().profile, 'default')
})
