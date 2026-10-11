// Minimal capture page (Task 01 item 7). Phase 4 replaces it.
// Each stream is drawn on its own time axis: the live feed does not align streams (ADR 0013).
// Recording state comes from the server's frames only, never from button clicks (ADR 0014).
import { useEffect, useRef, useState } from "react";

type Value = number | null;

/** One stream in a frame: its own time column and channels, as its StreamSpec declares them. */
interface StreamFrame {
  time_column: string;
  columns: Record<string, Value[]>;
}

interface Frame {
  t_utc: number;
  recording: boolean;
  t_start: number | null;
  received: Record<string, number>;
  dropped: Record<string, number>;
  streams: Record<string, StreamFrame>;
  skipped: number;
}

interface StreamInfo {
  n_samples: number | null;
}

interface StopResult {
  uuid: string;
  streams: Record<string, StreamInfo>;
}

const WINDOW_S = 20;
const GAP_S = 0.5; // per channel: >= 50 ms decimated, 100 ms for 10 Hz mag; more is a gap (reconnect, dropout, blink)
// Axis meaning by time column. These clocks are not comparable to each other (ADR 0013).
const AXES: Record<string, { label: string; clock: boolean }> = {
  t: { label: "t — host wall-clock, UTC", clock: true },
  device_ts: { label: "device_ts — seconds since stream open", clock: false },
};

type History = Record<string, StreamFrame>;

/** Append a frame's samples and keep the newest WINDOW_S of each stream's own clock.
 * History resets only on a new take (t_start), never on a backwards timestamp: real Tobii IMU
 * device_ts goes backwards at every magnetometer batch (docs/plan.md), which must not blank a pane. */
function append(history: History, frame: Frame) {
  for (const [sid, { time_column: tc, columns }] of Object.entries(frame.streams)) {
    const ts = columns[tc] ?? [];
    if (!ts.length) continue;
    const h = (history[sid] ??= { time_column: tc, columns: {} }).columns;
    for (const [c, vs] of Object.entries(columns)) (h[c] ??= []).push(...vs);
    const newest = ts.at(-1) as number;
    const cut = h[tc].findIndex((t) => t != null && t >= newest - WINDOW_S);
    if (cut > 0) for (const c in h) h[c].splice(0, cut);
  }
}

function fmtTime(t: number, clock: boolean) {
  return clock ? new Date(t * 1000).toISOString().slice(11, 21) + " UTC" : `${t.toFixed(1)} s`;
}

function Pane({
  sid,
  stream,
  received,
  dropped,
}: {
  sid: string;
  stream: StreamFrame;
  received: number;
  dropped: number;
}) {
  const { time_column: tc, columns: cols } = stream;
  const channels = Object.keys(cols).filter((c) => c !== tc);
  const [chosen, setChosen] = useState<string | null>(null);
  const channel = chosen && channels.includes(chosen) ? chosen : channels[0];
  const axis = AXES[tc] ?? { label: tc, clock: false };
  const ts = cols[tc] as number[];
  const vs = cols[channel] ?? [];
  const W = 1000;
  const H = 160;

  const newest = ts.at(-1) ?? 0;
  const x0 = newest - WINDOW_S;
  const finite = vs.filter((v): v is number => v != null && Number.isFinite(v));
  const lo = finite.length ? Math.min(...finite) : 0;
  const hi = finite.length ? Math.max(...finite) : 1;
  const span = hi - lo || 1;
  // Rows without this channel are skipped, not breaks: mixed-rate streams (Tobii IMU) interleave
  // channels row by row. A break is a time gap since this channel's last value. Points with no
  // neighbour are drawn as dots so a sparse channel never renders as nothing.
  const segs: [number, number][][] = [];
  let prev = -Infinity;
  ts.forEach((t, i) => {
    const v = vs[i];
    if (v == null || !Number.isFinite(v)) return;
    if (t - prev > GAP_S) segs.push([]);
    segs[segs.length - 1].push([((t - x0) / WINDOW_S) * W, H - ((v - lo) / span) * H]);
    prev = t;
  });
  const xy = ([x, y]: [number, number]) => `${x.toFixed(1)} ${y.toFixed(1)}`;
  const line = segs
    .filter((s) => s.length > 1)
    .map((s) => "M" + s.map(xy).join("L"))
    .join("");
  const dots = segs
    .filter((s) => s.length === 1)
    .map((s) => `M${xy(s[0])}h0`) // zero-length subpath + round cap = a dot
    .join("");

  return (
    <section className="rounded border border-slate-200 bg-white p-3">
      <div className="mb-1 flex flex-wrap items-center gap-4 text-sm">
        <h3 className="font-mono font-semibold">{sid}</h3>
        <select
          className="rounded border border-slate-300 px-1"
          value={channel}
          onChange={(e) => setChosen(e.target.value)}
        >
          {channels.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <span>
          received <b className="tabular-nums">{received.toLocaleString()}</b>
        </span>
        <span className="text-slate-600">
          dropped from display <span className="tabular-nums">{dropped.toLocaleString()}</span>
        </span>
      </div>
      <div className="flex gap-2 text-xs text-slate-500">
        <div className="flex w-16 flex-col justify-between text-right tabular-nums">
          <span>{hi.toPrecision(4)}</span>
          <span>{lo.toPrecision(4)}</span>
        </div>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className="h-40 flex-1 bg-slate-50"
          role="img"
          aria-label={`${sid} ${channel}, last ${WINDOW_S} seconds`}
        >
          <path d={line} fill="none" stroke="#1d4ed8" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          <path
            d={dots}
            stroke="#1d4ed8"
            strokeWidth={5}
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </div>
      <div className="ml-18 flex justify-between text-xs text-slate-500 tabular-nums">
        <span>{fmtTime(x0, axis.clock)}</span>
        <span className="italic">{axis.label}</span>
        <span>{fmtTime(newest, axis.clock)}</span>
      </div>
    </section>
  );
}

async function post(path: string, body?: unknown) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const json = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(json.detail ?? `${path} returned ${r.status}`);
  return json;
}

