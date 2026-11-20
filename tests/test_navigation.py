import math
import unittest

from navigation import Navigator


def observation(t=0, x=0, y=0, energy=100, grounded=True):
    return {
        "t": t,
        "self": {
            "pos": [x, y, 0],
            "stats": {"walk_speed": 11.7},
            "energy": energy,
            "max_energy": 100,
            "grounded": grounded,
        },
    }


class NavigationTest(unittest.TestCase):
    def test_arrival_and_hold(self):
        nav = Navigator(1)
        far = nav.steer(observation(), (30, 40))
        self.assertEqual(far["move"], [0.6, 0.8])
        near = nav.steer(observation(0.1), (2, 0), hurry=True)
        self.assertGreater(near["move"][0], 0)
        self.assertLess(near["move"][0], 1)
        self.assertFalse(near["boost"])
        self.assertEqual(nav.steer(observation(0.2), (1, 0), hurry=True),
                         {"move": [0, 0], "boost": False, "jump": False})

    def test_sprint_has_energy_hysteresis_and_no_unrequested_jet(self):
        nav = Navigator(4)
        energies = [100, 51, 30, 59, 85]
        boosts = [nav.steer(observation(i / 10, i, energy=e), (100, 0), hurry=True)["boost"]
                  for i, e in enumerate(energies)]
        self.assertEqual(boosts, [True, True, False, False, True])
        self.assertFalse(nav.steer(observation(0.5, grounded=False), (100, 0),
                                   hurry=True)["boost"])

    def test_stalled_mech_jumps_then_detours_if_still_blocked(self):
        nav = Navigator(2)
        actions = []
        for i in range(55):
            obs = observation(i / 10, grounded=(i != 10))
            actions.append(nav.steer(obs, (100, 0)))
        self.assertFalse(actions[0]["jump"])
        self.assertTrue(any(a["jump"] for a in actions))
        self.assertTrue(actions[10]["boost"])
        self.assertTrue(any(abs(a["move"][1]) > 0.8 for a in actions))
        self.assertTrue(all(math.hypot(*a["move"]) <= 1.000001 for a in actions))

    def test_steady_progress_does_not_trigger_recovery(self):
        nav = Navigator(11)
        for i in range(101):
            action = nav.steer(observation(i / 10, x=i), (120, 0))
            self.assertEqual(action["move"], [1, 0])
            self.assertFalse(action["jump"])

    def test_new_goal_cancels_detour(self):
        nav = Navigator(3)
        for i in range(12):
            move = nav.steer(observation(i / 10, energy=10), (90, 0))
        self.assertGreater(abs(move["move"][1]), 0.8)
        changed = nav.steer(observation(1.2), (-90, 0))
        self.assertEqual(changed["move"], [-1, 0])
