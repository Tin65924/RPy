"""
sdk/roblox.py — Roblox SDK stubs for RPy.

These are THIN STUBS that exist ONLY for IDE autocomplete and type safety.
They are NEVER executed by the transpiler — `from roblox import ...` is
treated as a passthrough (the names become Luau globals).

Usage in RPy scripts:
    from roblox import Instance, Vector3, game, workspace

The transpiler strips these imports entirely; the names are assumed to
exist in the Luau runtime environment (Roblox Studio).

Stub design:
  - Classes have __init__ signatures matching Roblox constructors.
  - Methods/properties use proper return-type annotations for IDE support.
  - No real logic — all methods return NotImplemented or raise.
"""

from __future__ import annotations
from typing import Any, Optional, List, Union, overload


# ---------------------------------------------------------------------------
# Marker — signals to type checkers that this package is typed
# ---------------------------------------------------------------------------

__all__ = [
    # Core globals
    "game", "workspace", "script",
    # Datatypes
    "Instance", "Vector3", "Vector2", "CFrame",
    "Color3", "BrickColor", "UDim", "UDim2",
    "Enum", "EnumItem",
    "Ray", "Region3", "Rect",
    "NumberRange", "NumberSequence", "ColorSequence",
    "TweenInfo",
    # Services (class names, usable as types)
    "Players",
    "RunService", "TweenService", "UserInputService",
    "ReplicatedStorage", "ServerStorage", "ServerScriptService",
    "StarterGui", "StarterPack", "StarterPlayer",
    "Lighting", "SoundService", "Chat",
    "DataStoreService", "MessagingService",
    "MarketplaceService", "BadgeService",
    "PhysicsService", "CollectionService",
    "HttpService", "TeleportService",
    "Teams", "TextService", "GuiService",
    "ContextActionService", "HapticService",
    "PathfindingService", "ProximityPromptService",
    # Roblox global functions (that don't shadow Python builtins)
    "warn", "typeof",
    "wait", "delay", "spawn", "tick", "time",
    "require", "tostring", "tonumber",
    "pcall", "xpcall", "select", "unpack",
    "next", "pairs", "ipairs", "rawget", "rawset",
    "setmetatable", "getmetatable",
    "task", "coroutine", "debug",
    # Events
    "RBXScriptSignal", "RBXScriptConnection",
]


# ===========================================================================
# Core data types
# ===========================================================================

class Vector3:
    """Represents a 3D vector."""
    X: float
    Y: float
    Z: float
    Magnitude: float
    Unit: "Vector3"

    zero: "Vector3"
    one: "Vector3"
    xAxis: "Vector3"
    yAxis: "Vector3"
    zAxis: "Vector3"

    def __init__(self, x: float = 0, y: float = 0, z: float = 0) -> None: ...
    def __add__(self, other: "Vector3") -> "Vector3": ...
    def __sub__(self, other: "Vector3") -> "Vector3": ...
    def __mul__(self, other: Union[float, "Vector3"]) -> "Vector3": ...
    def __div__(self, other: Union[float, "Vector3"]) -> "Vector3": ...
    def __neg__(self) -> "Vector3": ...
    def Dot(self, other: "Vector3") -> float: ...
    def Cross(self, other: "Vector3") -> "Vector3": ...
    def Lerp(self, goal: "Vector3", alpha: float) -> "Vector3": ...
    def FuzzyEq(self, other: "Vector3", epsilon: float = ...) -> bool: ...

    @staticmethod
    def new(x: float = 0, y: float = 0, z: float = 0) -> "Vector3": ...


class Vector2:
    """Represents a 2D vector."""
    X: float
    Y: float
    Magnitude: float
    Unit: "Vector2"

    zero: "Vector2"
    one: "Vector2"

    def __init__(self, x: float = 0, y: float = 0) -> None: ...
    def __add__(self, other: "Vector2") -> "Vector2": ...
    def __sub__(self, other: "Vector2") -> "Vector2": ...
    def __mul__(self, other: Union[float, "Vector2"]) -> "Vector2": ...
    def Dot(self, other: "Vector2") -> float: ...
    def Cross(self, other: "Vector2") -> float: ...
    def Lerp(self, goal: "Vector2", alpha: float) -> "Vector2": ...

    @staticmethod
    def new(x: float = 0, y: float = 0) -> "Vector2": ...


