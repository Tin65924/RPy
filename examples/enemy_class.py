"""RPy Example: Enemy class with inheritance."""
from roblox import Instance, Vector3


class Entity:
    """Base class for all game entities."""

    def __init__(self, name, health):
        self.name = name
        self.health = health
        self.max_health = health
        self.alive = True

    def take_damage(self, amount):
        self.health = self.health - amount
        if self.health <= 0:
            self.health = 0
            self.alive = False
            self.on_death()

    def heal(self, amount):
        self.health = self.health + amount
        if self.health > self.max_health:
            self.health = self.max_health

    def on_death(self):
        print(f"{self.name} has died!")


class Enemy(Entity):
    """An enemy entity with attack power and loot."""

    def __init__(self, name, health, damage):
        self.name = name
        self.health = health
        self.max_health = health
        self.alive = True
        self.damage = damage
        self.loot = []

    def add_loot(self, item):
        self.loot.append(item)

    def attack(self, target):
        if self.alive:
            target.take_damage(self.damage)
            print(f"{self.name} attacks {target.name} for {self.damage} damage!")

    def drop_loot(self):
        if len(self.loot) > 0:
            print(f"{self.name} drops:")
            for item in self.loot:
                print(f"  - {item}")
        return self.loot


# Create enemies
zombie = Enemy("Zombie", 50, 10)
zombie.add_loot("Rotten Flesh")
zombie.add_loot("Gold Coin")

skeleton = Enemy("Skeleton", 30, 15)
skeleton.add_loot("Bone")
skeleton.add_loot("Arrow")

# Simulate combat
hero = Entity("Hero", 100)
zombie.attack(hero)
skeleton.attack(hero)

print(f"Hero health: {hero.health}/{hero.max_health}")

# Defeat zombie
zombie.take_damage(50)
items = zombie.drop_loot()
