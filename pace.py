"""Spend spare energy on ground movement when the next safe ring is getting tight."""
import math


def adjust_pace(obs, action):
    me = obs["self"]
    if action.get("boost") or action.get("jump") or not me["grounded"]:
        return
    stats = me["stats"]
    # Keep one third of the battery, including the next normal decision interval.
    if me["energy"] < me["max_energy"] / 3 + 0.1 * stats["boost_drain"]:
        return
    zone = obs["zone"]
    gap = math.dist(me["pos"][:2], zone["next_center"]) - zone["next_radius"]
    if gap <= 0:
        return
    # Allow one second to react and 50% more distance for turns and wall slides.
    # Start sprinting only while the commanded direction is actually traversable.
    walking_seconds = 1.5 * gap / stats["walk_speed"] + 1.0
    along_move = sum(v * u for v, u in zip(me["vel"][:2], action["move"]))
    if zone["shrink_end"] - obs["t"] <= walking_seconds and along_move > 0.2 * stats["walk_speed"]:
        action["boost"] = True