class CFrame:
    """Represents a coordinate frame (position + rotation)."""
    Position: Vector3
    LookVector: Vector3
    UpVector: Vector3
    RightVector: Vector3
    X: float
    Y: float
    Z: float

    identity: "CFrame"

    def __init__(self, *args: Any) -> None: ...
    def __mul__(self, other: Union["CFrame", Vector3]) -> Union["CFrame", Vector3]: ...
    def __add__(self, other: Vector3) -> "CFrame": ...
    def __sub__(self, other: Vector3) -> "CFrame": ...
    def Inverse(self) -> "CFrame": ...
    def Lerp(self, goal: "CFrame", alpha: float) -> "CFrame": ...
    def ToWorldSpace(self, cf: "CFrame") -> "CFrame": ...
    def ToObjectSpace(self, cf: "CFrame") -> "CFrame": ...
    def PointToWorldSpace(self, v: Vector3) -> Vector3: ...
    def PointToObjectSpace(self, v: Vector3) -> Vector3: ...
    def GetComponents(self) -> tuple: ...

    @staticmethod
    def new(*args: Any) -> "CFrame": ...
    @staticmethod
    def lookAt(pos: Vector3, lookAt: Vector3, up: Optional[Vector3] = None) -> "CFrame": ...
    @staticmethod
    def Angles(rx: float, ry: float, rz: float) -> "CFrame": ...
    @staticmethod
    def fromEulerAnglesXYZ(rx: float, ry: float, rz: float) -> "CFrame": ...


class Color3:
    """Represents an RGB color."""
    R: float
    G: float
    B: float

    def __init__(self, r: float = 0, g: float = 0, b: float = 0) -> None: ...
    def Lerp(self, goal: "Color3", alpha: float) -> "Color3": ...
    def ToHSV(self) -> tuple: ...

    @staticmethod
    def new(r: float = 0, g: float = 0, b: float = 0) -> "Color3": ...
    @staticmethod
    def fromRGB(r: int, g: int, b: int) -> "Color3": ...
    @staticmethod
    def fromHSV(h: float, s: float, v: float) -> "Color3": ...
    @staticmethod
    def fromHex(hex: str) -> "Color3": ...


class BrickColor:
    """Legacy color system."""
    Name: str
    Number: int
    Color: Color3
    r: float
    g: float
    b: float

    def __init__(self, val: Union[str, int] = ...) -> None: ...

    @staticmethod
    def new(val: Union[str, int] = ...) -> "BrickColor": ...
    @staticmethod
    def Random() -> "BrickColor": ...


class UDim:
    """Represents a one-dimensional UI dimension."""
    Scale: float
    Offset: int

    def __init__(self, scale: float = 0, offset: int = 0) -> None: ...

    @staticmethod
    def new(scale: float = 0, offset: int = 0) -> "UDim": ...


class UDim2:
    """Represents a two-dimensional UI dimension."""
    X: UDim
    Y: UDim
    Width: UDim
    Height: UDim

    def __init__(self, *args: Any) -> None: ...
    def Lerp(self, goal: "UDim2", alpha: float) -> "UDim2": ...

    @staticmethod
    def new(*args: Any) -> "UDim2": ...
    @staticmethod
    def fromScale(x: float, y: float) -> "UDim2": ...
    @staticmethod
    def fromOffset(x: int, y: int) -> "UDim2": ...


class Ray:
    """Represents a ray with origin and direction."""
    Origin: Vector3
    Direction: Vector3
    Unit: "Ray"

    def __init__(self, origin: Vector3 = ..., direction: Vector3 = ...) -> None: ...
    def ClosestPoint(self, point: Vector3) -> Vector3: ...
    def Distance(self, point: Vector3) -> float: ...

    @staticmethod
    def new(origin: Vector3 = ..., direction: Vector3 = ...) -> "Ray": ...


class Region3:
    """Represents a 3D region."""
    CFrame: CFrame
    Size: Vector3

    def __init__(self, min: Vector3 = ..., max: Vector3 = ...) -> None: ...
    def ExpandToGrid(self, resolution: float) -> "Region3": ...

    @staticmethod
    def new(min: Vector3 = ..., max: Vector3 = ...) -> "Region3": ...


class Rect:
    """Represents a 2D rectangle."""
    Min: Vector2
    Max: Vector2
    Width: float
    Height: float

    def __init__(self, *args: Any) -> None: ...

    @staticmethod
    def new(*args: Any) -> "Rect": ...


class NumberRange:
    Min: float
    Max: float
    def __init__(self, min: float = 0, max: float = ...) -> None: ...
    @staticmethod
    def new(min: float = 0, max: float = ...) -> "NumberRange": ...


