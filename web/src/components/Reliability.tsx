import { motion } from "framer-motion";
import type { AucRow, Reliability } from "../lib/api";
import { aucWord, pct } from "../lib/format";
import { Accordion, cx } from "./ui";

const LAB: Record<string, string> = { terminated: "Overall termination (any reason)", terminated_low_accrual: "Termination for low accrual" };
const MODEL_ORDER = ["Therapeutic-area base rate", "Logistic regression", "Gradient boosting"];

function Forest({ rows }: { rows: AucRow[] }) {
  const lo = 0.45, hi = 0.8, x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="space-y-5">
      {(["terminated_low_accrual", "terminated"] as const).map((lab) => (
        <div key={lab}>
          <h4 className="mb-2 text-sm font-semibold">{LAB[lab]}</h4>
          <ul className="space-y-2">
            {MODEL_ORDER.map((m) => {
              const r = rows.find((q) => q.label === lab && q.model === m);
              if (!r) return null;
              const main = m === "Gradient boosting";
              return (
                <li key={m} className="grid grid-cols-[8.5rem_1fr_6.5rem] items-center gap-3 text-xs sm:grid-cols-[11rem_1fr_8rem]">
                  <span className={cx("truncate", main ? "font-semibold text-ink" : "text-muted")}>{m}</span>
                  <div className="relative h-5" role="img" aria-label={`${m}: AUC ${r.auc.toFixed(3)}, 95% interval ${r.ci_low?.toFixed(3)} to ${r.ci_high?.toFixed(3)}`}>
                    <span className="absolute inset-y-0 w-px bg-muted/50" style={{ left: x(0.5) }} aria-hidden />
                    {r.ci_low != null && r.ci_high != null && (
                      <motion.span className={cx("absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full", main ? "bg-accent" : "bg-muted/50")}
                        initial={{ opacity: 0, scaleX: 0.6 }} whileInView={{ opacity: 1, scaleX: 1 }} viewport={{ once: true }}
                        style={{ left: x(r.ci_low), width: `calc(${x(r.ci_high)} - ${x(r.ci_low)})` }} />
                    )}
                    <span className={cx("absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface", main ? "bg-accent" : "bg-muted")} style={{ left: x(r.auc) }} />
                  </div>
                  <span className="num text-right text-muted">{r.auc.toFixed(3)} <span className="opacity-80">({r.ci_low?.toFixed(2)}–{r.ci_high?.toFixed(2)})</span></span>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <p className="text-xs text-muted">Test-set ROC-AUC with 95% bootstrap intervals (trials starting 2017–2019). The vertical line is a coin flip (0.50); 1.0 would be perfect.</p>
    </div>
  );
}

export function ReliabilityPanel({ data, full = false }: { data: Reliability; full?: boolean }) {
  const gb = (lab: string) => data.main_results.find((r) => r.label === lab && r.model === "Gradient boosting")!;
  const cal = (lab: string) => data.calibration.find((c) => c.label === lab && c.model === "Gradient boosting");
  const low = gb("terminated_low_accrual"), all = gb("terminated"), cLow = cal("terminated_low_accrual"), cAll = cal("terminated");
  const bands = data.band_table.filter((b) => b.label === "terminated_low_accrual");
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="card p-5">
          <p className="eyebrow">Low accrual</p>
          <p className="mt-1 display text-4xl font-semibold num">{low.auc.toFixed(2)} <span className="text-lg font-medium text-muted">AUC · {aucWord(low.auc)}</span></p>
          <p className="mt-1 text-sm text-muted num">95% interval {low.ci_low?.toFixed(2)}–{low.ci_high?.toFixed(2)} on {data.test_positives.terminated_low_accrual} test positives.</p>
          {cLow && <p className="mt-2 text-sm">Well calibrated: predicted <strong className="num">{pct(cLow.mean_predicted)}</strong> vs observed <strong className="num">{pct(cLow.observed)}</strong>.</p>}
        </div>
        <div className="card p-5">
          <p className="eyebrow">Overall termination</p>
          <p className="mt-1 display text-4xl font-semibold num">{all.auc.toFixed(2)} <span className="text-lg font-medium text-muted">AUC · {aucWord(all.auc)}</span></p>
          <p className="mt-1 text-sm text-muted num">95% interval {all.ci_low?.toFixed(2)}–{all.ci_high?.toFixed(2)} on {data.test_positives.terminated.toLocaleString()} test positives.</p>
          {cAll && <p className="mt-2 text-sm">Under-predicts the shifted 2017–2019 period (predicted <strong className="num">{pct(cAll.mean_predicted)}</strong> vs observed <strong className="num">{pct(cAll.observed)}</strong>), so it is shown as a band only.</p>}
        </div>
      </div>

      <div className="card p-5">
        <h3 className="mb-4 text-base font-semibold">How the models compare with simple baselines</h3>
        <Forest rows={data.main_results} />
      </div>

      <div className="card p-5">
        <h3 className="text-base font-semibold">Does the band mean anything? Low accrual, 2017–2019 test period</h3>
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {bands.map((b) => (
            <li key={b.band} className="rounded-xl bg-surface2 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">{b.band}</p>
              <p className="display mt-1 text-3xl font-semibold num">{pct(b.observed_rate)}</p>
              <p className="text-xs text-muted num">terminated for low accrual · {pct(b.share_of_positives, 0)} of all such trials</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">The score separates groups of trials; it does not identify individual ones.</p>
      </div>

      <div className="card p-5">
        <h3 className="text-base font-semibold">Drift</h3>
        <p className="mt-1 text-sm leading-relaxed text-muted">{data.drift_note}</p>
        {full && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[30rem] text-left text-sm num">
              <caption className="sr-only">Termination rate by start year</caption>
              <thead><tr className="text-xs text-muted"><th className="py-1.5 pr-4 font-semibold">Start year</th><th className="pr-4 font-semibold">Trials</th><th className="pr-4 font-semibold">Terminated</th><th className="pr-4 font-semibold">Low accrual</th><th className="font-semibold">COVID-19 cited</th></tr></thead>
              <tbody>{data.drift.map((d) => (
                <tr key={d.year} className="border-t border-line"><td className="py-1.5 pr-4">{d.year}</td><td className="pr-4">{d.trials.toLocaleString()}</td><td className="pr-4">{d.terminated_pct.toFixed(1)}%</td><td className="pr-4">{d.low_accrual_pct.toFixed(1)}%</td><td>{d.covid_cited_pct.toFixed(1)}%</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>

      <Accordion title="Limits (please read)" defaultOpen={full}>
        <ol className="list-decimal space-y-2 pl-5">{data.limits.map((l) => <li key={l}>{l}</li>)}</ol>
      </Accordion>
    </div>
  );
}
