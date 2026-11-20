import math
import unittest

from bot import Bot, circle_at, distance


def game():
    configuration = {"loot": {"pickup_radius": 4}, "mech": {"height": 9},
                     "cubes": {"size_per_cube": 0.05}}
    bot = Bot({"seed": 23, "config": configuration})
    state = {
        "t": 0, "tick": 0, "alive": 16, "offer": None, "mechs": [],
        "crates": [], "cubes": [], "pickups": [], "drops": [],
        "self": {"id": 5, "pos": [0, 0, 0], "aim": [0, 0], "hp": 1400, "max_hp": 1400,
                 "energy": 100, "max_energy": 100, "grounded": True, "cubes": 0,
                 "stats": {"walk_speed": 11.7, "muzzle_height": 7}, "in_zone": True,
                 "weapons": [{"kind": "gun", "stats": {"mag": 12, "range": 230},
                              "ammo": 12, "reload": 0}, None]},
        "zone": {"center": [0, 0], "radius": 100, "next_center": [0, 0],
                 "next_radius": 60, "shrink_start": 60, "shrink_end": 80},
    }
    return bot, state


class GamePolicyTest(unittest.TestCase):
    def test_circle_projection_across_phase_edges(self):
        zone = {"center": [0, 0], "radius": 100, "next_center": [20, 0], "next_radius": 60,
                "shrink_start": 5, "shrink_end": 15}
        self.assertEqual(circle_at(zone, 0, 4), ([0, 0], 100))
        self.assertEqual(circle_at(zone, 0, 10), ([10, 0], 80))
        zone.update(center=[10, 0], radius=80)
        self.assertEqual(circle_at(zone, 10, 2.5), ([15, 0], 70))
        self.assertEqual(circle_at(zone, 10, 20), ([20, 0], 60))

    def test_ring_overrides_visible_cube(self):
        bot, state = game()
        state["self"]["pos"] = [102, 0, 0]
        state["self"]["in_zone"] = False
        state["cubes"] = [{"id": 5012, "pos": [105, 0, 0]}]
        action = bot.act(state)
        self.assertLess(action["move"][0], 0)
        self.assertTrue(action["boost"])

    def test_collectible_and_pickup_height(self):
        bot, state = game()
        state["cubes"] = [{"id": 5012, "pos": [-9, 0, 0]}]
        state["pickups"] = [{"id": 8001, "kind": "lightning", "pos": [0, 0, 15]}]
        self.assertLess(bot.act(state)["move"][0], 0)
        self.assertNotIn("take", bot.act(state))
        state["pickups"][0]["pos"] = [1, 0, 0]
        self.assertEqual(bot.act(state)["take"], 8001)

    def test_drop_capture_stays_inside(self):
        bot, state = game()
        state["drops"] = [{"id": 20000, "pos": [2, 0, 0], "lands_in": 0, "progress": 0,
                           "capture_s": 4, "holder": None, "radius": 8}]
        for i in range(45):
            state["t"] = i / 10
            self.assertEqual(bot.act(state)["move"], [0, 0])
        state["drops"][0]["holder"] = 9
        self.assertNotEqual(bot.act(state)["move"], [0, 0])

    def test_upgrades_are_chosen_by_effect_in_any_order(self):
        bot, state = game()
        for ids in [("gun_mag", "plating", "jets"), ("plating", "jets", "gun_mag")]:
            state["offer"] = {"choices": [{"id": name} for name in ids]}
            self.assertEqual(ids[bot.act(state)["pick"]], "plating")

    def test_game_slots_and_regeneration(self):
        bot, state = game()
        state["mechs"] = [{"id": 1, "kind": "mech", "pos": [30, 0, 0]}]
        state["self"]["aim"] = [0, math.atan2(-2.5, 30)]
        self.assertEqual(bot.act(state)["fire"], [True, False])
        state["self"]["weapons"][1] = {"kind": "lightning", "stats": {"cone_deg": 30, "range": 45, "energy": 3}}
        self.assertEqual(bot.act(state)["fire"], [True, True])
        state["self"]["energy"] = 8
        self.assertEqual(bot.act(state)["fire"], [True, False])
        state["mechs"][0]["pos"][0] = 90
        state["self"]["hp"] = 500
        self.assertEqual(bot.act(state)["fire"], [False, False])

    def test_stalled_collectible_times_out(self):
        bot, state = game()
        state["cubes"] = [{"id": 5012, "pos": [10, 0, 0]}]
        bot.act(state)
        self.assertEqual(bot.focus, ("cube", 5012))
        state["t"] = 4.5
        bot.act(state)
        self.assertIsNone(bot.focus)
        self.assertIn(("cube", 5012), bot.skip_until)

    def test_follow_a_moving_shrinking_circle(self):
        # This closed-loop fixture models movement on flat ground. No leaderboard score is inferred.
        bot, state = game()
        state["self"]["pos"] = [98, 0, 0]
        for i in range(401):
            now = i / 10
            phase = max(0, min(1, (now - 5) / 35))
            state.update(t=now, tick=i * 2)
            zone = state["zone"]
            zone.update(center=[-25 * phase, 10 * phase], radius=100 * (1 - phase) + 4 * phase,
                        next_center=[-25, 10], next_radius=4, shrink_start=5, shrink_end=40)
            me = state["self"]
            me["in_zone"] = distance(me["pos"], zone["center"]) <= zone["radius"]
            self.assertTrue(me["in_zone"], f"left circle at {now}s")
            move = bot.act(state)
            speed = 19.5 if move["boost"] else 11.7
            for axis, direction in enumerate(move["move"]):
                me["pos"][axis] += speed * 0.1 * direction
        self.assertLessEqual(distance(state["self"]["pos"], [-25, 10]), 4)
