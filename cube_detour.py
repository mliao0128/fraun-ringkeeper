"""Movement-only overlay for Fraun's 1.58 recovery controller."""
import math

from bot import Bot as Recovery
import mechfight as mf


class Bot(Recovery):
    name = "Fraun-Safe-Cube-Detour"

    def __init__(self, hello):
        super().__init__(hello)
        self.until = 0
        self.target = None
        self.cooldown = 0

    def act(self, obs):
        action = super().act(obs)
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        pos = me["pos"]
        walk = me["stats"]["walk_speed"]
        margin = 2 * me["stats"]["radius"]

        def safe(xy):
            return (math.dist(xy, zone["center"]) <= zone["radius"] - margin
                    and math.dist(xy, zone["next_center"]) <= zone["next_radius"] - margin)

        old = self.target
        choices = []
        if me["in_zone"] and safe(pos[:2]) and now >= self.cooldown:
            for c in obs["cubes"]:
                if old is not None and (c["id"] != old or now >= self.until):
                    continue
                p = c["pos"]
                dist = math.dist(p[:2], pos[:2])
                if not 0 < dist <= 1.5 * walk or abs(p[2] - pos[2]) > 4 or not safe(p[:2]):
                    continue
                # Allow time for a round trip plus one second to rejoin the route.
                if now + 2 * dist / walk + 1 < zone["shrink_end"]:
                    choices.append((dist, c["id"], p))
        if not choices:
            if old is not None:
                self.target, self.cooldown = None, now + 1
            return action
        dist, self.target, p = min(choices)
        if old is None:
            self.until = now + 2
        action["move"] = [(p[i] - pos[i]) / dist for i in range(2)]
        return action


if __name__ == "__main__":
    mf.run(Bot)
