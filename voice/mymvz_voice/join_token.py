"""Print a join token for talking to the agent in the browser (development).

    docker compose --profile voice run --rm voice python -m mymvz_voice.join_token

Then open https://meet.livekit.io, tab "Custom", server URL
ws://localhost:7880 and this token. The agent joins the room by itself.
"""

from __future__ import annotations

import argparse
import os
from datetime import timedelta

from livekit import api


def make_token(*, room: str, identity: str, key: str, secret: str) -> str:
    grant = api.VideoGrants(room_join=True, room=room)
    return (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_grants(grant)
        .with_ttl(timedelta(hours=1))
        .to_jwt()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--room", default="test")
    parser.add_argument("--identity", default="tester")
    args = parser.parse_args()
    print(
        make_token(
            room=args.room,
            identity=args.identity,
            key=os.environ["LIVEKIT_API_KEY"],
            secret=os.environ["LIVEKIT_API_SECRET"],
        )
    )


if __name__ == "__main__":
    main()
