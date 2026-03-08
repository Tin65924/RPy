"""RPy Example: NPC movement with patrol points."""
from roblox import Instance, workspace, Vector3


class NPC:
    """Simple NPC that patrols between waypoints."""

    def __init__(self, name, speed):
        self.name = name
        self.speed = speed
        self.health = 100
        self.waypoints = []
        self.current_index = 0

        # Create the physical model
        self.model = Instance.new("Model")
        self.model.Name = name
        self.model.Parent = workspace

    def add_waypoint(self, position):
        """Add a patrol waypoint."""
        self.waypoints.append(position)

    def take_damage(self, amount):
        """Apply damage to this NPC."""
        self.health = self.health - amount
        if self.health <= 0:
            self.health = 0
            print(f"{self.name} has been defeated!")

    def is_alive(self):
        return self.health > 0

    def get_next_waypoint(self):
        """Get the next patrol destination."""
        if len(self.waypoints) == 0:
            return None
        wp = self.waypoints[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.waypoints)
        return wp


# Create an NPC with a patrol route
guard = NPC("Guard", 16)
guard.add_waypoint(Vector3.new(0, 0, 0))
guard.add_waypoint(Vector3.new(50, 0, 0))
guard.add_waypoint(Vector3.new(50, 0, 50))
guard.add_waypoint(Vector3.new(0, 0, 50))

# Simulate patrol
for step in range(8):
    wp = guard.get_next_waypoint()
    print(f"{guard.name} moving to waypoint {step}")
