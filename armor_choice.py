"""Keep the recovery policy and pick direct protection when the first card lacks it."""
from bot import Bot as RecoveryBot
import mechfight as mf


class Bot(RecoveryBot):
    name = "Fraun-Armor-Choice"

    def act(self, obs):
        action = super().act(obs)
        if obs["offer"]:
            cards = [card["id"] for card in obs["offer"]["choices"]]
            if cards[0] not in ("plating", "armor", "nanites"):
                for preferred in ("plating", "armor"):
                    if preferred in cards:
                        action["pick"] = cards.index(preferred)
                        break
        return action


if __name__ == "__main__":
    mf.run(Bot)
