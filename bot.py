"""Follow an A* ground route, retaining the current bot as fallback."""
import math

import mechfight as mf
from current import Bot as Current
from grid import Grid
from pace import adjust_pace
from planner import Search, nearby_goal


class Bot(Current):
    name = "Fraun-AStar"

    def __init__(self, hello, clearance=None):
        super().__init__(hello)
        try:
            self.grid = Grid.from_hello(hello, clearance=clearance)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            mf.log(f"Ground map unavailable: {exc}")
            self.grid = None
        self.destination = None
        self.search = None
        self.path = []
        self.retry_at = 0
        self.progress_time = None

    def movement(self, obs):
        grid = self.grid
        pos = tuple(obs["self"]["pos"][:2])
        zone = obs["zone"]
        goal = tuple(zone["next_center"])
        now = obs["t"]
        destination = (goal, zone["next_radius"])
        if destination != self.destination:
            self.destination = destination
            self.search, self.path = None, []
            self.retry_at = now
            self.progress_time = None
        if grid.clear(pos, goal):
            self.search, self.path = None, []
            self.progress_time = None
            return None
        if now < self.retry_at or not grid.free(grid.cell(pos)):
            return None
        if self.search is None and not self.path:
            end = nearby_goal(grid, goal, zone["next_radius"])
            if end is None:
                self.retry_at = now + 2
                return None
            self.search = Search(grid, grid.cell(pos), end)
        if self.search is not None:
            path = self.search.advance()
            if path is None:
                return None
            self.search, self.path = None, path
            if not path:
                self.retry_at = now + 2
                return None
        # Pick the furthest currently visible waypoint in a short section of
        # the route. Recheck line of travel from the actual moving position.
        for i in range(min(14, len(self.path)) - 1, -1, -1):
            waypoint = self.path[i]
            if grid.clear(pos, waypoint):
                del self.path[:i]
                break
        else:
            self.path = []
            self.retry_at = now + 0.3
            return None
        distance = math.dist(pos, waypoint)
        if distance < 0.5:
            self.path.pop(0)
            return None
        if self.progress_time is None or now < self.progress_time:
            self.progress_pos, self.progress_time = pos, now
        elif now - self.progress_time >= 1.2:
            stalled = math.dist(self.progress_pos, pos) < self.radius
            self.progress_pos, self.progress_time = pos, now
            if stalled:
                self.path = []
                self.retry_at = now + 1.5
                return None
        return [(waypoint[0] - pos[0]) / distance, (waypoint[1] - pos[1]) / distance]

    def act(self, obs):
        action = super().act(obs)
        direction = self.movement(obs) if self.grid is not None else None
        if direction is not None:
            action["move"] = direction
            action["boost"] = not obs["self"]["in_zone"]
            adjust_pace(obs, action)
        return action


if __name__ == "__main__":
    mf.run(Bot)