class NumberSequence:
    Keypoints: list
    def __init__(self, *args: Any) -> None: ...
    @staticmethod
    def new(*args: Any) -> "NumberSequence": ...


class ColorSequence:
    Keypoints: list
    def __init__(self, *args: Any) -> None: ...
    @staticmethod
    def new(*args: Any) -> "ColorSequence": ...


class TweenInfo:
    """Describes how a tween should animate."""
    Time: float
    EasingStyle: Any
    EasingDirection: Any
    RepeatCount: int
    Reverses: bool
    DelayTime: float

    def __init__(
        self,
        time: float = 1,
        easingStyle: Any = ...,
        easingDirection: Any = ...,
        repeatCount: int = 0,
        reverses: bool = False,
        delayTime: float = 0,
    ) -> None: ...

    @staticmethod
    def new(
        time: float = 1,
        easingStyle: Any = ...,
        easingDirection: Any = ...,
        repeatCount: int = 0,
        reverses: bool = False,
        delayTime: float = 0,
    ) -> "TweenInfo": ...


# ===========================================================================
# Enum system
# ===========================================================================

class EnumItem:
    """A single enum value."""
    Name: str
    Value: int
    EnumType: "EnumType"

class EnumType:
    """A group of enum items."""
    def GetEnumItems(self) -> list: ...

class _Enum:
    """Root Enum namespace — Enum.KeyCode.W, Enum.EasingStyle.Quad, etc."""
    # Common enum groups (attributes are EnumType)
    KeyCode: Any
    UserInputType: Any
    EasingStyle: Any
    EasingDirection: Any
    Material: Any
    PartType: Any
    SurfaceType: Any
    Font: Any
    TextXAlignment: Any
    TextYAlignment: Any
    SortOrder: Any
    FillDirection: Any
    HorizontalAlignment: Any
    VerticalAlignment: Any
    ScaleType: Any
    SizeConstraint: Any
    AutomaticSize: Any
    HumanoidStateType: Any
    RenderPriority: Any
    PlaybackState: Any
    ProductType: Any
    AnimationPriority: Any

    def __getattr__(self, name: str) -> Any: ...

Enum = _Enum()


# ===========================================================================
# Instance — the base class for all Roblox objects
# ===========================================================================

class Instance:
    """Base class for all Roblox objects."""
    Name: str
    ClassName: str
    Parent: Optional["Instance"]
    Archivable: bool

    def __init__(self, className: str = ..., parent: Optional["Instance"] = None) -> None: ...

    # Hierarchy
    def FindFirstChild(self, name: str, recursive: bool = False) -> Optional["Instance"]: ...
    def FindFirstChildOfClass(self, className: str) -> Optional["Instance"]: ...
    def FindFirstChildWhichIsA(self, className: str, recursive: bool = False) -> Optional["Instance"]: ...
    def FindFirstAncestor(self, name: str) -> Optional["Instance"]: ...
    def FindFirstAncestorOfClass(self, className: str) -> Optional["Instance"]: ...
    def FindFirstAncestorWhichIsA(self, className: str) -> Optional["Instance"]: ...
    def GetChildren(self) -> list: ...
    def GetDescendants(self) -> list: ...
    def IsA(self, className: str) -> bool: ...
    def IsDescendantOf(self, ancestor: "Instance") -> bool: ...
    def IsAncestorOf(self, descendant: "Instance") -> bool: ...
    def WaitForChild(self, name: str, timeout: float = ...) -> "Instance": ...

    # Lifecycle
    def Clone(self) -> "Instance": ...
    def Destroy(self) -> None: ...
    def ClearAllChildren(self) -> None: ...

    # Attributes
    def GetAttribute(self, name: str) -> Any: ...
    def SetAttribute(self, name: str, value: Any) -> None: ...
    def GetAttributes(self) -> dict: ...

    # Tags
    def HasTag(self, tag: str) -> bool: ...
    def AddTag(self, tag: str) -> None: ...
    def RemoveTag(self, tag: str) -> None: ...
    def GetTags(self) -> list: ...

    # Events (RBXScriptSignal)
    ChildAdded: Any
    ChildRemoved: Any
    Destroying: Any
    AttributeChanged: Any

    # Catch-all for dynamic properties
    def __getattr__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any) -> None: ...

    @staticmethod
    def new(className: str, parent: Optional["Instance"] = None) -> "Instance": ...


# ===========================================================================
# Events
# ===========================================================================

