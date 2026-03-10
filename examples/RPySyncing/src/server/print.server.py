from roblox import game

part = Instance.new("Part")
part.Transparency = 0.5
part.Color = Color3.new(1, 0, 0)
part.Parent = game.Workspace
part.Position = Vector3.new(0, 10, 0)
part.Anchored = True

def onHit(hit):
    print(f"I was touched by {hit.Name}")

part.Touched.Connect(onHit)