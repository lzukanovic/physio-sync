# PLUX-API-Python3 (vendored)

Compiled PLUX BITalino/biosignalsplux API extension modules. There is no PyPI
distribution, so they are committed here and loaded by the BITalino adapter.

- **Upstream:** https://github.com/pluxbiosignals/python-samples (`PLUX-API-Python3/`)
- **Commit:** `6d5a2059a1da220a6db712fbf283b36c93c948c3` (2025-10-29,
  "Inclusion of support to Python 3.13 (Windows 64 bits)"), the last commit
  touching `PLUX-API-Python3/`
- **Copied unmodified:** the kept folders are byte-identical to upstream at that commit.

## Kept folders

Python 3.10 only, for the platforms actually used:

| Folder | Used for |
| --- | --- |
| `Win64_310/` | lab machine (Windows) |
| `M1_310/` | development on Apple Silicon |
| `MacOS/Intel310/` | development on Intel Mac |

Python 3.10 is forced by the intersection of this SDK (no Win64 binary for 3.11
or 3.12) and g3pylib. See `CLAUDE.md` and `docs/adapters.md`. Folders for other
platforms or Python versions were removed on purpose; they cannot run here and
would only bloat the repo and the wheel.

## Updating

Copy the same folders from a newer upstream commit, then update the commit hash
and date above. If the PLUX API changes behaviour, re-measure BITalino
`nSeq` handling (see `docs/adapters.md`) before trusting the new binary.
