local alert = require "hs.alert"
local application = require "hs.application"
local fnutils = require "hs.fnutils"
local grid = require "hs.grid"
local hints = require "hs.hints"
local hotkey = require "hs.hotkey"
local window = require "hs.window"
require "boosh"

hints.showTitleThresh = 0

grid.setMargins({w = 0, h = 0})

local meta = {"cmd", "ctrl"}

-- Reload automatically on config changes
hs.pathwatcher.new(os.getenv("HOME") .. "/.hammerspoon/", hs.reload):start()
hs.alert.show("Hail Hydra", 1)

-- Window hints
hotkey.bind(meta, "f", hs.hints.windowHints)

-- Move focus between windows
hotkey.bind(meta, ",", function() window.focusedWindow():focusWindowWest(true) end)
hotkey.bind(meta, ".", function() window.focusedWindow():focusWindowEast(true) end)

-- Move windows between screens
hotkey.bind(meta, "n", grid.pushWindowNextScreen)

-- Push or resize the window in a direction
hotkey.bind(meta, "h", function() boosh.send_or_resize("left") end)
hotkey.bind(meta, "j", function() boosh.send_or_resize("down") end)
hotkey.bind(meta, "k", function() boosh.send_or_resize("up") end)
hotkey.bind(meta, "l", function() boosh.send_or_resize("right") end)
hotkey.bind(meta, "m", grid.maximizeWindow)

-- Launch or focus applications
fnutils.each(
   {
      {key = "b", app = "google chrome"},
      {key = "e", app = "emacs"},
      {key = "l", app = "slack"},
      {key = "s", app = "spotify"},
      {key = "t", app = "iterm"},
   }, function(object)
      hotkey.bind({"command"}, object.key, function() application.launchOrFocus(object.app) end)
end)
