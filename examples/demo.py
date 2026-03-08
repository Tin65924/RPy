from roblox import Instance, workspace

def create_brick(name, size):
    part = Instance.new("Part")
    part.Name = name
    part.Size = size
    part.Parent = workspace
    return part

bricks = []
for i in range(5):
    b = create_brick(f"Brick_{i}", i * 2)
    bricks.append(b)

if len(bricks) > 0:
    print("Created bricks!")
