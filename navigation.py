"""Waypoint steering for the Mech Royale movement protocol."""

import math
import random


class Navigator:
    def __init__(self, seed):
        self.side = random.Random(seed).choice((-1, 1))
        self.sprinting = False
        self._reset()

    def _reset(self):
        self.sample = None
        self.mode = "direct"
        self.until = 0.0
        self.failures = 0
        self.clear_windows = 0
        self.flipped = False

    def _progress(self, now, x, y, dx, dy, speed, grounded, energy):
        if self.mode != "direct" and now >= self.until:
            self.mode = "direct"
            self.sample = None

        if self.sample is not None:
            then, sx, sy, ux, uy, expected = self.sample
            elapsed = now - then
            # A changed waypoint or a gap in observations invalidates this sample.
            if elapsed < 0 or elapsed > 2 or dx * ux + dy * uy < 0.65:
                self._reset()
            elif elapsed >= 0.8:
                self.sample = None
                if self.mode == "direct":
                    advance = (x - sx) * ux + (y - sy) * uy
                    if advance < min(2.5, expected * elapsed * 0.23):
                        self.failures += 1
                        self.clear_windows = 0
                        if self.failures == 1 and grounded and energy > 0.45:
                            self.mode = "climb"
                            self.until = now + 2.2
                        else:
                            # Keep the same side on successive attempts so a wide
                            # obstacle does not make us oscillate about its middle.
                            self.mode = "detour"
                            self.until = now + min(6.0, 1.0 + self.failures)
                            self.flipped = False
                    else:
                        self.clear_windows += 1
                        if self.clear_windows >= 3:
                            self.failures = 0
                elif self.mode == "detour" and not self.flipped:
                    if math.hypot(x - sx, y - sy) < 1.0:
                        self.side *= -1
                        self.flipped = True

        if self.sample is None:
            self.sample = (now, x, y, dx, dy, speed)

    def steer(self, obs, goal, *, hurry=False, hold_radius=1.5):
        """Approach the horizontal waypoint, or stand still inside its hold radius."""
        mech = obs["self"]
        x, y = mech["pos"][:2]
        dx, dy = goal[0] - x, goal[1] - y
        distance = math.hypot(dx, dy)
        if distance <= max(hold_radius, 0.001):
            self._reset()
            self.sprinting = False
            return {"move": [0.0, 0.0], "boost": False, "jump": False}

        dx, dy = dx / distance, dy / distance
        now = obs["t"]
        stats = mech["stats"]
        walk = max(0.1, stats["walk_speed"])
        # Ease into the hold region instead of sprinting through it.
        scale = min(1.0, (distance - 0.6 * hold_radius) / (0.38 * walk))
        energy = mech["energy"] / max(1.0, mech["max_energy"])
        grounded = mech["grounded"]
        self._progress(now, x, y, dx, dy, walk * scale, grounded, energy)

        if self.mode == "detour":
            # The slight forward component keeps the mech sliding around a corner.
            lateral = self.side * 0.96
            dx, dy = 0.28 * dx - lateral * dy, 0.28 * dy + lateral * dx
            scale = 1.0

        jump = self.mode == "climb" and grounded and now < self.until - 1.85
        if self.mode == "climb":
            self.sprinting = False
            boost = energy > 0.2 and (jump or not grounded)
        else:
            if not hurry or not grounded or distance < max(9.0, hold_radius + 5.0):
                self.sprinting = False
            elif energy >= 0.80:
                self.sprinting = True
            elif energy <= 0.35:
                self.sprinting = False
            boost = self.sprinting

        return {"move": [dx * scale, dy * scale], "boost": boost, "jump": jump}
