-- Modified for Hammerspoon from
-- https://gist.github.com/iansinnott/0c9a0dcba88e6d0de0e5

local window = require "hs.window"
local screen = require "hs.screen"
boosh = {}

local function round(num, idp)
  local mult = 10^(idp or 0)
  return math.floor(num * mult + 0.5) / mult
end

-- Helper function for doing less verbose comparisons with a degree of error.
local function similar(compare, compare_to, accuracy)
  return compare >= compare_to-accuracy and compare <= compare_to+accuracy
end

-- Resize as folows:
--
-- For width:
-- if already at half width, resize to one third
-- if already one third, resize to two thirds
-- under any other circumstances resize back to half
--
-- For height:
-- Toggle between full and half height
local function resize_frame(frame, direction, screen)
  local half_width  = round(screen.w / 2)
  local third_width = round(screen.w / 3)
  local half_height = round(screen.h / 2)

  -- Left
  if direction == 'left' then

    if similar(frame.w, half_width, 2) then
      frame.w = third_width
    elseif similar(frame.w, third_width, 2) then
      frame.w = round(third_width * 2)
    else
      frame.w = half_width
    end

  -- Up
  elseif direction == 'up' then

    if similar(frame.h, screen.h, 10) then
      frame.h = half_height
    else
      frame.h = screen.h
    end

  -- Down
  elseif direction == 'down' then

    -- Toggle height
    if similar(frame.h, screen.h, 10) then
      frame.h = half_height
      frame.y = screen.y + screen.h - frame.h
    else
      frame.y = screen.y
      frame.h = screen.h
    end

  -- Right
  elseif direction == 'right' then

    -- Handle the width, just like for left
    if similar(frame.w, half_width, 5) then
      frame.w = third_width
    elseif similar(frame.w, third_width, 5) then
      frame.w = round(third_width * 2)
    else
      frame.w = half_width
    end

    -- Set the x coordinate so that the frame remains on the right side
    frame.x = math.max(round(screen.x + screen.w - frame.w), 0)

  end
end

function boosh.send_or_resize(direction)
  local win = window.focusedWindow()

  -- If no focused window, just return
  if not win then return end

  local winframe = win:frame()
  local screenframe = win:screen():frame()
  local newframe = {
    x = winframe.x,
    y = winframe.y,
    w = winframe.w,
    h = winframe.h,
  }

  -- Left
  if direction == 'left' then
    if newframe.x == screenframe.x then resize_frame(newframe, 'left', screenframe)
    else newframe.x = screenframe.x end

  -- Up
  elseif direction == 'up' then
    if newframe.y == screenframe.y then resize_frame(newframe, 'up', screenframe)
    else newframe.y = screenframe.y end

  -- Down
  elseif direction == 'down' then
    local bottom_y = screenframe.y + screenframe.h - newframe.h

    if newframe.y == bottom_y then resize_frame(newframe, 'down', screenframe)
    else newframe.y = bottom_y end

  -- Right
  elseif direction == 'right' then
    local right_x = screenframe.x + screenframe.w - newframe.w

    if newframe.x == right_x then resize_frame(newframe, 'right', screenframe)
    else newframe.x = right_x end
  end

  win:setFrame(newframe)
end

-- Generic helper function to do things with the current frame.
local function set_frame(fn)
  local win = window.focusedWindow()

  -- If no focused window, just return
  if not win then return end

  local winframe = win:frame()
  local screenframe = win:screen():frame()
  local newframe = {
    x = screenframe.x,
    y = screenframe.y,
    w = screenframe.w,
    h = screenframe.h,
  }

  fn(win, winframe, screenframe, newframe)

  win:setFrame(newframe)
end

-- Maximize the window
function boosh.maximize_window()
  set_frame(function(w, f, screenframe, newframe)
    newframe = {
      x = screenframe.x,
      y = screenframe.y,
      w = screenframe.w,
      h = screenframe.h,
    }
  end)
end
