"""Official Python starter with position-based stalled-movement recovery."""
import math

import mechfight as mf
from starter import Bot as Starter


class Bot(Starter):
    name = "Fraun-Starter-Recovery"

    def __init__(self, hello):
        super().__init__(hello)
        self.radius = hello["config"]["mech"]["radius"]
        self.goal = None
        self.last_time = None
        self.detour = None
        self.side = 1

    def act(self, obs):
        action = super().act(obs)
        pos = tuple(obs["self"]["pos"][:2])
        goal = tuple(obs["zone"]["next_center"])
        now = obs["t"]
        direct = action["move"]
        # The wrapper can skip observations. A gap or a fresh destination
        # invalidates the displacement measurement from the previous command.
        if (goal != self.goal or self.last_time is None
                or not 0 < now - self.last_time <= 0.6
                or math.dist(pos, goal) <= 2 * self.radius):
            self.goal = goal
            self.last_time = now
            self.anchor, self.since = pos, now
            self.detour = None
            self.side = 1
            return action
        self.last_time = now

        if self.detour is None:
            elapsed = now - self.since
            if elapsed < 1.0:
                return action
            gain = math.dist(self.anchor, goal) - math.dist(pos, goal)
            dx, dy = pos[0] - self.anchor[0], pos[1] - self.anchor[1]
            self.anchor, self.since = pos, now
            # A useful wall slide can make little progress toward the center.
            # Let it continue while position is still changing appreciably.
            if (gain >= 0.6 * self.radius * elapsed
                    or math.hypot(dx, dy) >= 1.4 * self.radius * elapsed):
                return action
            # Continue any lateral slide the game already produced.
            lateral = -direct[1] * dx + direct[0] * dy
            if abs(lateral) > 0.4 * self.radius:
                self.side = 1 if lateral > 0 else -1
            self.detour = tuple(direct)
            self.origin, self.started = pos, now

        fx, fy = self.detour
        forward_gain = (pos[0] - self.origin[0]) * fx + (pos[1] - self.origin[1]) * fy
        if forward_gain >= 3 * self.radius or now - self.started >= 8.0:
            self.detour = None
            self.anchor, self.since = pos, now
            return action

        # Keep the sideways direction fixed as we pass the obstacle. If that
        # direction is itself blocked, try the other side.
        if now - self.since >= 1.0:
            sideways_gain = self.side * (-(pos[0] - self.anchor[0]) * fy
                                         + (pos[1] - self.anchor[1]) * fx)
            if sideways_gain < 0.4 * self.radius:
                self.side *= -1
            self.anchor, self.since = pos, now
        norm = math.hypot(0.5, 1.0)
        action["move"] = [(0.5 * fx - self.side * fy) / norm,
                          (0.5 * fy + self.side * fx) / norm]
        return action


if __name__ == "__main__":
    mf.run(Bot)
