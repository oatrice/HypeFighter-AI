--[[
  =============================================================================
  FrameWhisper: Ikemen GO Lua Telemetry & Combat Micro-Event Bridge
  =============================================================================
  Streams 60 FPS fighter telemetry and combat micro-events via UDP to agent-core.
  Compatible with Ikemen GO (macOS / Linux / Windows).
--]]

local bridge = {}

local socket_ok, socket = pcall(require, "socket")

-- Configuration
bridge.config = {
    host = "127.0.0.1",
    port = 9999,
    enabled = true,
    debug = false
}

local udp = nil
local frame_counter = 0
local prev_state = nil

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

-- Safely retrieve player property across Ikemen GO API variations
local function get_prop(p, field, getter_name, default_val)
    if not p then return default_val end
    if getter_name and type(p[getter_name]) == "function" then
        local ok, res = pcall(p[getter_name], p)
        if ok and res ~= nil then return res end
    end
    if p[field] ~= nil then
        return p[field]
    end
    return default_val
end

-- Initialize UDP socket
function bridge.init(opts)
    opts = opts or {}
    if opts.host then bridge.config.host = opts.host end
    if opts.port then bridge.config.port = opts.port end
    if opts.enabled ~= nil then bridge.config.enabled = opts.enabled end
    if opts.debug ~= nil then bridge.config.debug = opts.debug end

    if not socket_ok then
        if bridge.config.debug then
            print("[FrameWhisper Bridge] LuaSocket not found. Running in offline/simulation mode.")
        end
        return false
    end

    udp = socket.udp()
    if udp then
        udp:setpeername(bridge.config.host, bridge.config.port)
        udp:settimeout(0) -- Non-blocking
        if bridge.config.debug then
            print(string.format("[FrameWhisper Bridge] UDP connected to %s:%d", bridge.config.host, bridge.config.port))
        end
        return true
    end
    return false
end

-- Extract normalized character telemetry
function bridge.extract_player_state(p, id)
    if not p then return nil end

    local pos_x = get_prop(p, "x", "pos_x", 0)
    local pos_y = get_prop(p, "y", "pos_y", 0)
    if type(p.pos) == "table" then
        pos_x = p.pos.x or pos_x
        pos_y = p.pos.y or pos_y
    end

    local life = get_prop(p, "life", "getLife", 1000)
    local life_max = get_prop(p, "lifeMax", "getLifeMax", 1000)
    local power = get_prop(p, "power", "getPower", 0)
    local power_max = get_prop(p, "powerMax", "getPowerMax", 3000)
    local facing = get_prop(p, "facing", "getFacing", id == 1 and 1 or -1)
    local stateno = get_prop(p, "stateno", "getStateNo", 0)
    local movetype = get_prop(p, "movetype", "getMoveType", "I")
    local ctrl = get_prop(p, "ctrl", "getCtrl", false)
    local invincible = get_prop(p, "invincible", "isInvincible", false)
    local armor = get_prop(p, "armor", "hasArmor", false)

    return {
        id = id,
        life = tonumber(life) or 0,
        life_max = tonumber(life_max) or 1000,
        power = tonumber(power) or 0,
        power_max = tonumber(power_max) or 3000,
        pos = {
            x = tonumber(pos_x) or 0,
            y = tonumber(pos_y) or 0
        },
        facing = tonumber(facing) or 1,
        stateno = tonumber(stateno) or 0,
        movetype = tostring(movetype):upper(), -- "I" (idle), "A" (attack), "H" (hit/hurt)
        ctrl = not not ctrl,
        invincible = not not invincible,
        armor = not not armor
    }
end

-- Spatial safe-zone evaluation:
-- Returns true if AI (p1) is behind the attacking opponent (p2) relative to p2's attack direction.
function bridge.evaluate_safe_zone(p1, p2)
    if not p1 or not p2 then return false end
    
    local p2_attacking = (p2.movetype == "A")
    if not p2_attacking then return false end

    -- Opponent facing Right (1) while AI is behind them on the Left (p1.pos.x < p2.pos.x)
    if p2.facing == 1 and (p1.pos.x < p2.pos.x) then
        return true
    end

    -- Opponent facing Left (-1) while AI is behind them on the Right (p1.pos.x > p2.pos.x)
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

    -- 1. WHIFF_DETECTED: Opponent was attacking last frame, now finished, without hitting P1
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

    -- 2. DAMAGE_TAKEN: Life dropped while entering or in Hurt state ("H")
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

    -- 3. BLOCK_STRING: P1 is guarding against incoming pressure (stateno 120-155)
    local is_guard_state = (p1_curr.stateno >= 120 and p1_curr.stateno <= 155)
    if is_guard_state and (p2_curr.movetype == "A" or p2_prev.movetype == "A") then
        events[#events + 1] = {
            type = "BLOCK_STRING",
            defender = "p1",
            attacker = "p2",
            stateno = p1_curr.stateno,
            frame = current.frame,
            timestamp_ms = current.timestamp_ms
        }
    end

    return events
end

-- Main tick function: invoke once per game loop tick (60 FPS)
function bridge.tick(p1_raw, p2_raw, engine_meta)
    if not bridge.config.enabled then return nil end

    frame_counter = frame_counter + 1
    local now_ms = socket_ok and math.floor(socket.gettime() * 1000) or math.floor(os.clock() * 1000)

    local p1 = bridge.extract_player_state(p1_raw, 1)
    local p2 = bridge.extract_player_state(p2_raw, 2)

    if not p1 or not p2 then return nil end

    local distance = math.abs(p1.pos.x - p2.pos.x)
    local safe_back_zone = bridge.evaluate_safe_zone(p1, p2)

    local snapshot = {
        frame = frame_counter,
        timestamp_ms = now_ms,
        distance = distance,
        safe_back_zone = safe_back_zone,
        p1 = p1,
        p2 = p2,
        meta = engine_meta or {}
    }

    -- Micro-events detection
    local events = bridge.detect_micro_events(snapshot, prev_state)
    snapshot.events = events
    prev_state = snapshot

    -- Stream snapshot via UDP
    if udp then
        local payload = to_json(snapshot)
        udp:send(payload)
    end

    return snapshot
end

return bridge
