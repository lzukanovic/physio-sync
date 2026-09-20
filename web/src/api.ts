export interface Health {
  version: string;
  data_root: string;
  db_ok: boolean;
}

export async function fetchHealth(): Promise<Health> {
  const r = await fetch("/api/health");
  if (!r.ok) throw new Error(`/api/health returned ${r.status}`);
  return r.json();
}
