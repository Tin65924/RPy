-- RPy Studio Plugin (v0.3.0)
-- Native syncing for Python -> Roblox development.

local HttpService = game:GetService("HttpService")
local Selection = game:GetService("Selection")
local ChangeHistoryService = game:GetService("ChangeHistoryService")

local SERVER_URL = "http://127.0.0.1:8000"
local POLL_INTERVAL = 0.1

local pluginName = "RPy Sync"
local toolbar = plugin:CreateToolbar(pluginName)
local syncButton = toolbar:CreateButton("Toggle Sync", "Enable/Disable RPy Live Sync", "rbxassetid://4458901886")

-- UI Components
local interface = plugin:CreateDockWidgetPluginGui(
    "RPySyncGui",
    DockWidgetPluginGuiInfo.new(
        Enum.InitialDockState.Right,
        false, -- Initial enabled
        false, -- Override previous enabled state
        250, 400, -- Size
        200, 300  -- Min size
    )
)
interface.Title = "RPy Sync Panel"

local container = Instance.new("Frame")
container.Size = UDim2.fromScale(1, 1)
container.BackgroundColor3 = Color3.fromRGB(24, 24, 27)
container.BorderSizePixel = 0
container.Parent = interface

-- Status Header
local statusHeader = Instance.new("Frame")
statusHeader.Size = UDim2.new(1, -20, 0, 40)
statusHeader.Position = UDim2.fromOffset(10, 10)
statusHeader.BackgroundColor3 = Color3.fromRGB(39, 39, 42)
statusHeader.Parent = container

local statusDot = Instance.new("Frame")
statusDot.Size = UDim2.fromOffset(12, 12)
statusDot.Position = UDim2.new(0, 10, 0.5, -6)
statusDot.BackgroundColor3 = Color3.fromRGB(239, 68, 68) -- Red (Inactive)
statusDot.Parent = statusHeader

local statusLabel = Instance.new("TextLabel")
statusLabel.Size = UDim2.new(1, -35, 1, 0)
statusLabel.Position = UDim2.fromOffset(30, 0)
statusLabel.BackgroundTransparency = 1
statusLabel.Text = "Disconnected"
statusLabel.TextColor3 = Color3.fromRGB(228, 228, 231)
statusLabel.TextXAlignment = Enum.TextXAlignment.Left
statusLabel.Font = Enum.Font.SourceSansBold
statusLabel.TextSize = 14
statusLabel.Parent = statusHeader

-- Sync Activity
local activityList = Instance.new("ScrollingFrame")
activityList.Size = UDim2.new(1, -20, 1, -120)
activityList.Position = UDim2.fromOffset(10, 60)
activityList.BackgroundColor3 = Color3.fromRGB(18, 18, 21)
activityList.BorderSizePixel = 0
activityList.ScrollBarThickness = 4
activityList.Parent = container

local lastSyncedLabel = Instance.new("TextLabel")
lastSyncedLabel.Size = UDim2.new(1, -20, 0, 20)
lastSyncedLabel.Position = UDim2.fromOffset(10, -30)
lastSyncedLabel.Position = UDim2.new(0, 10, 1, -100)
lastSyncedLabel.BackgroundTransparency = 1
lastSyncedLabel.Text = "Last synced: Never"
lastSyncedLabel.TextColor3 = Color3.fromRGB(161, 161, 170)
lastSyncedLabel.TextSize = 12
lastSyncedLabel.Parent = container

-- Toggle Overwrite
local overwriteEnabled = true
local toggleBtn = Instance.new("TextButton")
toggleBtn.Size = UDim2.new(1, -20, 0, 30)
toggleBtn.Position = UDim2.new(0, 10, 1, -40)
toggleBtn.BackgroundColor3 = Color3.fromRGB(59, 130, 246)
toggleBtn.Text = "Auto-Overwrite: ON"
toggleBtn.TextColor3 = Color3.fromRGB(255, 255, 255)
toggleBtn.Font = Enum.Font.SourceSansBold
toggleBtn.Parent = container

toggleBtn.MouseButton1Click:Connect(function()
    overwriteEnabled = not overwriteEnabled
    toggleBtn.Text = "Auto-Overwrite: " .. (overwriteEnabled and "ON" or "OFF")
    toggleBtn.BackgroundColor3 = overwriteEnabled and Color3.fromRGB(59, 130, 246) or Color3.fromRGB(82, 82, 91)
end)

-- Core Sync Logic
local isSyncing = false
local lastEventId = 0

local SERVICE_MAP = {
    workspace = game.Workspace,
    replicatedstorage = game:GetService("ReplicatedStorage"),
    serverscriptservice = game:GetService("ServerScriptService"),
    starterplayerscripts = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts") or game:GetService("StarterPlayer"),
    lighting = game:GetService("Lighting"),
    startergui = game:GetService("StarterGui"),
}

