import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { Dashboard as D, getDashboard, Row } from "../lib/api";
import { num } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { cx, ErrorState, Skeleton } from "../components/ui";

type Metric = "terminated_pct" | "low_accrual_pct";
const METRIC_LABEL: Record<Metric, string> = { terminated_pct: "Terminated (any reason)", low_accrual_pct: "Terminated for low accrual" };

function Tip({ active, payload, metric }: any) {
  if (!active || !payload?.length) return null;
  const r: Row = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-card">
      <p className="font-semibold text-ink">{r.label}</p>
      <p className="num text-muted">{METRIC_LABEL[metric as Metric]}: <strong className="text-ink">{r[metric as Metric].toFixed(1)}%</strong></p>
      <p className="num text-muted">{num(r.trials)} trials</p>
    </div>
  );
}

function DataTable({ rows }: { rows: Row[] }) {
  return (
    <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[26rem] text-left text-sm num">
      <thead><tr className="text-xs text-muted"><th className="py-1.5 pr-4 font-semibold">Group</th><th className="pr-4 font-semibold">Trials</th><th className="pr-4 font-semibold">Terminated</th><th className="font-semibold">Low accrual</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.key} className="border-t border-line"><td className="py-1.5 pr-4">{r.label}</td><td className="pr-4">{num(r.trials)}</td><td className="pr-4">{r.terminated_pct.toFixed(1)}%</td><td>{r.low_accrual_pct.toFixed(1)}%</td></tr>)}</tbody>
    </table></div>
  );
}

