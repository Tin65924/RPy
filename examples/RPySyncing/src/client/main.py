"""Client-side RPy script."""
from roblox import game


players = game.GetService("Players")
local_player = players.LocalPlayer
print(f"Hello, {local_player.Name}!")
