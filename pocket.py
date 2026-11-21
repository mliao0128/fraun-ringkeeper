"""Extend the submitted controller when its sideways detour also stalls."""
import math

from recovery import Bot as SubmittedBot


class Bot(SubmittedBot):
    name = "Fraun-Pocket-Recovery"

    def __init__(self, hello):
        super().__init__(hello)
        self.escape = None

    def act(self, obs):
        previous_side = self.side
        previous_detour = self.detour
        previous_time = self.last_time
        pos = obs["self"]["pos"][:2]
        goal = tuple(obs["zone"]["next_center"])
        now = obs["t"]
        if (goal != self.goal or previous_time is None or not 0 < now - previous_time <= 0.6
                or math.dist(pos, goal) <= 2 * self.radius):
            self.escape = None
        action = super().act(obs)
        if self.escape is None:
            if previous_detour is None or self.detour is None or self.side == previous_side:
                return action
            # A forward route and the sideways slide both failed. Back out
            # diagonally until measured lateral travel shows room to go around.
            self.escape = (previous_detour, previous_side, tuple(pos), now)
            self.cleared_side = False

        (fx, fy), side, start, started = self.escape
        dx, dy = pos[0] - start[0], pos[1] - start[1]
        lateral = side * (-fy * dx + fx * dy)
        forward = fx * dx + fy * dy
        self.cleared_side |= lateral >= 3 * self.radius
        if now - started >= 12 or (self.cleared_side and forward >= 4 * self.radius):
            self.escape = self.detour = None
            self.anchor, self.since = tuple(pos), now
            angle = math.atan2(goal[1] - pos[1], goal[0] - pos[0])
            action["move"] = [math.cos(angle), math.sin(angle)]
            return action

        along = 0.8 if self.cleared_side else -1.0
        norm = math.hypot(along, 1)
        action["move"] = [(along * fx - side * fy) / norm, (along * fy + side * fx) / norm]
        return action