function RateChart({ title, note, rows, metric, avg, horizontal = false, line = false, highlight }: { title: string; note?: string; rows: Row[]; metric: Metric; avg: number; horizontal?: boolean; line?: boolean; highlight?: string }) {
  const [table, setTable] = useState(false);
  const h = horizontal ? Math.max(260, rows.length * 34 + 30) : 280;
  const tick = { fill: "var(--chart-text)", fontSize: 12 };
  return (
    <section className="card p-5" aria-labelledby={`h-${title}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h3 id={`h-${title}`} className="text-base font-semibold">{title}</h3>{note && <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-muted">{note}</p>}</div>
        <button className="rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-muted hover:text-ink min-h-[36px]" aria-pressed={table} onClick={() => setTable(!table)}>{table ? "Show chart" : "Show table"}</button>
      </div>
      {table ? <DataTable rows={rows} /> : (
        <div className="mt-3" style={{ height: h }} role="img" aria-label={`${title}: ${METRIC_LABEL[metric]} by group. Use "Show table" for the exact values.`}>
          <ResponsiveContainer width="100%" height="100%">
            {line ? (
              <LineChart data={rows} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="label" tick={tick} tickLine={false} axisLine={{ stroke: "var(--chart-grid)" }} />
                <YAxis tick={tick} tickLine={false} axisLine={false} unit="%" domain={[0, "auto"]} />
                <Tooltip content={<Tip metric={metric} />} />
                <ReferenceLine y={avg} stroke="var(--chart-2)" strokeDasharray="4 4" />
                <Line type="monotone" dataKey={metric} stroke="var(--chart-1)" strokeWidth={3} dot={{ r: 3.5, fill: "var(--chart-1)" }} isAnimationActive />
              </LineChart>
            ) : (
              <BarChart data={rows} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 4, right: 24, left: horizontal ? 8 : -8, bottom: 0 }}>
                <CartesianGrid stroke="var(--chart-grid)" horizontal={!horizontal} vertical={horizontal} />
                {horizontal ? (<><XAxis type="number" tick={tick} unit="%" axisLine={false} tickLine={false} /><YAxis type="category" dataKey="label" tick={tick} width={190} axisLine={false} tickLine={false} /></>)
                  : (<><XAxis dataKey="label" tick={tick} tickLine={false} interval={0} axisLine={{ stroke: "var(--chart-grid)" }} /><YAxis tick={tick} unit="%" axisLine={false} tickLine={false} /></>)}
                <Tooltip content={<Tip metric={metric} />} cursor={{ fill: "var(--chart-grid)", opacity: 0.4 }} />
                {horizontal ? <ReferenceLine x={avg} stroke="var(--chart-2)" strokeDasharray="4 4" /> : <ReferenceLine y={avg} stroke="var(--chart-2)" strokeDasharray="4 4" />}
                <Bar dataKey={metric} radius={4} isAnimationActive>
                  {rows.map((r) => <Cell key={r.key} fill={r.key === highlight ? "var(--chart-warn)" : "var(--chart-1)"} />)}
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-2 text-xs text-muted">Dashed line: all trials ({avg.toFixed(1)}%).</p>
    </section>
  );
}

function Reasons({ d }: { d: D }) {
  const max = Math.max(...d.reasons.map((r) => r.pct_of_terminated));
  return (
    <section className="card p-5" aria-labelledby="reasons-h">
      <h3 id="reasons-h" className="text-base font-semibold">Why trials were stopped</h3>
      <p className="mt-1 text-[13px] text-muted">Share of the {num(d.totals.terminated)} terminated trials, by keyword-derived reason class.</p>
      <ul className="mt-4 space-y-3">
        {d.reasons.map((r) => (
          <li key={r.key}>
            <div className="flex items-baseline justify-between text-sm"><span className={cx("font-medium", r.key === "other_unspecified" && "text-high")}>{r.label}</span><span className="num text-muted"><strong className="text-ink">{r.pct_of_terminated.toFixed(1)}%</strong> · {num(r.trials)}</span></div>
            <div className="mt-1.5 h-3 rounded-full bg-surface2"><div className={cx("h-full rounded-full", r.key === "other_unspecified" ? "bg-high" : "bg-accent")} style={{ width: `${(r.pct_of_terminated / max) * 100}%`, transition: "width .8s cubic-bezier(.16,1,.3,1)" }} /></div>
          </li>
        ))}
      </ul>
      <p className="mt-4 rounded-lg border border-high/40 bg-high/10 px-4 py-3 text-[13px] leading-relaxed">
        <strong>“Other / unspecified” is the largest group: {d.other_reason.pct_of_terminated.toFixed(1)}% of terminated trials.</strong>{" "}
        {num(d.other_reason.no_reason_given)} of them ({d.other_reason.no_reason_pct_of_terminated.toFixed(1)}% of all terminated) gave no reason at all; the rest have a reason our keyword rules do not recognise (drug supply, investigator left, regulatory hold…). The reason classes describe only trials where a reason was stated and matched.
      </p>
    </section>
  );
}

export default function Dashboard() {
  const { data: d, error, loading } = useAsync(getDashboard, []);
  const [metric, setMetric] = useState<Metric>("terminated_pct");
  const avg = d ? d.totals[metric === "terminated_pct" ? "terminated_pct" : "low_accrual_pct"] : 0;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <h1 className="display text-4xl font-semibold sm:text-5xl">Dashboard</h1>
      <p className="mt-3 max-w-3xl text-lg leading-relaxed text-muted">
        What the {d ? num(d.totals.trials) : "41,380"} trials in the data say. Phase 2, 2/3 and 3 trials with a drug or biological intervention, started 2008–2019, that ended as completed or terminated.
        Withdrawn, unknown-status and still-running trials are excluded, so true non-completion is probably higher.
      </p>
      {error ? <div className="mt-8"><ErrorState kind="offline" title="Dashboard unavailable" message="The data summary could not be loaded." onRetry={() => location.reload()} /></div> : (
        <>
          <div role="group" aria-label="Metric" className="mt-8 inline-flex rounded-xl border border-line bg-surface p-1">
            {(Object.keys(METRIC_LABEL) as Metric[]).map((m) => (
              <button key={m} aria-pressed={metric === m} onClick={() => setMetric(m)} className={cx("rounded-lg px-4 py-2 text-sm font-semibold min-h-[40px]", metric === m ? "bg-accent text-accent-ink" : "text-muted hover:text-ink")}>{METRIC_LABEL[m]}</button>
            ))}
          </div>
          {loading || !d ? <div className="mt-6 grid gap-5 lg:grid-cols-2"><Skeleton className="h-80 lg:col-span-2" /><Skeleton className="h-72" /><Skeleton className="h-72" /></div> : (
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              <div className="lg:col-span-2">
                <RateChart title="By therapeutic area" horizontal rows={[...d.by_area].sort((a, b) => b[metric] - a[metric])} metric={metric} avg={avg} highlight="other"
                  note={`Areas come from a keyword mapping on condition names. “Other (not mapped)” (shown in orange) holds ${num(d.other_area.trials)} trials (${d.other_area.pct.toFixed(0)}%) whose conditions the mapping did not recognise, so treat area rates as approximate.`} />
              </div>
              <RateChart title="By phase" rows={d.by_phase} metric={metric} avg={avg} note="Phase 2/3 and Phase 1/2 are combined designs (a Phase 1/2 trial is in scope because it includes Phase 2)." />
              <RateChart title="By lead sponsor class" rows={[...d.by_sponsor].sort((a, b) => b[metric] - a[metric])} metric={metric} avg={avg} note="INDUSTRY = company · OTHER = mostly universities and hospitals · NIH/FED/OTHER_GOV = government · NETWORK = research network · INDIV = individual." />
              <div className="lg:col-span-2"><RateChart title="By start year" line rows={d.by_year} metric={metric} avg={avg} note="The overall rate rises for 2017–2019 starts. Terminations that cite COVID-19 explain part of this, not all of it." /></div>
              <div className="lg:col-span-2"><Reasons d={d} /></div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