class RBXScriptConnection:
    Connected: bool
    def Disconnect(self) -> None: ...

class RBXScriptSignal:
    def Connect(self, callback: Any) -> RBXScriptConnection: ...
    def Once(self, callback: Any) -> RBXScriptConnection: ...
    def Wait(self) -> Any: ...


# ===========================================================================
# Services (accessed via game:GetService("Name"))
# ===========================================================================

class _DataModel(Instance):
    """The root `game` object."""
    def GetService(self, serviceName: str) -> Any: ...
    PlaceId: int
    GameId: int
    JobId: str


class _Workspace(Instance):
    """The workspace service."""
    Gravity: float
    CurrentCamera: Any
    def Raycast(self, origin: Vector3, direction: Vector3, params: Any = ...) -> Any: ...
    def GetPartBoundsInBox(self, cframe: CFrame, size: Vector3, params: Any = ...) -> list: ...
    def GetPartBoundsInRadius(self, position: Vector3, radius: float, params: Any = ...) -> list: ...


class Players(Instance):
    LocalPlayer: Any  # Player instance on client
    MaxPlayers: int
    def GetPlayers(self) -> list: ...
    def GetPlayerByUserId(self, userId: int) -> Optional[Any]: ...
    def GetPlayerFromCharacter(self, character: Instance) -> Optional[Any]: ...
    PlayerAdded: RBXScriptSignal
    PlayerRemoving: RBXScriptSignal


class RunService(Instance):
    def IsClient(self) -> bool: ...
    def IsServer(self) -> bool: ...
    def IsStudio(self) -> bool: ...
    Heartbeat: RBXScriptSignal
    RenderStepped: RBXScriptSignal
    Stepped: RBXScriptSignal


class TweenService(Instance):
    def Create(self, instance: Instance, tweenInfo: TweenInfo, properties: dict) -> Any: ...


class UserInputService(Instance):
    MouseEnabled: bool
    TouchEnabled: bool
    KeyboardEnabled: bool
    GamepadEnabled: bool
    def IsKeyDown(self, keyCode: Any) -> bool: ...
    def GetMouseLocation(self) -> Vector2: ...
    InputBegan: RBXScriptSignal
    InputEnded: RBXScriptSignal
    InputChanged: RBXScriptSignal


class ReplicatedStorage(Instance):
    pass


class ServerStorage(Instance):
    pass


class ServerScriptService(Instance):
    pass


class StarterGui(Instance):
    def SetCoreGuiEnabled(self, coreGuiType: Any, enabled: bool) -> None: ...


class StarterPack(Instance):
    pass


class StarterPlayer(Instance):
    pass


class Lighting(Instance):
    ClockTime: float
    Brightness: float
    Ambient: Color3
    OutdoorAmbient: Color3
    FogEnd: float
    FogStart: float
    FogColor: Color3
    TimeOfDay: str


class SoundService(Instance):
    pass


class Chat(Instance):
    pass


class DataStoreService(Instance):
    def GetDataStore(self, name: str, scope: str = ...) -> Any: ...
    def GetOrderedDataStore(self, name: str, scope: str = ...) -> Any: ...
    def GetGlobalDataStore(self) -> Any: ...


class MessagingService(Instance):
    def SubscribeAsync(self, topic: str, callback: Any) -> Any: ...
    def PublishAsync(self, topic: str, message: Any) -> None: ...


class MarketplaceService(Instance):
    def PromptPurchase(self, player: Any, assetId: int) -> None: ...
    def PromptGamePassPurchase(self, player: Any, gamePassId: int) -> None: ...
    def UserOwnsGamePassAsync(self, userId: int, gamePassId: int) -> bool: ...
    def GetProductInfo(self, assetId: int) -> dict: ...
    PromptPurchaseFinished: RBXScriptSignal


class BadgeService(Instance):
    def AwardBadge(self, userId: int, badgeId: int) -> bool: ...
    def UserHasBadgeAsync(self, userId: int, badgeId: int) -> bool: ...
    def GetBadgeInfoAsync(self, badgeId: int) -> dict: ...


class PhysicsService(Instance):
    pass


class CollectionService(Instance):
    def GetTagged(self, tag: str) -> list: ...
    def HasTag(self, instance: Instance, tag: str) -> bool: ...
    def AddTag(self, instance: Instance, tag: str) -> None: ...
    def RemoveTag(self, instance: Instance, tag: str) -> None: ...
    def GetInstanceAddedSignal(self, tag: str) -> RBXScriptSignal: ...
    def GetInstanceRemovedSignal(self, tag: str) -> RBXScriptSignal: ...


