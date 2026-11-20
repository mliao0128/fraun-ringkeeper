"""Placement-oriented policy for the mechfight/1 game."""
import math
import random

import mechfight
from navigation import Navigator


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


def fit_inside(point, center, radius):
    span = distance(point, center)
    if span <= radius or span == 0:
        return tuple(point[:2])
    scale = radius / span
    return tuple(c + (p - c) * scale for p, c in zip(point[:2], center))


UPGRADES = (
    "plating", "nanites", "armor", "servos", "lightning_efficiency",
    "lightning_range", "reactor", "jets", "capacitor", "gun_rate",
    "gun_damage", "gun_mag", "sensors", "gyros",
)


class Bot:
    name = "Ringkeeper"

    def __init__(self, hello):
        self.config = hello["config"]
        self.navigator = Navigator(hello["seed"])
        self.phase = random.Random(hello["seed"]).uniform(-math.pi, math.pi)
        self.waypoint = None
        self.refresh_at = 0.0
        self.waypoint_mode = None
        self.focus = None
        self.best_distance = math.inf
        self.last_progress = 0.0
        self.skip_until = {}

    def roam(self, obs, center, radius, rivals, mode):
        me = obs["self"]["pos"]
        now = obs["t"]
        if (mode == self.waypoint_mode and self.waypoint is not None
                and now < self.refresh_at and distance(me, self.waypoint) > 5):
            return fit_inside(self.waypoint, center, radius)
        self.phase = (self.phase + 2.399963) % math.tau
        options = []
        stride = min(55.0, radius * 0.65)
        for i in range(12):
            angle = self.phase + i * math.tau / 12
            point = fit_inside((me[0] + stride * math.cos(angle),
                                me[1] + stride * math.sin(angle)), center, radius)
            clearance = min((min(130, distance(point, r["pos"])) for r in rivals), default=0)
            # Spend the quiet part of the round searching for upgrades inside the next ring.
            inward = max(0.0, distance(point, obs["zone"]["next_center"]) -
                         obs["zone"]["next_radius"] * 0.75)
            value = clearance + 0.32 * distance(me, point) - 0.55 * inward
            options.append((value, point))
        self.waypoint = max(options, key=lambda option: round(option[0], 4))[1]
        self.waypoint_mode = mode
        self.refresh_at = now + (1.7 if mode == "space" else 7.0)
        return self.waypoint

    def objective(self, obs, center, radius, rivals, arc_missing):
        me = obs["self"]
        pos = me["pos"]
        now = obs["t"]
        health = me["hp"] / max(1, me["max_hp"])
        options = []
        self.skip_until = {key: end for key, end in self.skip_until.items() if end > now}

        def add(kind, obj, value, limit):
            point = obj["pos"]
            key = (kind, obj["id"])
            span = distance(pos, point)
            if key in self.skip_until or span > limit or abs(point[2] - pos[2]) > 4:
                return
            if distance(point, center) > radius:
                return
            # A rival already beside a bonus can take it or freeze the capture clock.
            lead = min((distance(point, r["pos"]) for r in rivals), default=math.inf)
            if kind == "drop" and lead < obj["radius"] + 5:
                return
            value -= max(0, 30 - lead) + 0.63 * span
            if key == self.focus:
                value += 8
            if value > 0:
                options.append((value, key, span, obj))

        for cube in obs["cubes"]:
            add("cube", cube, 60 if me["cubes"] < 10 else 40, 68)
        if arc_missing:
            for item in obs["pickups"]:
                if item["kind"] == "lightning":
                    add("arc", item, 71, 80)
        for drop in obs.get("drops", []):
            travel = distance(pos, drop["pos"]) / max(1, me["stats"]["walk_speed"])
            if drop["lands_in"] <= travel + 2 and drop["holder"] in (None, me["id"]):
                add("drop", drop, 80 + 65 * (1 - health), 130)
        if not rivals and health > 0.8 and me["cubes"] < 10:
            for crate in obs["crates"]:
                add("crate", crate, 46, 52)
        if not options:
            self.focus = None
            return None
        _, key, span, obj = max(options, key=lambda item: item[0])
        # Suppress inaccessible loot temporarily, including crates whose HP stops falling.
        measure = span + (obj.get("hp", 0) * 0.06 if key[0] == "crate" else 0)
        if self.focus != key or measure < self.best_distance - 1.2:
            self.focus, self.best_distance, self.last_progress = key, measure, now
        holding = key[0] == "drop" and span < obj["radius"] and obj["holder"] in (None, me["id"])
        if not holding and now - self.last_progress > 4:
            self.skip_until[key] = now + 12
            self.focus = None
            return None
        return key[0], obj

    def act(self, obs):
        me = obs["self"]
        pos = me["pos"]
        now = obs["t"]
        center, radius = circle_at(obs["zone"], now, 9)
        margin = min(10.0, radius * 0.18)
        safe_radius = max(0, radius - margin)
        urgent = not me["in_zone"] or distance(pos, center) > safe_radius + 0.25
        rivals = [actor for actor in obs["mechs"] if actor["kind"] == "mech"]
        nearest = min(rivals, key=lambda actor: distance(pos, actor["pos"]), default=None)
        near = distance(pos, nearest["pos"]) if nearest else math.inf
        arc_slot = next((i for i, w in enumerate(me["weapons"]) if w and w["kind"] == "lightning"), None)
        item = None
        hold_radius = min(1.4, max(0.05, radius * 0.08))
        mode = "roam"
        if urgent:
            self.focus = None
            goal = fit_inside(pos, center, max(0.0, safe_radius * 0.65))
        else:
            item = self.objective(obs, center, safe_radius, rivals, arc_slot is None)
            # Collect a bonus already at our feet even when the rest of the route is crowded.
            if near < 52 and (not item or distance(pos, item[1]["pos"]) > 7):
                item = None
                mode = "space"
            if item:
                kind, obj = item
                goal = obj["pos"]
                hold_radius = {"crate": 17.0, "drop": obj.get("radius", 1) * 0.6}.get(kind, 0.8)
            else:
                goal = self.roam(obs, center, safe_radius, rivals, mode)
        act = self.navigator.steer(obs, goal, hurry=urgent or mode == "space", hold_radius=hold_radius)

        # Turn the game camera to find collectibles. A crate takes several hits to open.
        yaw = self.phase + now * 0.95
        pitch = 0.0
        fire = [False, False]
        if item and item[0] == "crate":
            box = item[1]["pos"]
            yaw = math.atan2(box[1] - pos[1], box[0] - pos[0])
            pitch = math.atan2(box[2] + 1.5 - pos[2] - me["stats"]["muzzle_height"],
                               max(0.01, distance(pos, box)))
            aligned = abs(math.remainder(yaw - me["aim"][0], math.tau)) < 0.1
            if aligned and abs(pitch - me["aim"][1]) < 0.12:
                fire = [bool(w and w["kind"] == "gun") for w in me["weapons"]]
        elif nearest:
            # Facing an observed game token also activates the mech's front-armor bonus.
            yaw = math.atan2(nearest["pos"][1] - pos[1], nearest["pos"][0] - pos[0])
            game_height = self.config["mech"]["height"] * (1 + self.config["cubes"].get("size_per_cube", 0)
                                                           * nearest.get("cubes", 0))
            pitch = math.atan2(nearest["pos"][2] + game_height / 2 - pos[2] - me["stats"]["muzzle_height"],
                               max(0.01, near))
            yaw_error = abs(math.remainder(yaw - me["aim"][0], math.tau))
            # Long trades restart the game's HP regeneration timer. Keep healing
            # when the nearest rival is distant and there are several players left.
            engage = near < 55 or obs["alive"] <= 2 or me["hp"] > 0.8 * me["max_hp"]
            if engage and yaw_error < 0.10 and abs(pitch - me["aim"][1]) < 0.12:
                fire = [bool(w and w["kind"] == "gun" and near < w["stats"]["range"])
                        for w in me["weapons"]]
            if arc_slot is not None:
                stats = me["weapons"][arc_slot]["stats"]
                ready = yaw_error < math.radians(stats["cone_deg"])
                fire[arc_slot] = ready and near < stats["range"] and me["energy"] > stats["energy"] + 8
        act.update(aim=[math.remainder(yaw, math.tau), pitch], fire=fire)
        if arc_slot is None and None in me["weapons"]:
            for pickup in obs["pickups"]:
                if (pickup["kind"] == "lightning" and distance(pos, pickup["pos"]) <= self.config["loot"]["pickup_radius"]
                        and abs(pos[2] - pickup["pos"][2]) <= 4):
                    act["take"] = pickup["id"]
                    break
        if not any(fire):
            act["reload"] = any(w and w["kind"] == "gun" and w["ammo"] < 0.65 * w["stats"]["mag"]
                                and w["reload"] == 0 for w in me["weapons"])
        if obs.get("offer"):
            choices = obs["offer"]["choices"]
            if choices:
                priorities = {name: i for i, name in enumerate(UPGRADES)}
                act["pick"] = min(range(len(choices)), key=lambda i: priorities.get(choices[i]["id"], 100))
        return act


if __name__ == "__main__":
    mechfight.run(Bot)
