"""Recovery with corner escape and deadline-aware ground movement."""
import mechfight as mf
from pace import adjust_pace
from pocket import Bot as PocketBot


class Bot(PocketBot):
    name = "Fraun-Recovery-Plus"

    def act(self, obs):
        action = super().act(obs)
        adjust_pace(obs, action)
        return action


if __name__ == "__main__":
    mf.run(Bot)
