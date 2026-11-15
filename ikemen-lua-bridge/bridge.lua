--[[
  =============================================================================
  FrameWhisper: Ikemen GO Lua Telemetry & Combat Micro-Event Bridge
  =============================================================================
  Streams 60 FPS fighter telemetry, camera stats, and combat micro-events.
  Receives bidirectional FighterAction commands to drive AI.
  Compatible with Ikemen GO (macOS / Linux / Windows).
--]]

local bridge = {}

local socket_ok, socket = pcall(require, "socket")

-- Configuration
bridge.config = {
    host = "127.0.0.1",
    telemetry_port = 9999,
    input_port = 9998,
    telemetry_file = "/tmp/framewhisper_telemetry.json",
    action_file = "/tmp/framewhisper_action.json",
    enabled = true,
    debug = true
}

local telemetry_udp = nil
local input_udp = nil
local frame_counter = 0
local prev_state = nil
bridge.latest_action = nil

-- Simple JSON encoder to eliminate external dependencies
local function to_json(val)
    local t = type(val)
    if t == "table" then
        local is_array = true
        local n = 0
        for k, _ in pairs(val) do
            n = n + 1
            if type(k) ~= "number" or k ~= n then
                is_array = false
                break
            end
        end
        local parts = {}
        if is_array then
            for i = 1, #val do
                parts[#parts + 1] = to_json(val[i])
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(val) do
                parts[#parts + 1] = string.format("%q:%s", tostring(k), to_json(v))
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    elseif t == "string" then
        return string.format("%q", val)
    elseif t == "number" or t == "boolean" then
        return tostring(val)
    elseif t == "nil" then
        return "null"
    else
        return string.format("%q", tostring(val))
    end
end

-- Initialize UDP sockets or fallback IPC files
function bridge.init(opts)
    opts = opts or {}
    if opts.host then bridge.config.host = opts.host end
    if opts.telemetry_port then bridge.config.telemetry_port = opts.telemetry_port end
    if opts.port then bridge.config.telemetry_port = opts.port end
    if opts.input_port then bridge.config.input_port = opts.input_port end
    if opts.enabled ~= nil then bridge.config.enabled = opts.enabled end
    if opts.debug ~= nil then bridge.config.debug = opts.debug end

    if socket_ok and socket and socket.udp then
        telemetry_udp = socket.udp()
        if telemetry_udp then
            telemetry_udp:setpeername(bridge.config.host, bridge.config.telemetry_port)
            telemetry_udp:settimeout(0)
        end

        input_udp = socket.udp()
        if input_udp then
            input_udp:setsockname(bridge.config.host, bridge.config.input_port)
            input_udp:settimeout(0)
        end
        if bridge.config.debug then
            print(string.format("[FrameWhisper Bridge] Initialized UDP on %s (Tele:%d, In:%d)", bridge.config.host, bridge.config.telemetry_port, bridge.config.input_port))
        end
    else
        if bridge.config.debug then
            print("[FrameWhisper Bridge] Using high-speed IPC file streaming fallback: " .. bridge.config.telemetry_file)
        end
    end

    return true
end

-- Parse action JSON
local function parse_action_json(str)
    if not str or str == "" then return nil end
    local action = {}

    local dir = str:match('"dir"%s*:%s*"([^"]+)"')
    if dir then action.dir = dir end

    local btn = str:match('"btn"%s*:%s*"([^"]+)"')
    if btn then action.btn = btn end

    local h_axis = str:match('"h_axis"%s*:%s*(-?%d+)')
    if h_axis then action.h_axis = tonumber(h_axis) end

    local f_lock = str:match('"f_lock"%s*:%s*(%a+)')
    if f_lock then action.f_lock = (f_lock == "true") end

    local reaction = str:match('"reaction"%s*:%s*"([^"]+)"')
    if reaction then action.reaction = reaction end

    return action
end

-- Poll incoming action commands
function bridge.poll_inputs()
    if input_udp then
        while true do
            local data, err = input_udp:receive()
            if not data then break end
            local action = parse_action_json(data)
            if action then bridge.latest_action = action end
        end
    else
        -- Fallback: check action IPC file
        local f = io.open(bridge.config.action_file, "r")
        if f then
            local content = f:read("*a")
            f:close()
            local action = parse_action_json(content)
            if action then bridge.latest_action = action end
        end
    end
    return bridge.latest_action
end

-- Apply action to player
function bridge.apply_input(p_id, action)
    if not action then return end

    local oldid = id and id() or 0
    if player and player(p_id) then
        local dir = action.dir
        local fwd = (dir == "FORWARD" or dir == "UP_FORWARD" or dir == "DOWN_FORWARD")
        local back = (dir == "BACK" or dir == "UP_BACK" or dir == "DOWN_BACK")
        local up = (dir == "UP" or dir == "UP_FORWARD" or dir == "UP_BACK")
        local down = (dir == "DOWN" or dir == "DOWN_FORWARD" or dir == "DOWN_BACK")

        if action.f_lock and fwd then
            fwd = false -- Safety Lock enforced
        end

        local btn = action.btn
        local btn_x = (btn == "LP")
        local btn_y = (btn == "MP")
        local btn_z = (btn == "HP")
        local btn_a = (btn == "LK")
        local btn_b = (btn == "MK")
        local btn_c = (btn == "HK")

        if setCommand then
            if btn_z then setCommand("z") end
            if btn_x then setCommand("x") end
            if fwd then setCommand("holdfwd") end
            if back then setCommand("holdback") end
        end

        playerId(oldid)
    end
end

-- Safely extract player properties using Ikemen GO context pattern
function bridge.extract_player_by_id(p_id)
    local oldid = id and id() or 0
    if player and player(p_id) then
        local p_x = posX and posX() or 0
        local p_y = posY and posY() or 0
        local p_life = life and life() or 1000
        local p_life_max = lifeMax and lifeMax() or 1000
        local p_power = power and power() or 0
        local p_power_max = powerMax and powerMax() or 3000
        local p_facing = facing and facing() or (p_id == 1 and 1 or -1)
        local p_stateno = stateNo and stateNo() or 0
        local p_movetype = moveType and tostring(moveType()):upper() or "I"
        local p_ctrl = ctrl and (ctrl() == 1 or ctrl() == true) or false

        playerId(oldid)

        return {
            id = p_id,
            life = tonumber(p_life) or 0,
            life_max = tonumber(p_life_max) or 1000,
            power = tonumber(p_power) or 0,
            power_max = tonumber(p_power_max) or 3000,
            pos = {
                x = tonumber(p_x) or 0,
                y = tonumber(p_y) or 0
            },
            facing = tonumber(p_facing) or 1,
            stateno = tonumber(p_stateno) or 0,
            movetype = p_movetype,
            ctrl = p_ctrl,
            invincible = false,
            armor = false
        }
    end
    return nil
end

-- Safely extract camera metrics directly from Ikemen GO engine
function bridge.extract_camera_metrics()
    local cam_x = cameraPosX and cameraPosX() or 0
    local cam_y = cameraPosY and cameraPosY() or 0
    local cam_zoom = cameraZoom and cameraZoom() or 1.0

    return {
        x = tonumber(cam_x) or 0,
        y = tonumber(cam_y) or 0,
        zoom = tonumber(cam_zoom) or 1.0
    }
end

-- Spatial safe-zone evaluation:
function bridge.evaluate_safe_zone(p1, p2)
    if not p1 or not p2 then return false end
    local p2_attacking = (p2.movetype == "A")
    if not p2_attacking then return false end

    if p2.facing == 1 and (p1.pos.x < p2.pos.x) then
        return true
    end
    if p2.facing == -1 and (p1.pos.x > p2.pos.x) then
        return true
    end
    return false
end

-- Detect structured combat micro-events between frame transitions
function bridge.detect_micro_events(current, previous)
    local events = {}
    if not previous or not current then return events end

    local p1_curr = current.p1
    local p2_curr = current.p2
    local p1_prev = previous.p1
    local p2_prev = previous.p2

    if not p1_curr or not p2_curr or not p1_prev or not p2_prev then
        return events
    end

    if p2_prev.movetype == "A" and p2_curr.movetype ~= "A" and p1_curr.movetype ~= "H" then
        events[#events + 1] = {
            type = "WHIFF_DETECTED",
            actor = "p2",
            target = "p1",
            stateno = p2_prev.stateno,
            frame = current.frame,
            timestamp_ms = current.timestamp_ms
        }
    end

    if p1_curr.life < p1_prev.life and p1_curr.movetype == "H" then
        events[#events + 1] = {
            type = "DAMAGE_TAKEN",
            target = "p1",
            amount = p1_prev.life - p1_curr.life,
            remaining_life = p1_curr.life,
            frame = current.frame,
            timestamp_ms = current.timestamp_ms
        }
    end

    return events
end

-- Main tick function: invoke once per game loop tick (60 FPS)
function bridge.tick(p1_arg, p2_arg, engine_meta)
    if not bridge.config.enabled then return nil end

    -- 1. Poll incoming actions & apply to P1
    local action = bridge.poll_inputs()
    if action then
        bridge.apply_input(1, action)
    end

    frame_counter = frame_counter + 1
    local now_ms = socket_ok and math.floor(socket.gettime() * 1000) or math.floor(os.clock() * 1000)

    -- 2. Extract P1 and P2 states using player context switching
    local p1 = bridge.extract_player_by_id(1)
    local p2 = bridge.extract_player_by_id(2)

    if not p1 or not p2 then return nil end

    -- 3. Extract real-time camera tracking and zoom metrics
    local camera = bridge.extract_camera_metrics()

    local distance = math.abs(p1.pos.x - p2.pos.x)
    local safe_back_zone = bridge.evaluate_safe_zone(p1, p2)

    local snapshot = {
        frame = frame_counter,
        timestamp_ms = now_ms,
        distance = distance,
        safe_back_zone = safe_back_zone,
        p1 = p1,
        p2 = p2,
        camera = camera,
        meta = engine_meta or {}
    }

    local events = bridge.detect_micro_events(snapshot, prev_state)
    snapshot.events = events
    prev_state = snapshot

    -- Output formatted live telemetry line to stdout every 30 frames
    if frame_counter % 30 == 0 or (camera.zoom < 0.95 or camera.y < -30) then
        print(string.format(
            "[FW Live] Frame:%05d | P1_Y:%6.1f | P2_Y:%6.1f | Cam_Y:%6.1f | Zoom:%4.2fx",
            frame_counter, p1.pos.y, p2.pos.y, camera.y, camera.zoom
        ))
    end

    -- 4. Stream snapshot via UDP or write atomic IPC file
    local payload = to_json(snapshot)
    if telemetry_udp then
        telemetry_udp:send(payload)
    end

    local f = io.open(bridge.config.telemetry_file, "w")
    if f then
        f:write(payload)
        f:close()
    end

    return snapshot
end

return bridge