export default function Capture() {
  const [frame, setFrame] = useState<Frame | null>(null);
  const [connected, setConnected] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StopResult | null>(null);
  const history = useRef<History>({});
  const takeStart = useRef<number | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    let closed = false;
    const connect = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/live`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => {
        const f: Frame = JSON.parse(e.data);
        if (f.t_start !== takeStart.current) {
          takeStart.current = f.t_start;
          if (f.t_start != null) history.current = {}; // a new take: old history is another take's
        }
        append(history.current, f);
        setFrame(f);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 1000);
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      ws.close();
    };
  }, []);

  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const start = () =>
    act(async () => {
      setResult(null);
      await post("/api/session/start", { "replay:bitalino": { speed }, "replay:tobii": { speed } });
    });
  const stop = () => act(async () => setResult(await post("/api/session/stop")));
  const cancel = () => {
    if (confirm("Cancel deletes this take and everything recorded so far. Continue?"))
      act(async () => void (await post("/api/session/cancel")));
  };

  const recording = connected && !!frame?.recording;
  const elapsed = recording && frame?.t_start != null ? Math.max(0, frame.t_utc - frame.t_start) : 0;
  const hms = new Date(elapsed * 1000).toISOString().slice(11, 19);

  return (
    <div className="max-w-6xl space-y-4">
      <h2 className="text-xl font-semibold">Capture</h2>

      {!connected ? (
        <div className="rounded bg-slate-300 p-3 font-semibold text-slate-800">
          ● Feed disconnected — state unknown. Reconnecting…
        </div>
      ) : recording ? (
        <div className="rounded bg-red-600 p-3 font-semibold text-white">
          ● RECORDING <span className="ml-4 font-mono tabular-nums">{hms}</span>
        </div>
      ) : (
        <div className="rounded bg-slate-100 p-3 font-semibold text-slate-700">○ Not recording</div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
          onClick={start}
          disabled={busy}
        >
          Start
        </button>
        <button
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
          onClick={stop}
          disabled={busy}
        >
          Stop
        </button>
        <button
          className="rounded border border-slate-400 px-4 py-2 disabled:opacity-40"
          onClick={cancel}
          disabled={busy}
        >
          Cancel
        </button>
        <label className="ml-4 flex items-center gap-2 text-sm">
          Replay speed
          <input
            type="number"
            min={0.1}
            step="any"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="w-20 rounded border border-slate-300 px-2 py-1"
          />
          <span className="text-slate-500">× — fixture playback, not a device setting</span>
        </label>
      </div>

      {error && <p className="text-red-700">{error}</p>}
      {result && (
        <div className="rounded border border-slate-200 bg-white p-3 text-sm">
          Take <span className="font-mono">{result.uuid}</span> finalised:{" "}
          {Object.entries(result.streams)
            .map(([sid, s]) => `${sid} ${s.n_samples?.toLocaleString() ?? "?"}`)
            .join(", ")}{" "}
          samples written.
        </div>
      )}

      {frame && frame.skipped > 0 && (
        <p className="text-sm text-slate-600">This browser skipped {frame.skipped} frames (display only).</p>
      )}
      {Object.entries(history.current).map(([sid, stream]) => (
        <Pane
          key={sid}
          sid={sid}
          stream={stream}
          received={frame?.received?.[sid] ?? 0}
          dropped={frame?.dropped?.[sid] ?? 0}
        />
      ))}
    </div>
  );
}
