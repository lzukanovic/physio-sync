# 0001 — Single process for the capture stack

**Context.** An earlier scaffold split the system into a host-side collector, a
containerised API, a database container, and a web container. The lab PC is a
single Windows machine that also runs SCANeR Studio.

**Decision.** One Python process. Adapters run in-process as asyncio tasks.
FastAPI serves the API, the live WebSocket, and the built frontend as static
files.

**Consequences.** No serialisation boundary in the capture path, one log, one
failure domain, one thing for the operator to start. The `SourceAdapter`
interface is maintained as the seam where a future split into remote loggers
would happen, but that split is not built. Deployment to an internal lab server
remains possible later and is listed as future work.