local function getContainerForPath(relPath)
    relPath = relPath:gsub("\\", "/"):lower()
    local segments = string.split(relPath, "/")
    local root = segments[1]
    
    if SERVICE_MAP[root] then
        return SERVICE_MAP[root]
    end
    
    -- Backward compatibility for v1.0 structures
    if root == "server" then return game:GetService("ServerScriptService") end
    if root == "client" then 
        local sp = game:GetService("StarterPlayer")
        return sp:FindFirstChild("StarterPlayerScripts") or sp
    end
    if root == "shared" then return game:GetService("ReplicatedStorage") end

    -- Default to ServerStorage/RPyUnknown for isolation
    local unknownRoot = game:GetService("ServerStorage"):FindFirstChild("RPyUnknown")
    if not unknownRoot then
        unknownRoot = Instance.new("Folder")
        unknownRoot.Name = "RPyUnknown"
        unknownRoot.Parent = game:GetService("ServerStorage")
    end
    return unknownRoot
end

local function syncFile(path, event, config)
    local code = event.code
    local scriptType = event.script_type
    local eventType = event.type or "update"
    
    local parent = getContainerForPath(path)
    if not parent then return end
    
    -- Normalize path for segments
    path = path:gsub("\\", "/")
    
    -- Split path into segments
    local segments = {}
    for segment in path:gmatch("[^/]+") do
        table.insert(segments, segment)
    end
    
    -- Handle subfolders
    for i = 1, #segments - 1 do
        local folderName = segments[i]
        local existingFolder = parent:FindFirstChild(folderName)
        if not existingFolder then
            existingFolder = Instance.new("Folder")
            existingFolder.Name = folderName
            existingFolder.Parent = parent
        end
        parent = existingFolder
    end
    
    local fileName = segments[#segments]
    local name = fileName:gsub("%.py$", ""):gsub("%.server$", ""):gsub("%.client$", "")
    
    local existing = parent:FindFirstChild(name)
    
    -- Handle Deletion
    if eventType == "delete" then
        if existing then
            existing:Destroy()
            return true
        end
        return false
    end
    
    -- Handle Update/Create
    local className = "ModuleScript"
    if scriptType == "server" then
        className = "Script"
    elseif scriptType == "client" then
        className = "LocalScript"
    end
    
    local scriptObj = existing
    if existing then
        if not overwriteEnabled then return end
        
        -- Backup logic
        if config and config.flags and config.flags.backup_studio then
            local backupFolder = game:GetService("ServerStorage"):FindFirstChild("RPy_Backups")
            if not backupFolder then
                backupFolder = Instance.new("Folder")
                backupFolder.Name = "RPy_Backups"
                backupFolder.Parent = game:GetService("ServerStorage")
            end
            local backup = existing:Clone()
            backup.Name = name .. "_" .. os.date("%H%M%S")
            backup.Parent = backupFolder
        end

        if existing.ClassName ~= className then
            existing:Destroy()
            scriptObj = nil
        elseif className == "ModuleScript" then
            scriptObj = existing:Clone()
            existing:Destroy()
            scriptObj.Parent = parent
            
            -- Notify game runtime VM of hot reload
            local rs = game:GetService("ReplicatedStorage")
            local ev = rs:FindFirstChild("RPyHotReloadEvent")
            if ev and ev:IsA("BindableEvent") then
                local module_path = path:gsub("%.[pylua]+$", ""):gsub("\\", "/")
                ev:Fire(module_path)
                ev:Fire(module_path:gsub("/", "."))
            end
        end
    end
    
    scriptObj = scriptObj or Instance.new(className)
    scriptObj.Name = name
    scriptObj.Source = code or ""
    scriptObj.Parent = parent
    
    return true
end

local function poll()
    if not isSyncing then 
        statusLabel.Text = "Sync Disabled"
        statusDot.BackgroundColor3 = Color3.fromRGB(82, 82, 91) -- Gray
        return 
    end
    
    local success, response = pcall(function()
        return HttpService:GetAsync(SERVER_URL .. "/sync?after=" .. lastEventId)
    end)
    
    if success then
        local decodeSuccess, responseData = pcall(function()
            return HttpService:JSONDecode(response)
        end)
        
        if not decodeSuccess then
            statusLabel.Text = "JSON Decode Error"
            statusDot.BackgroundColor3 = Color3.fromRGB(249, 115, 22) -- Orange
            return
        end
        
        -- Handle forced resync
        if responseData.resync then
            lastEventId = 0
            poll() -- retry immediately with 0
            return
        end
        
        lastEventId = responseData.latest_event_id
        local config = responseData.config
        
        local syncCount = 0
        for _, event in ipairs(responseData.events) do
            if syncFile(event.path, event, config) then
                syncCount = syncCount + 1
            end
        end
        
        if syncCount > 0 then
            lastSyncedLabel.Text = "Last synced: " .. os.date("%H:%M:%S")
            ChangeHistoryService:SetWaypoint("RPy Sync: " .. syncCount .. " files")
        end
        
        statusLabel.Text = "Connected"
        statusDot.BackgroundColor3 = Color3.fromRGB(34, 197, 94) -- Green
    else
        statusLabel.Text = "Offline (Check Output)"
        statusDot.BackgroundColor3 = Color3.fromRGB(239, 68, 68) -- Red
        warn("[RPy Sync Error]: " .. tostring(response))
    end
end

syncButton.Click:Connect(function()
    isSyncing = not isSyncing
    interface.Enabled = isSyncing
    syncButton:SetActive(isSyncing)
end)

task.spawn(function()
    while true do
        poll()
        task.wait(POLL_INTERVAL)
    end
end)

print("RPy Sync Plugin Loaded.")
