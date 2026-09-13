# 0004 — No cross-device event anchoring

**Context.** BITalino has no clock and no trigger input. Tobii offers
`recorder!send-event`, which would let BITalino start and stop be anchored on the
glasses' clock.

**Decision.** Not used. Each stream is aligned onto the reference system's clock
using the timestamps it already carries; BITalino is first reconstructed from its
sequence number against a host wall-clock start time.

**Consequences.** Anchoring would require the BITalino capture module to talk to
the glasses during capture, coupling two systems that are independent by design.
The setup would no longer work without the glasses, and adding any new device
would require deciding which existing system it binds to. This violates the
modularity requirement. The cost is that BITalino's absolute placement depends on
the host clock, whose jitter becomes a shared error term. This is measured and
reported per recording rather than assumed away.
