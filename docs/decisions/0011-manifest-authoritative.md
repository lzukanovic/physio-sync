# 0011 — The manifest is authoritative; SQLite is a rebuildable index

**Context.** Task 01 records takes before study management exists (Phase 4). The
`take` table requires a `recording_id`, and the manifest required study,
participant, scenario and take index. Either the database is authoritative and a
take directory is payload it points at, or the directory is authoritative and
the database indexes it. Both are defensible; left open, Phase 4 would pick one
by accident.

**Decision.** The take directory, through its `manifest.json`, is the record of
a take. SQLite is an index that can be rebuilt by scanning `takes/`. The
manifest's `study_id`, `participant_id`, `scenario_id` and `take_index` are
nullable: a take recorded outside a study is complete without them. Task 01
writes no SQLite rows. Seeding a placeholder study to satisfy the schema was
rejected: fake entities in the database are worse than none.

**Consequences.** A take directory copied between machines stays valid, and
importing existing takes, including the lab's historical recordings, is a scan
plus whatever converter their format needs. Phase 4 must keep every fact about a
take that is needed to rebuild its row in the manifest, and must treat a
disagreement between database and manifest as the database being stale.
