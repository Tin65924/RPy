"""RPy Example: Iterating over players."""
from roblox import game


def greet_players():
    """Print a greeting for each player in the server."""
    players_service = game.GetService("Players")
    player_list = players_service.GetPlayers()

    for i in range(len(player_list)):
        player = player_list[i]
        print(f"Welcome, {player.Name}!")

    print(f"Total players: {len(player_list)}")


greet_players()
