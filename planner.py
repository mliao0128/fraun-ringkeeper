"""Incremental eight-neighbor A* on the static ground map."""
import heapq
import math


def lower_bound(a, b):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


class Search:
    def __init__(self, grid, start, goal):
        self.grid = grid
        self.goal = goal
        self.cost = {start: 0.0}
        self.parent = {start: None}
        self.queue = [(lower_bound(start, goal), 0.0, start)]

    def advance(self, budget=160):
        """Return None while searching, [] on failure, or waypoints on success."""
        for _ in range(budget):
            if not self.queue:
                return []
            _, negative_cost, node = heapq.heappop(self.queue)
            cost = -negative_cost
            if cost != self.cost[node]:
                continue
            if node == self.goal:
                path = []
                while node is not None:
                    path.append(self.grid.point(node))
                    node = self.parent[node]
                return path[::-1]
            x, y = node
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (1, -1), (-1, 1), (1, 1)):
                nxt = (x + dx, y + dy)
                if not self.grid.free(nxt):
                    continue
                if dx and dy and not (self.grid.free((x + dx, y)) and self.grid.free((x, y + dy))):
                    continue
                trial = cost + (math.sqrt(2) if dx and dy else 1)
                if trial < self.cost.get(nxt, math.inf):
                    self.cost[nxt] = trial
                    self.parent[nxt] = node
                    heapq.heappush(self.queue, (trial + lower_bound(nxt, self.goal), -trial, nxt))
        return None


def nearby_goal(grid, goal, radius):
    target = grid.cell(goal)
    if grid.free(target):
        return target
    # If the exact center lies in a wall, try nearby walkable points in the ring.
    x, y = target
    for k in range(1, min(16, math.ceil(radius / grid.step)) + 1):
        border = [(x + i, y + j) for i in range(-k, k + 1) for j in (-k, k)]
        border.extend((x + i, y + j) for j in range(1 - k, k) for i in (-k, k))
        choices = [p for p in border if grid.free(p) and math.dist(grid.point(p), goal) <= radius]
        if choices:
            return min(choices, key=lambda p: math.dist(grid.point(p), goal))
    return None
