from physiosync.adapters.replay import ReplayAdapter

# Adapter id -> factory. The session manager builds adapters from here.
ADAPTERS = {
    "replay:bitalino": lambda: ReplayAdapter("bitalino"),
    "replay:tobii": lambda: ReplayAdapter("tobii"),
}
