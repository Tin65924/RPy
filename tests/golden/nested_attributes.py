from roblox import game, workspace

# Static calls (depth 1 or namespaced)
plrs = game.GetService("Players")
part = workspace.Raycast(Vector3.new(0,0,0), Vector3.new(0,-10,0))

# Nested attribute signals/methods
player = game.Players.LocalPlayer
character = player.Character
character.Humanoid.TakeDamage(10)

# Nested signal
workspace.Baseplate.Touched.Connect(lambda: print("Baseplate touched"))
