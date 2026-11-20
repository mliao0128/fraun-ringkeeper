# Ringkeeper

Ringkeeper is a Python bot for the Builders Buildathon Mech Royale track. It projects the shrinking circle nine game-seconds ahead. When the circle permits a detour, it looks for power cubes, supply drops that restore health, and the lightning pickup. It opens crates, picks upgrades, and can leave an unreachable item to find another route. Its movement controller uses position feedback to recover from obstacles. The match supplies all observations over standard input.

## Run the tests

From the root of this repository, run the following with Python 3.11 or later.

```sh
python3 -B -m unittest discover -s tests -v
```

## Run the organizer's check

Download and unpack the [official starter kit](https://www.joinbuilders.org/buildathon/tracks/builders/files/mechfight-kit.tar.gz). On Linux, run the following commands from the root of this repository. Set KIT to the unpacked directory containing check/ and arena/.

```sh
KIT=/absolute/path/to/mechfight-kit
docker build --platform linux/amd64 -t ringkeeper .
python3 "$KIT/check/check.py" --map-dir /arena -- \
  docker run --rm -i --network none --cpus 1 --memory 512m --memory-swap 512m \
  --read-only --tmpfs /tmp:rw,size=64m --user 65534:65534 \
  --pids-limit 128 --cap-drop ALL -v "$KIT/arena:/arena:ro" ringkeeper
```

The check replays recorded observations. To get a placement score, publish this directory at the root of a public GitHub repository, keep the submitted commit accessible through the results, and submit it from your registered team's [Mech Royale track page](https://www.joinbuilders.org/buildathon/tracks/builders).

## Credits and license

The unchanged `mechfight.py` transport and type definitions come from the [organizer's Python starter kit](https://www.joinbuilders.org/buildathon/tracks/builders). The decision policy, navigation controller, and unit tests were written for this entry with OpenAI Codex assistance. The bot uses the Python standard library and the Docker Official Image for Python. The entry is released under the [MIT License](LICENSE).
