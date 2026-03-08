"""RPy Example: Spawning parts in the workspace."""
from roblox import Instance, workspace, Vector3


def spawn_part(position, color):
    """Create a new Part at the given position with a color."""
    part = Instance.new("Part")
    part.Size = Vector3.new(4, 1, 2)
    part.Position = position
    part.BrickColor = color
    part.Anchored = True
    part.Parent = workspace
    return part


# Create a row of 10 parts
for i in range(10):
    pos = Vector3.new(i * 5, 10, 0)
    spawn_part(pos, "Bright blue")
    print(f"Spawned part {i}")
