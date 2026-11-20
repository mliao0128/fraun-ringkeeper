import unittest

from test_policy import game


def cube(identifier, x, y=0):
    return {"id": identifier, "pos": [x, y, 0]}


class CollectionTest(unittest.TestCase):
    def test_memory_survives_occlusion_until_expiry(self):
        bot, state = game()
        state["cubes"] = [cube(5001, 25)]
        bot.act(state)
        state.update(cubes=[], t=2.0)
        self.assertEqual(bot.act(state)["move"], [1, 0])
        self.assertEqual(bot.focus, ("cube", 5001))
        state["t"] = 6.1
        bot.act(state)
        self.assertIsNone(bot.focus)

    def test_absence_at_pickup_range_invalidates_memory(self):
        bot, state = game()
        state["cubes"] = [cube(5001, 14)]
        bot.act(state)
        state.update(cubes=[], t=0.6)
        state["self"]["pos"] = [13, 0, 0]
        bot.act(state)
        self.assertIsNone(bot.focus)

    def test_two_stop_route_can_beat_nearest(self):
        bot, state = game()
        state["cubes"] = [cube(5001, -10), cube(5002, 16), cube(5003, 20)]
        bot.act(state)
        self.assertEqual(bot.focus, ("cube", 5002))

    def test_sprint_observes_energy_hysteresis(self):
        bot, state = game()
        state["cubes"] = [cube(5001, 35)]
        for i, (energy, expected) in enumerate([(87, False), (92, True), (65, True),
                                                (59, False), (85, False)]):
            state.update(t=i * 0.1, tick=i * 2)
            state["self"]["energy"] = energy
            self.assertEqual(bot.act(state)["boost"], expected)

    def test_sprint_stops_before_pickup(self):
        bot, state = game()
        state["cubes"] = [cube(5001, 20)]
        self.assertTrue(bot.act(state)["boost"])
        state["t"] = 0.6
        state["self"]["pos"] = [9, 0, 0]
        self.assertFalse(bot.act(state)["boost"])
