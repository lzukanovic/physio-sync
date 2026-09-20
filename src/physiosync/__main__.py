import sys

import uvicorn

from physiosync import config
from physiosync.api.app import create_app


def main() -> None:
    try:
        settings = config.load()
    except config.ConfigError as e:
        print(f"physiosync: configuration error: {e}", file=sys.stderr)
        sys.exit(2)
    # Loopback on purpose: the lab PC is the only client. ws="websockets" pins uvicorn's legacy
    # implementation: g3pylib requires websockets~=10.3, and "auto" imports the sans-IO one
    # (needs websockets>=13) and crashes at startup. See docs/decisions/0008-uvicorn-legacy-websockets.md.
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, ws="websockets")


if __name__ == "__main__":
    main()
