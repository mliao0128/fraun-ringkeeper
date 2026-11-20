"""Short-lived cube memory, two-stop route choices, and collection energy management."""
import math


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def circle_at(zone, now, ahead):
    """The reported circle already includes any shrink that has taken place."""
    start = max(now, zone["shrink_start"])
    end = zone["shrink_end"]
    fraction = min(1.0, max(0.0, (now + ahead - start) / max(end - start, 0.001)))
    center = [a + (b - a) * fraction for a, b in zip(zone["center"], zone["next_center"])]
    radius = zone["radius"] + (zone["next_radius"] - zone["radius"]) * fraction
    return center, radius


class CollectionPolicy:
    def __init__(self, pickup_radius):
        self.pickup_radius = pickup_radius
        self.seen_cubes = {}
        self.cube_sprint = False

    def visible_and_remembered(self, obs):
        now = obs["t"]
        pos = obs["self"]["pos"]
        near = self.pickup_radius
        visible = {obj["id"]: obj for obj in obs["cubes"]}
        # Reaching a remembered empty spot invalidates it even before its timer expires.
        self.seen_cubes = {
            key: record for key, record in self.seen_cubes.items()
            if now - record[1] <= 6.0 and
            (key in visible or distance(pos, record[0]["pos"]) > near + 1.5
             or abs(pos[2] - record[0]["pos"][2]) > 4)
        }
        for key, obj in visible.items():
            self.seen_cubes[key] = (obj, now)
        return [record[0] for record in self.seen_cubes.values()]

    @staticmethod
    def first_stop(obs, center, radius, focus, skip_until):
        me = obs["self"]
        pos = me["pos"]
        now = obs["t"]
        speed = max(1, me["stats"]["walk_speed"])
        eligible = []
        for cube in obs["cubes"]:
            point = cube["pos"]
            d = distance(pos, point)
            if (d <= 68 and abs(pos[2] - point[2]) <= 4 and distance(point, center) <= radius
                    and skip_until.get(("cube", cube["id"]), 0) <= now):
                eligible.append((d, cube))
        if len(eligible) <= 1:
            return obs["cubes"]
        # Bound the work and use a short route only while the second stop is safe on arrival.
        pool = sorted(eligible, key=lambda entry: (entry[0], entry[1]["id"]))[:8]
        best_cost = math.inf
        best = None
        for travel, first in pool:
            reward = 0
            for _, second in pool:
                if first["id"] == second["id"]:
                    continue
                onward = distance(first["pos"], second["pos"])
                if onward >= 32:
                    continue
                arrival = (travel + onward) / speed
                c, r = circle_at(obs["zone"], now, arrival + 2)
                if distance(second["pos"], c) < r - min(6, r * 0.15):
                    reward = max(reward, 0.75 * (32 - onward))
            cost = travel - reward - (4 if focus == ("cube", first["id"]) else 0)
            if cost < best_cost:
                best_cost, best = cost, first
        return [best]

    def collect_with_reserve(self, obs, action, focus, navigation_mode):
        me = obs["self"]
        if (not focus or focus[0] != "cube" or navigation_mode != "direct"
                or not me["grounded"] or not me["in_zone"]
                or any(r["kind"] == "mech" and distance(me["pos"], r["pos"]) < 52 for r in obs["mechs"])):
            self.cube_sprint = False
            return
        cube = next((p for p in obs["cubes"] if p["id"] == focus[1]), None)
        if cube is None or distance(me["pos"], cube["pos"]) < 12:
            self.cube_sprint = False
            return
        energy = me["energy"] / max(1, me["max_energy"])
        self.cube_sprint = energy >= (0.60 if self.cube_sprint else 0.90)
        if self.cube_sprint:
            action["boost"] = True
