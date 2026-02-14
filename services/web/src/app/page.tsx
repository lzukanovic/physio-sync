export default function DashboardPage() {
  return (
    <div>
      <h2 className="mb-6 text-2xl font-semibold tracking-tight">Dashboard</h2>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <Card title="Devices" value="--" description="Connected sensors" />
        <Card title="Recording" value="Idle" description="Current status" />
        <Card title="Samples" value="0" description="Total received" />
      </div>
    </div>
  );
}

function Card({
  title,
  value,
  description,
}: {
  title: string;
  value: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-sm font-medium text-zinc-500">{title}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      <p className="mt-1 text-sm text-zinc-400">{description}</p>
    </div>
  );
}
