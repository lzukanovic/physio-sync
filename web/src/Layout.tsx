import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { fetchHealth, type Health } from "./api";

const links = [
  { to: "/studies", label: "Studies" },
  { to: "/devices", label: "Devices" },
];

function HealthStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth, (e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="text-red-600">Backend unreachable: {error}</p>;
  if (!health) return <p className="text-slate-500">Checking backend…</p>;
  return (
    <dl className="space-y-1 text-xs text-slate-600">
      <div>v{health.version}</div>
      <div className={health.db_ok ? "text-green-700" : "text-red-600"}>
        database {health.db_ok ? "ok" : "unreachable"}
      </div>
      <div className="break-all">{health.data_root}</div>
    </dl>
  );
}

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="flex w-56 flex-col justify-between border-r border-slate-200 bg-white p-4">
        <div>
          <h1 className="mb-6 text-lg font-semibold">physio-sync</h1>
          <nav className="flex flex-col gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded px-3 py-2 text-sm ${isActive ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <HealthStatus />
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
