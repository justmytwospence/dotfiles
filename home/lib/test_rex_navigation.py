"""Behavioral tests for the actual Rex navigation actions, with no live server."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'dot_config/rex/init.lua.tmpl'

# The action and each subprocess receive separate Rex facades. The latter runs
# the embedded helper itself, not a canned approximation of its results.
HARNESS = r'''
local actions, bindings, warnings, focused, queued = {}, {}, {}, {}, {}
local hosts, aliases, default = {}, {}, 'local'
local failures, executions, attachments = {}, {}, {}
local before_focus, helper_transform, response_transform
local function check_failure(method, host, id)
  local failure = failures[host .. ':' .. method .. ':' .. (id or '')]
  if failure then return nil, failure end
  return true
end
local function api(host)
  local a = {}
  a.call = function(method, args)
    assert(method == 'server.status', 'unexpected API method: ' .. tostring(method))
    local ok, err = check_failure('server.status', host)
    if not ok then return nil, err end
    return { host_id = hosts[host].id }
  end
  local session = {
    list = function()
      local ok, err = check_failure('session.list', host)
      if not ok then return nil, err end
      local sessions = {}
      for _, s in ipairs(hosts[host].sessions) do sessions[#sessions+1] = {session_id=s.id} end
      return {sessions=sessions}
    end,
    view = function(args)
      local ok, err = check_failure('session.view', host, args.session_id)
      if not ok then return nil, err end
      for _, s in ipairs(hosts[host].sessions) do
        if s.id == args.session_id then return s.view end
      end
      return nil, 'session not found'
    end,
    focus_block = function(args)
      local ok, err = check_failure('session.focus_block', host, args.block_id)
      if not ok then return nil, err end
      focused[#focused+1] = {host=host, session_id=args.session_id, block_id=args.block_id}
      return {}
    end,
  }
  local status = a.call
  a.call = function(method, args)
    if method == 'server.status' then return status(method, args) end
    if method == 'session.attach_all' then
      assert(args.event_scope == 'session')
      attachments[#attachments+1] = host
      return {}
    end
    local name = method:match('^session%.(.+)$')
    assert(name and session[name], 'unexpected helper API: '..tostring(method))
    return session[name](args or {})
  end
  a.block = {call = function(creator, method, args)
    assert(creator == 'com.superlogical.terminal' and method == 'program_status')
    local ok, err = check_failure('program_status', host, args.block_id)
    if not ok then return nil, err end
    for _, s in ipairs(hosts[host].sessions) do
      if s.id == args.session_id and s.records[args.block_id] then
        return {records=s.records[args.block_id]}
      end
    end
    return nil, 'block not found'
  end}
  return a
end
local rex = {
  bind = function(key, name) bindings[key] = name end,
  mode = function() end,
  host = function(def) assert(def.label == 'nuc') end,
  action = function(def) assert(type(def) == 'table'); actions[def.name] = def end,
  call = function(method, args)
    assert(method == 'server.status', 'parent attempted '..tostring(method))
    return api(default).call(method, args)
  end,
  client = {queue = function(name, args)
    assert(name == 'session.select')
    if failures.queue then return nil, failures.queue end
    queued[#queued+1] = args
    return {}
  end},
  log = function(level, message) warnings[#warnings+1] = {level, message} end,
  json = {encode=vim.json.encode, decode=vim.json.decode, null=vim.NIL},
}
rex.exec = function(argv, opts)
  assert(type(argv) == 'table' and type(opts) == 'table')
  local source, payload
  for i, arg in ipairs(argv) do
    if arg == '-e' then source = argv[i+1] end
    if arg == '--args' then payload = vim.json.decode(argv[i+1]) end
  end
  assert(type(source) == 'string' and type(payload) == 'table')
  executions[#executions+1] = {argv=argv, opts=opts, op=payload.op}
  if failures.transport == payload.op then return nil, 'transport failure' end
  if failures.timeout == payload.op then return {timed_out=true, code=0, stdout=''} end
  if failures.exit == payload.op then return {code=1, stdout='', stderr='failed'} end
  if failures.json == payload.op then return {code=0, stdout='not json'} end
  if payload.op == 'focus' and before_focus then before_focus(payload) end
  local child = api('local')
  child.args = payload
  child.json = {encode=vim.json.encode, decode=vim.json.decode, null=vim.NIL}
  child.servers = function() local t = {}; for label in pairs(aliases) do t[#t+1]=label end; return t end
  child.server = function(label) return api(assert(aliases[label], label)) end
  local env = setmetatable({rex=child}, {__index=_G})
  if helper_transform then source = helper_transform(source) end
  local chunk, err = loadstring(source, 'embedded-helper')
  assert(chunk, err)
  setfenv(chunk, env)
  local ok, result = pcall(chunk)
  if not ok then return {code=1, stdout='', stderr=tostring(result)} end
  if response_transform then result = response_transform(payload.op, result) end
  return {code=0, stdout=vim.json.encode(result), stderr=''}
end
local function pane(id, state, timestamp)
  return {id=id, records=state and {{id='root', state=state, updated_at=timestamp or '2026-01-01T00:00:00Z'}} or {}}
end
local function host(name, id, session, panes)
  local blocks, records = {}, {}
  for _, p in ipairs(panes) do
    blocks[#blocks+1] = {block_id=p.id, creator_name=p.creator or 'com.superlogical.terminal'}
    records[p.id] = p.records
  end
  local layer = {layer_id='layer', kind='tiled', bounds={0,0,1,1}, layout={rect={0,0,1,1}}, blocks=blocks}
  local view = {revision=1, session_id=session, active_window_id='w-'..session,
    windows={{window_id='w-'..session, focused_block_id=panes[1] and panes[1].id, layers={layer}}}}
  local s = {id=session, view=view, records=records}
  hosts[name] = {id=id, sessions={s}}
  return s, layer
end
local function invoke(name, block, client, session)
  return assert(actions[name], name).run({client_id=client or 'client-1', session_id=session or 's', block_id=block}, {})
end
local function expect(name, current, destination, client, session, destination_host)
  local before, qb = #focused, #queued
  local result = invoke(name, current, client, session)
  if destination then
    assert(result.moved == true and #focused == before+1 and #queued == qb+1, vim.inspect(result))
    local f, q = focused[#focused], queued[#queued]
    assert(f.block_id == destination and (not destination_host or f.host == destination_host), vim.inspect(f))
    assert(q.session_id == f.session_id and q.window_id == 'w-'..f.session_id, vim.inspect(q))
  else
    assert(result.moved == false and #focused == before and #queued == qb, vim.inspect(result))
  end
end
local function fails(fn, fragment)
  local ok, err = pcall(fn)
  assert(not ok, 'expected failure')
  if fragment then assert(tostring(err):find(fragment, 1, true), tostring(err)) end
end
'''


@unittest.skipUnless(shutil.which('nvim') and shutil.which('chezmoi'),
                     'chezmoi and Neovim are required for Rex Lua behavioral tests')
class RexNavigation(unittest.TestCase):
    def run_lua(self, body):
        with tempfile.TemporaryDirectory(prefix='rex navigation ') as tmp:
            script = Path(tmp) / 'test.lua'
            config = Path(tmp) / 'chezmoi.toml'
            config.write_text('[data]\nhost = "mac-pro"\nrole = "pro"\nextras = ""\n')
            env = {**os.environ, 'HOME': tmp, 'XDG_CONFIG_HOME': tmp + '/config',
                   'XDG_DATA_HOME': tmp + '/data', 'XDG_STATE_HOME': tmp + '/state'}
            rendered = subprocess.check_output([
                'chezmoi', '--config', str(config), '--source', str(ROOT),
                'execute-template', '--file', str(SOURCE),
            ], env=env, text=True)
            script.write_text(HARNESS + '\n' + rendered + '\n' + body + "\nvim.cmd('qa!')\n")
            result = subprocess.run(['nvim', '--headless', '-u', 'NONE', '-n', '-l', str(script)],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_registration_and_priority(self):
        self.run_lua(r'''
assert(bindings['ctrl+b>enter'] == 'next_program')
assert(bindings['ctrl+b>ctrl+enter'] == 'next_attention')
assert(actions.next_program.title == 'Next Program by Priority' and actions.next_program.category == 'Navigation')
assert(actions.next_attention.title == 'Next Attention Needed' and actions.next_attention.category == 'Navigation')
host('local','h','s',{pane('a','working'),pane('b','done'),pane('c','blocked'),pane('d','error'),pane('e','idle')})
expect('next_program','a','c')
expect('next_program','c','b')
expect('next_program','b','d')
expect('next_program','d','e')
expect('next_attention','e',nil)
''')

    def test_sampling_shared_history_and_rearming(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked'),pane('c','working')})
expect('next_attention','a','b')
-- A queued request is not an observation; invoking again from a still chooses b.
expect('next_attention','a','b')
expect('next_program','b','c')
expect('next_attention','c',nil)
s.records.b[1].updated_at = '2026-01-01T00:00:01Z'
expect('next_attention','c','b')
expect('next_attention','b',nil)
''')

    def test_fallback_order_and_independent_clients(self):
        self.run_lua(r'''
host('local','h','s',{pane('a','idle'),pane('b','working'),pane('c','idle')})
expect('next_program','a','b','one')
expect('next_program','b','c','one')
expect('next_program','c','a','one')
expect('next_program','a','b','two')
expect('next_program','a','b','one')
''')

    def test_multiple_records_acknowledged_together(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked'),pane('c','done')})
s.records.b = {{id='root',state='blocked',updated_at='t1'}, {id='child',state='error',updated_at='t2'}}
expect('next_attention','a','b')
expect('next_attention','b','c')
expect('next_attention','c',nil)
s.records.b[2].updated_at='t3'
expect('next_attention','c','b')
''')

    def test_empty_unknown_and_excluded_panes(self):
        self.run_lua(r'''
local s, layer = host('local','h','s',{pane('a','working'),pane('empty'),pane('unknown','future'),pane('other','blocked'),pane('floating','blocked')})
layer.blocks[4].creator_name='other.creator'
local floating=table.remove(layer.blocks,5)
s.view.windows[1].layers[2]={layer_id='float',kind='floating',state='minimized',bounds={0,0,1,1},layout={rect={0,0,1,1}},blocks={floating}}
-- Detached is in the record store only, not the view.
s.records.detached={{id='root',state='blocked',updated_at='t'}}
expect('next_program','a',nil)
expect('next_attention','a',nil)
s.view.windows={}
expect('next_program','a',nil)
''')

    def test_host_identity_aliases_and_current_not_background_focus(self):
        self.run_lua(r'''
host('local','local-id','s',{pane('same','working'),pane('l','working')})
host('remote','remote-id','s',{pane('same','blocked')})
aliases.z='local'; aliases.nuc='remote'; aliases.duplicate='remote'
expect('next_attention','same','same',nil,'s','remote')
expect('next_attention','same','same',nil,'s','remote')
''')

    def test_offline_host_keeps_history_and_successful_scan_prunes(self):
        self.run_lua(r'''
host('local','local-id','s',{pane('a','working'),pane('l','working')})
local r = host('remote','remote-id','r',{pane('b','blocked')})
aliases.nuc='remote'
expect('next_attention','a','b',nil,'s','remote')
default='remote'; expect('next_attention','b',nil,nil,'r')
default='local'; failures['remote:session.list:']='offline'
expect('next_program','a','l')
assert(#warnings > 0 and warnings[#warnings][1] == 'warn')
failures['remote:session.list:']=nil
expect('next_attention','a',nil)
-- A successful scan with the pane absent discards its acknowledgement.
r.view.windows={}; expect('next_attention','a',nil)
r.view.windows={{window_id='w-r', layers={{layer_id='layer',kind='tiled',bounds={0,0,1,1},layout={rect={0,0,1,1}},blocks={{block_id='b',creator_name='com.superlogical.terminal'}}}}}}
expect('next_attention','a','b',nil,'s','remote')
''')

    def test_failures_and_inventory_immutability(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked')})
local snapshot = vim.deepcopy(s)
fails(function() actions.next_program.run({session_id='s',block_id='a'}, {}) end, 'Rex navigation requires an attached app client')
failures['local:session.list:']='unavailable'
fails(function() invoke('next_program','a') end, 'Rex navigation:')
failures['local:session.list:']=nil
s.records.b[1].updated_at=nil
fails(function() invoke('next_program','a') end)
s.records.b[1].updated_at='2026-01-01T00:00:00Z'
failures['local:session.focus_block:b']='gone'
fails(function() invoke('next_program','a') end)
assert(#queued == 0)
failures['local:session.focus_block:b']=nil
failures.queue='queue failed'
fails(function() invoke('next_program','a') end)
assert(#queued == 0)
assert(vim.deep_equal(snapshot,s), 'inventory was mutated')
''')

    def test_disappeared_pane_is_skipped(self):
        self.run_lua(r'''
host('local','h','s',{pane('a','working'),pane('b','blocked'),pane('c','done')})
failures['local:program_status:b']='block not found'
expect('next_attention','a','c')
''')

    def test_forwarding_retains_home_inventory_and_history(self):
        self.run_lua(r'''
local local_session = host('local','mac','s',{pane('a','blocked'),pane('b','working')})
host('remote','nuc','r',{pane('c','working')})
aliases.nuc='remote'
-- Acknowledging a locally persists when the selected server is forwarded.
expect('next_attention','a',nil)
default='remote'
expect('next_attention','c',nil,nil,'r')
local_session.records.a[1].updated_at='new report'
expect('next_attention','c','a',nil,'r','local')
default='local'
expect('next_attention','a',nil)
''')

    def test_transport_contract_and_failures(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked')})
expect('next_attention','a','b')
assert(#executions == 2 and executions[1].op == 'inventory' and executions[2].op == 'focus')
for _, call in ipairs(executions) do
  local argv, opts = call.argv, call.opts
  assert(argv[1]:find('Rex Server.app', 1, true) and argv[1]:find(' ', 1, true))
  assert(argv[2] == '--autostart=false' and argv[3] == '-S')
  assert(argv[4]:find(' ', 1, true) and argv[5] == '--timeout' and argv[6] == '2s')
  assert(opts.env.REX_SERVER == false and opts.env.REX_SESSION == false)
  assert(opts.env.REX_BLOCK == false and opts.env.REX_CLIENT == false)
  assert(opts.timeout == (call.op == 'inventory' and 5 or 3))
end
assert(#attachments == 2, 'subscriptions belong to helper connections')
expect('next_attention','b',nil)
assert(#executions == 3 and executions[3].op == 'inventory')
for _, kind in ipairs({'transport','timeout','exit','json'}) do
  for _, op in ipairs({'inventory','focus'}) do
    failures[kind]=op
    local start, q = #executions, #queued
    fails(function() invoke('next_program','a') end, 'Rex navigation:')
    assert(#executions == start + (op == 'focus' and 2 or 1), 'must not retry')
    assert(#queued == q)
    failures[kind]=nil
  end
end
''')

    def test_focus_revalidates_host_and_placement(self):
        self.run_lua(r'''
host('local','mac','s',{pane('a','working')})
local remote = host('remote','nuc','r',{pane('b','blocked')})
host('replacement','other','r',{pane('b','blocked')})
aliases.nuc='remote'
before_focus=function() aliases.nuc='replacement' end
fails(function() invoke('next_attention','a') end, 'Rex navigation:')
assert(#focused == 0 and #queued == 0 and #executions == 2)
aliases.nuc='remote'
before_focus=function()
  remote.view.windows[1].window_id='new-window'
end
local result = invoke('next_attention','a')
assert(result.moved and focused[#focused].block_id == 'b')
assert(queued[#queued].window_id == 'new-window')
''')

    def test_actual_embedded_source_and_parent_validation(self):
        self.run_lua(r'''
host('local','h','s',{pane('a','working'),pane('b','blocked')})
helper_transform=function(source)
  local changed, count = source:gsub('unknown operation', 'modified helper marker')
  assert(count == 1)
  return 'error("helper changed", 0)\n' .. changed
end
fails(function() invoke('next_program','a') end, 'Rex navigation:')
assert(#executions == 1 and #queued == 0)
helper_transform=nil
for _, mutate in ipairs({
  function(r) r.targets={key='not an array'} end,
  function(r) r.scanned_hosts={key='bad'} end,
  function(r) r.targets[1].session_id=nil end,
  function(r) r.targets[1].records[1].updated_at=nil end,
}) do
  response_transform=function(op, r) if op == 'inventory' then mutate(r) end; return r end
  fails(function() invoke('next_program','a') end, 'Rex navigation:')
  assert(#queued == 0)
end
response_transform=function(op, r) if op == 'focus' then r.host_id='wrong' end; return r end
fails(function() invoke('next_program','a') end, 'Rex navigation:')
assert(#queued == 0)
''')

    def test_optional_null_arrays_are_empty(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked')})
s.records.b=vim.NIL
expect('next_program','a',nil)
s.view.windows=vim.NIL
expect('next_program','a',nil)
''')

    def test_additional_host_failure_does_not_publish_partial_inventory(self):
        self.run_lua(r'''
host('local','mac','s',{pane('a','working'),pane('local-target','done')})
host('remote','nuc','r',{pane('remote-first','blocked'),pane('remote-bad','blocked')})
aliases.nuc='remote'
failures['remote:program_status:remote-bad']='connection lost'
expect('next_attention','a','local-target')
assert(#warnings > 0)
failures['remote:program_status:remote-bad']=nil
expect('next_attention','a','remote-first',nil,'s','remote')
''')

    def test_manual_intermediate_visit_is_not_sampled(self):
        self.run_lua(r'''
host('local','h','s',{pane('a','working'),pane('b','blocked'),pane('c','working')})
expect('next_attention','a','b')
-- A user may visit b manually, but there was no action invocation there.
expect('next_attention','c','b')
''')

    def test_malformed_and_disappeared_inventory_and_focus(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked')})
failures['local:server.status:']='offline'
fails(function() invoke('next_program','a') end, 'Rex navigation:')
assert(#executions == 0)
failures['local:server.status:']=nil
s.view.windows={invalid='key'}
fails(function() invoke('next_program','a') end, 'Rex navigation:')
s.view.windows={{window_id='w-s',layers={{kind='tiled',blocks={
  {block_id='a',creator_name='com.superlogical.terminal'},
  {block_id='b',creator_name='com.superlogical.terminal'},
}}}}}
s.records.b[1].id=123
fails(function() invoke('next_program','a') end, 'Rex navigation:')
s.records.b[1].id=nil
expect('next_attention','a','b')
s.records.b[1].id='root'
before_focus=function() s.view.windows={} end
local calls, q = #executions, #queued
fails(function() invoke('next_attention','a') end, 'Rex navigation:')
assert(#executions == calls+2 and #queued == q)
''')

    def test_disappeared_error_codes_and_unsupported_method(self):
        self.run_lua(r'''
local s = host('local','h','s',{pane('a','working'),pane('b','blocked'),pane('c','done')})
failures['local:program_status:b']='gone (status=404 code=not_found)'
expect('next_attention','a','c')
failures['local:session.view:s']='gone (status=404 code=session_not_found)'
expect('next_attention','a',nil)
failures['local:session.view:s']=nil
failures['local:program_status:b']='method not found (status=404 code=method_not_found)'
fails(function() invoke('next_attention','a') end, 'Rex navigation:')
failures['local:program_status:b']='block not found (status=403 code=forbidden)'
fails(function() invoke('next_attention','a') end, 'Rex navigation:')
failures['local:program_status:b']='block not found'
expect('next_attention','a','c')
''')

    def test_unsupported_method_on_remote_warns_and_is_not_scanned(self):
        self.run_lua(r'''
host('local','mac','s',{pane('a','working'),pane('local-target','done')})
host('remote','nuc','r',{pane('remote-target','blocked')})
aliases.nuc='remote'
expect('next_attention','a','remote-target',nil,'s','remote')
-- A failed scan must preserve the remote target's prior acknowledgement.
default='remote'
expect('next_attention','remote-target','local-target',nil,'r','local')
default='local'
failures['remote:program_status:remote-target']='method not found (status=404 code=method_not_found)'
expect('next_attention','a','local-target')
assert(#warnings > 0)
failures['remote:program_status:remote-target']=nil
expect('next_attention','a','local-target')
''')

    def test_fresh_load_has_no_history(self):
        body = r'''
host('local','h','s',{pane('a','working'),pane('b','blocked')})
expect('next_attention','b',nil)
expect('next_attention','a',nil)
'''
        self.run_lua(body)
        self.run_lua(r'''
host('local','h','s',{pane('a','working'),pane('b','blocked')})
expect('next_attention','a','b')
''')


if __name__ == '__main__':
    unittest.main()
