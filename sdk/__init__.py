"""
RPy Roblox SDK stubs — thin pass-body wrappers for IDE support only.

Usage:
    from roblox import Instance, Vector3, game, workspace

These stubs are purely for IDE autocomplete. The transpiler strips
all `from roblox import ...` statements and treats the names as Luau globals.
"""

# Re-export everything for IDE use
from sdk.roblox import (  # noqa: F401
    # Core globals
    game, workspace, script,
    # Datatypes
    Instance, Vector3, Vector2, CFrame,
    Color3, BrickColor, UDim, UDim2,
    Enum, EnumItem,
    Ray, Region3, Rect,
    NumberRange, NumberSequence, ColorSequence,
    TweenInfo,
    # Services
    Players,
    RunService, TweenService, UserInputService,
    ReplicatedStorage, ServerStorage, ServerScriptService,
    StarterGui, StarterPack, StarterPlayer,
    Lighting, SoundService, Chat,
    DataStoreService, MessagingService,
    MarketplaceService, BadgeService,
    PhysicsService, CollectionService,
    HttpService, TeleportService,
    Teams, TextService, GuiService,
    ContextActionService, HapticService,
    PathfindingService, ProximityPromptService,
    # Events
    RBXScriptSignal, RBXScriptConnection,
    # Utilities
    task, coroutine, debug,
)
