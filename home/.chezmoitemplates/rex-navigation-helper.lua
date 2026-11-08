-- This script runs in a short-lived CLI connection, never in the app client.
local terminal = "com.superlogical.terminal"
local states = { idle = true, working = true, blocked = true, done = true, error = true }

local function fail(message)
  error(message, 0)
end

local function object(value, name)
  if type(value) ~= "table" then fail(name .. " must be an object") end
  return value
end

local function required(value, name)
  if type(value) ~= "string" or value == "" then fail(name .. " must be a nonempty string") end
  return value
end

local function array(value, name)
  if value == nil or value == rex.json.null then return {} end
  if type(value) ~= "table" then fail(name .. " must be an array") end
  local count = 0
  for key in pairs(value) do
    if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
      fail(name .. " must be an array")
    end
    count = count + 1
  end
  if count ~= #value then fail(name .. " must be an array") end
  return value
end

local function call(api, method, args)
  local result, err = api.call(method, args)
  if err then fail(method .. ": " .. tostring(err)) end
  return result
end

local function disappeared(err)
  local message = tostring(err):lower()
  local code = message:match("%f[%w_]code=([%w_]+)")
  if code then return code == "not_found" or code == "session_not_found" end
  -- Older servers may omit codes; only recognize explicit resource failures.
  return message:find("block not found", 1, true) ~= nil
    or message:find("session not found", 1, true) ~= nil
end

local function status(api)
  local result = object(call(api, "server.status"), "server.status")
  return required(result.host_id, "host_id")
end

local function attach(api)
  call(api, "session.attach_all", { event_scope = "session" })
end

-- Walk only placements in the view, in the server's inventory order.
local function placements(view, visit)
  object(view, "session.view")
  for _, window in ipairs(array(view.windows, "windows")) do
    object(window, "window")
    local window_id = required(window.window_id, "window_id")
    for _, layer in ipairs(array(window.layers, "layers")) do
      object(layer, "layer")
      if not (layer.kind == "floating" and layer.state == "minimized") then
        for _, block in ipairs(array(layer.blocks, "blocks")) do
          object(block, "block")
          if block.creator_name == terminal then
            visit(required(block.block_id, "block_id"), window_id)
          end
        end
      end
    end
  end
end

local function records(api, session_id, block_id)
  local response, err = api.block.call(terminal, "program_status", {
    session_id = session_id, block_id = block_id,
  })
  if err then
    if disappeared(err) then return nil end
    fail("program_status: " .. tostring(err))
  end
  object(response, "program_status")
  local result = {}
  for _, record in ipairs(array(response.records, "records")) do
    object(record, "record")
    if states[record.state] then
      local id = record.id
      if id == nil then id = "" end
      if type(id) ~= "string" then fail("record id must be a string") end
      result[#result + 1] = {
        id = id,
        state = record.state,
        updated_at = required(record.updated_at, "record updated_at"),
      }
    end
  end
  return result
end

local function scan(api, host_id, route)
  attach(api)
  local listing = object(call(api, "session.list"), "session.list")
  local targets = {}
  for _, session in ipairs(array(listing.sessions, "sessions")) do
    object(session, "session")
    local session_id = required(session.session_id, "session_id")
    local view, err = api.call("session.view", { session_id = session_id })
    if err then
      if not disappeared(err) then fail("session.view: " .. tostring(err)) end
    else
      placements(view, function(block_id, window_id)
        local found = records(api, session_id, block_id)
        if found and #found > 0 then
          targets[#targets + 1] = {
            host_id = host_id, route = route, session_id = session_id,
            window_id = window_id, block_id = block_id, records = found,
          }
        end
      end)
    end
  end
  return targets
end

local function inventory()
  local home_host_id = status(rex)
  local targets, scanned_hosts, warnings = {}, {}, {}
  local seen = {}
  local function add(api, host_id, route)
    local found = scan(api, host_id, route)
    seen[host_id] = true
    scanned_hosts[#scanned_hosts + 1] = host_id
    for _, target in ipairs(found) do
      target.order = #targets + 1
      targets[#targets + 1] = target
    end
  end
  add(rex, home_host_id, "")
  local labels = array(rex.servers(), "servers")
  for _, label in ipairs(labels) do required(label, "server label") end
  table.sort(labels)
  for _, label in ipairs(labels) do
    local ok, err = pcall(function()
      local api = rex.server(label)
      local host_id = status(api)
      if not seen[host_id] then add(api, host_id, label) end
    end)
    if not ok then warnings[#warnings + 1] = label .. ": " .. tostring(err) end
  end
  return { home_host_id = home_host_id, targets = targets, scanned_hosts = scanned_hosts, warnings = warnings }
end

local function connected_app(client)
  return type(client) == "table" and type(client.info) == "table"
    and client.info.kind == "app"
    and (client.connection_state == nil or client.connection_state == "connected")
end

local function destination_app(api, args)
  local origin_id = required(args.origin_client_id, "origin_client_id")
  local response, err = rex.call("client.inspect", { client_id = origin_id })
  local origin = type(response) == "table" and response.client
  if err or not connected_app(origin) or origin.client_id ~= origin_id then
    fail("origin app identity is unavailable")
  end
  for _, key in ipairs({ "label", "platform", "name" }) do
    if type(origin.info[key]) ~= "string" or origin.info[key] == "" then
      fail("origin app identity is unavailable")
    end
  end
  if args.route == "" then return origin_id end
  local listing = object(call(api, "client.list"), "client.list")
  local matches = {}
  for _, client in ipairs(array(listing.clients, "clients")) do
    object(client, "client")
    if connected_app(client) and client.info.label == origin.info.label
      and client.info.platform == origin.info.platform and client.info.name == origin.info.name then
      matches[#matches + 1] = required(client.client_id, "destination client_id")
    end
  end
  if #matches == 0 then fail("destination app is not connected") end
  if #matches ~= 1 then fail("destination app identity is ambiguous") end
  return matches[1]
end

local function focus(args)
  local host_id = required(args.host_id, "host_id")
  if type(args.route) ~= "string" then fail("route must be a string") end
  local session_id = required(args.session_id, "session_id")
  required(args.window_id, "window_id")
  local block_id = required(args.block_id, "block_id")
  local api = args.route == "" and rex or rex.server(args.route)
  if status(api) ~= host_id then fail("server host_id changed") end
  local client_id = destination_app(api, args)
  attach(api)
  local view = call(api, "session.view", { session_id = session_id })
  local window_id
  placements(view, function(id, window)
    if id == block_id then window_id = window end
  end)
  if not window_id then fail("selected block is no longer placed") end
  call(api, "session.focus_block", { session_id = session_id, block_id = block_id })
  call(api, "client.perform", {
    client_id = client_id, action = "session.select",
    args = { session_id = session_id, window_id = window_id },
    origin = "key", timeout_ms = 1000,
  })
  return { host_id = host_id, session_id = session_id, window_id = window_id,
    block_id = block_id, shown = true }
end

local ok, result = pcall(function()
  local args = object(rex.args, "arguments")
  if args.op == "inventory" then return inventory() end
  if args.op == "focus" then return focus(args) end
  fail("unknown operation")
end)
if not ok then error("Rex navigation helper: " .. tostring(result), 0) end
return result
