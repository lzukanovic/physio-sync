# 0005 — No Docker on the lab machine

**Context.** Docker Compose would be a reasonable way to run a multi-service
stack, and the lab has no objection to it.

**Decision.** Not used for the capture stack.

**Consequences.** The lab PC is Windows. Docker Desktop runs containers inside a
WSL2 VM with no practical Bluetooth passthrough, so the BITalino adapter must run
on the host regardless. That forces a hybrid — native Python plus containers —
which is worse than either pure option: Python and the PLUX binaries still have
to be installed natively, and a network boundary appears between the collector
and the API. If the deployment target were Linux this decision would be revisited,
since `--net=host` plus a D-Bus mount makes BlueZ work in a container.
