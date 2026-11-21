"""Conservative 2-D walkability grid for the game's static obstacle footprints."""
from array import array
from collections import defaultdict
import json
import math
from pathlib import Path
import sys


class Grid:
    def __init__(self, bounds, clearance):
        self.x0, self.y0 = bounds["minX"], bounds["minY"]
        width = bounds["maxX"] - self.x0
        height = bounds["maxY"] - self.y0
        if min(width, height) <= 0 or clearance < 0:
            raise ValueError("invalid arena bounds or clearance")
        self.step = 2.0 if max(width, height) <= 350 else 4.0
        self.nx, self.ny = math.ceil(width / self.step), math.ceil(height / self.step)
        self.blocked = bytearray(self.nx * self.ny)
        # Complete cells must fit within the arena after allowing for body radius.
        for j in range(self.ny):
            if j * self.step < clearance or (j + 1) * self.step > height - clearance:
                self._fill(j, 0, self.nx - 1)
            else:
                self._fill(j, 0, math.ceil(clearance / self.step) - 1)
                self._fill(j, math.floor((width - clearance) / self.step), self.nx - 1)

    @classmethod
    def from_hello(cls, hello, clearance=None):
        root = Path(hello["map"]["dir"]) / "v2"
        world = json.loads((root / "world.json").read_bytes())
        stats = hello["config"]["mech"]
        radius = stats["radius"] if clearance is None else clearance
        grid = cls(world["bounds"], radius)
        for prism in world.get("prisms", []):
            # Treat bridges and above-ground prisms as blocked on this ground layer.
            grid._prism(prism, radius)
        if world.get("terrain", {}).get("file"):
            grid._terrain(root, world["terrain"], stats["max_slope_deg"])
        return grid

    def cell(self, pos):
        return (math.floor((pos[0] - self.x0) / self.step),
                math.floor((pos[1] - self.y0) / self.step))

    def point(self, cell):
        return (self.x0 + (cell[0] + 0.5) * self.step,
                self.y0 + (cell[1] + 0.5) * self.step)

    def free(self, cell):
        i, j = cell
        return 0 <= i < self.nx and 0 <= j < self.ny and not self.blocked[j * self.nx + i]

    def _fill(self, j, first, last):
        first, last = max(first, 0), min(last, self.nx - 1)
        if first <= last:
            self.blocked[j*self.nx + first:j*self.nx + last + 1] = b"\x01" * (last-first+1)

    def _span(self, j, left, right):
        first = math.ceil((left - self.x0) / self.step - 0.5)
        last = math.floor((right - self.x0) / self.step - 0.5)
        self._fill(j, first, last)

    def _prism(self, prism, clearance):
        crossings = defaultdict(list)
        # Half a cell diagonal covers the whole cell, plus clearance for
        # the character and a small margin for waypoint tracking error.
        pad = self.step / math.sqrt(2) + clearance + 0.45
        for ring in (prism["ring"], *prism.get("holes", [])):
            if len(ring) < 6:
                continue
            ax, ay = ring[-2:]
            for bx, by in zip(ring[::2], ring[1::2]):
                dx, dy = bx - ax, by - ay
                low, high = sorted((ay, by))
                j0 = max(0, self.cell((0, low - pad))[1])
                j1 = min(self.ny - 1, self.cell((0, high + pad))[1])
                for j in range(j0, j1 + 1):
                    y = self.y0 + (j + 0.5) * self.step
                    if low <= y < high:
                        crossings[j].append(ax + dx * ((y - ay) / dy))
                    # Conservative square dilation: bound segment x anywhere
                    # in this row's vertical band, then expand horizontally.
                    if y + pad < low or y - pad > high:
                        continue
                    if dy:
                        t0, t1 = sorted(((y - pad - ay) / dy, (y + pad - ay) / dy))
                        x0, x1 = ax + dx * max(0, t0), ax + dx * min(1, t1)
                    else:
                        x0, x1 = ax, bx
                    self._span(j, min(x0, x1) - pad, max(x0, x1) + pad)
                ax, ay = bx, by
        # Even/odd fill handles holes independently of winding order.
        for j, xs in crossings.items():
            xs.sort()
            for left, right in zip(xs[::2], xs[1::2]):
                self._span(j, left, right)

    def _terrain(self, root, terrain, max_slope):
        heights = array("h")
        heights.frombytes((root / terrain["file"]).read_bytes())
        if sys.byteorder != "little":
            heights.byteswap()
        cols, rows = terrain["nx"], terrain["ny"]
        if len(heights) != cols * rows or min(cols, rows) < 3:
            raise ValueError("terrain dimensions do not match height data")
        spacing = terrain["step"]
        limit = 2 * spacing * math.tan(math.radians(max_slope)) / terrain["scale"]
        # Approximate the local gradient at cell centers. Small ledges and
        # elevation-dependent passages need the existing movement fallback.
        xcols = [min(cols-2, max(1, round((self.point((i, 0))[0] - terrain["minX"]) / spacing)))
                 for i in range(self.nx)]
        for j in range(self.ny):
            y = self.point((0, j))[1]
            row = min(rows-2, max(1, round((y - terrain["minY"]) / spacing)))
            for i, col in enumerate(xcols):
                index = row*cols + col
                dx = heights[index+1] - heights[index-1]
                dy = heights[index+cols] - heights[index-cols]
                if dx * dx + dy * dy > limit * limit:
                    self.blocked[j*self.nx+i] = 1

    def clear(self, a, b):
        """Traverse all cells on the segment, checking both sides at corners."""
        i, j = self.cell(a)
        end = self.cell(b)
        if not self.free((i, j)) or not self.free(end):
            return False
        dx, dy = b[0] - a[0], b[1] - a[1]
        on_x_edge = not dx and abs(self.x0 + i*self.step - a[0]) < 1e-9
        on_y_edge = not dy and abs(self.y0 + j*self.step - a[1]) < 1e-9
        if (on_x_edge and not self.free((i-1, j))
                or on_y_edge and not self.free((i, j-1))
                or on_x_edge and on_y_edge and not self.free((i-1, j-1))):
            return False
        si, sj = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
        tx = (self.x0 + (i + (si > 0)) * self.step - a[0]) / dx if dx else math.inf
        ty = (self.y0 + (j + (sj > 0)) * self.step - a[1]) / dy if dy else math.inf
        dtx = self.step / abs(dx) if dx else math.inf
        dty = self.step / abs(dy) if dy else math.inf
        while (i, j) != end:
            # Stop advancing a dimension after it reaches the endpoint cell,
            # including endpoints exactly on a grid corner.
            xt = tx if i != end[0] else math.inf
            yt = ty if j != end[1] else math.inf
            if abs(xt - yt) <= 1e-10:
                if not self.free((i+si, j)) or not self.free((i, j+sj)):
                    return False
                i, j = i+si, j+sj
                tx, ty = tx+dtx, ty+dty
            elif xt < yt:
                i, tx = i+si, tx+dtx
            else:
                j, ty = j+sj, ty+dty
            if (not self.free((i, j)) or on_x_edge and not self.free((i-1, j))
                    or on_y_edge and not self.free((i, j-1))):
                return False
        return True