class HttpService(Instance):
    def JSONEncode(self, data: Any) -> str: ...
    def JSONDecode(self, json: str) -> Any: ...
    def GenerateGUID(self, wrapInCurlyBraces: bool = True) -> str: ...
    def GetAsync(self, url: str) -> str: ...
    def PostAsync(self, url: str, data: str, contentType: Any = ...) -> str: ...


class TeleportService(Instance):
    def Teleport(self, placeId: int, player: Any = ...) -> None: ...
    def TeleportToPlaceInstance(self, placeId: int, instanceId: str, player: Any = ...) -> None: ...


class Teams(Instance):
    def GetTeams(self) -> list: ...


class TextService(Instance):
    def GetTextSize(self, text: str, fontSize: int, font: Any, frameSize: Vector2) -> Vector2: ...
    def FilterStringAsync(self, stringToFilter: str, fromUserId: int) -> Any: ...


class GuiService(Instance):
    pass


class ContextActionService(Instance):
    def BindAction(self, actionName: str, callback: Any, createTouchButton: bool, *inputTypes: Any) -> None: ...
    def UnbindAction(self, actionName: str) -> None: ...


class HapticService(Instance):
    def IsVibrationSupported(self, inputType: Any) -> bool: ...
    def SetMotor(self, inputType: Any, motor: Any, value: float) -> None: ...


class PathfindingService(Instance):
    def CreatePath(self, agentParameters: dict = ...) -> Any: ...


class ProximityPromptService(Instance):
    PromptTriggered: RBXScriptSignal
    PromptButtonHoldBegan: RBXScriptSignal
    PromptButtonHoldEnded: RBXScriptSignal


# ===========================================================================
# Global singletons
# ===========================================================================

game: _DataModel = _DataModel()  # type: ignore
workspace: _Workspace = _Workspace()  # type: ignore
script: Instance = Instance()  # type: ignore


# ===========================================================================
# Roblox global functions (stubs)
# ===========================================================================

def wait(seconds: float = ...) -> tuple: ...
def delay(delayTime: float, callback: Any) -> None: ...
def spawn(callback: Any) -> None: ...
def tick() -> float: ...
def time() -> float: ...
def require(module: Any) -> Any: ...
def typeof(value: Any) -> str: ...
def warn(*args: Any) -> None: ...
def tostring(value: Any) -> str: ...
def tonumber(value: Any, base: int = ...) -> Optional[float]: ...
def pcall(func: Any, *args: Any) -> tuple: ...
def xpcall(func: Any, handler: Any, *args: Any) -> tuple: ...
def select(index: Any, *args: Any) -> Any: ...
def unpack(list: Any, i: int = ..., j: int = ...) -> Any: ...
def next(table: Any, index: Any = ...) -> Any: ...
def pairs(table: Any) -> Any: ...
def ipairs(table: Any) -> Any: ...
def rawget(table: Any, index: Any) -> Any: ...
def rawset(table: Any, index: Any, value: Any) -> None: ...
def setmetatable(table: Any, metatable: Any) -> Any: ...
def getmetatable(table: Any) -> Any: ...


# ===========================================================================
# Roblox standard libraries (stub namespaces)
# ===========================================================================

class _task:
    @staticmethod
    def wait(duration: float = ...) -> float: ...
    @staticmethod
    def spawn(callback: Any, *args: Any) -> Any: ...
    @staticmethod
    def delay(duration: float, callback: Any, *args: Any) -> Any: ...
    @staticmethod
    def defer(callback: Any, *args: Any) -> Any: ...
    @staticmethod
    def cancel(thread: Any) -> None: ...

task = _task()


class _coroutine:
    @staticmethod
    def create(func: Any) -> Any: ...
    @staticmethod
    def resume(co: Any, *args: Any) -> tuple: ...
    @staticmethod
    def yield_(*args: Any) -> Any: ...
    @staticmethod
    def wrap(func: Any) -> Any: ...
    @staticmethod
    def status(co: Any) -> str: ...
    @staticmethod
    def close(co: Any) -> tuple: ...

coroutine = _coroutine()


class _debug:
    @staticmethod
    def traceback(message: str = ..., level: int = ...) -> str: ...
    @staticmethod
    def info(level: int, options: str) -> Any: ...
    @staticmethod
    def profilebegin(label: str) -> None: ...
    @staticmethod
    def profileend() -> None: ...

debug = _debug()
