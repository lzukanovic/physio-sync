# 0008 — uvicorn runs its legacy `websockets` implementation

**Context.** g3pylib (the lab fork) requires `websockets ~= 10.3`. uvicorn's default
`ws="auto"` imports its sans-IO implementation, which needs `websockets >= 13`, and
the app then crashes at startup with `ImportError: cannot import name 'ServerProtocol'`.
Found in Phase 0 by running `python -m physiosync` after a clean install.

**Decision.** `__main__.py` starts uvicorn with `ws="websockets"`, the legacy
implementation, which works with websockets 10.x. No dependency was added or pinned.

**Consequences.** The live-feed WebSocket (Phase 1) runs on the legacy
implementation; it has not yet been exercised against a real WS route. uvicorn
marks it deprecated and plans to repoint `"websockets"` at the sans-IO one, so a
future uvicorn upgrade can break startup again. Revisit if the fork moves to
websockets >= 13, or cap `uvicorn` if the deprecation lands first.
