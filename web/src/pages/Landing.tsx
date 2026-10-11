import { motion } from "framer-motion";
import { ArrowRight, BarChart3, Layers, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { getDashboard, getReliability } from "../lib/api";
import { aucWord, num } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { Skeleton } from "../components/ui";

export default function Landing() {
  const rel = useAsync(getReliability, []);
  const dash = useAsync(getDashboard, []);
  const gb = (lab: string) => rel.data?.main_results.find((r) => r.label === lab && r.model === "Gradient boosting");
  const low = gb("terminated_low_accrual"), all = gb("terminated");
  return (
    <div>
      <section className="relative overflow-hidden border-b border-line">
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-60 [background:radial-gradient(60rem_30rem_at_85%_-10%,rgb(var(--accent)/.14),transparent_60%)]" />
        <div className="relative mx-auto grid max-w-6xl gap-10 px-4 pb-14 pt-10 sm:px-6 lg:grid-cols-[1.25fr_1fr] lg:pb-20 lg:pt-12">
          <div>
            <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="eyebrow">For clinical trial designers · Regeneron challenge, HackRU 2026</motion.p>
            <motion.h1 initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
              className="display mt-3 text-[2.5rem] font-semibold leading-[1.05] sm:text-5xl lg:text-[3.3rem]">
              See how trials like yours <span className="text-accent">actually ended.</span>
            </motion.h1>
            <motion.p initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 }} className="mt-4 max-w-xl text-[17px] leading-relaxed text-muted">
              Learned from every Phase 2 and 3 drug or biological trial (including Phase 1/2 and 2/3 designs) in ClinicalTrials.gov that started in 2008–2019 and ended as completed or terminated.
              It estimates the risk of stopping early, especially for low accrual, and shows the most similar trials that did stop, with the reasons they gave.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="mt-6 flex flex-wrap items-center gap-3">
              <Link to="/analyze" className="btn-primary">Analyze a trial <ArrowRight size={18} aria-hidden /></Link>
              <Link to="/about" className="btn-ghost">How reliable is it?</Link>
            </motion.div>
            <div className="mt-5 max-w-xl rounded-xl border border-line bg-surface/80 p-4 text-[15px] leading-relaxed" aria-live="polite">
              <p className="eyebrow mb-1">One honest sentence</p>
              {rel.loading ? <Skeleton className="h-12 w-full" /> : low && all ? (
                <p>
                  On held-out 2017–2019 trials it ranks low-accrual risk with <strong>{aucWord(low.auc)}</strong> accuracy (AUC <span className="num">{low.auc.toFixed(2)}</span>) and overall termination only <strong>{aucWord(all.auc)}ly</strong> (AUC <span className="num">{all.auc.toFixed(2)}</span>):
                  a screening aid for designers, not a verdict.
                </p>
              ) : <p className="text-muted">Performance figures are unavailable right now.</p>}
            </div>
          </div>
          <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15 }} className="card self-center p-6">
            <p className="eyebrow">The evidence base</p>
            {dash.loading ? <div className="mt-4 space-y-3"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : dash.data ? (
              <dl className="mt-4 divide-y divide-line">
                {[["Real trials", num(dash.data.totals.trials), "Phase 2/3 (incl. 1/2), drug or biological, 2008–2019"],
                  ["Terminated early", `${dash.data.totals.terminated_pct.toFixed(1)}%`, `${num(dash.data.totals.terminated)} trials`],
                  ["Terminated for low accrual", `${dash.data.totals.low_accrual_pct.toFixed(1)}%`, `${num(dash.data.totals.low_accrual)} trials (keyword-derived)`]].map(([k, v, s]) => (
                  <div key={k} className="flex items-baseline justify-between gap-4 py-3">
                    <dt className="text-sm font-semibold">{k}<span className="block text-xs font-normal text-muted">{s}</span></dt>
                    <dd className="display num text-3xl font-semibold">{v}</dd>
                  </div>))}
              </dl>
            ) : <p className="mt-3 text-muted">Data summary unavailable.</p>}
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <ul className="grid gap-5 md:grid-cols-3">
          {[[BarChart3, "Estimate", "A low-accrual risk band relative to recent trials, with calibration you can check, and overall termination risk shown as a band only."],
            [Layers, "Compare", "The 25 most similar past trials, how many were terminated, and the 5 nearest terminated ones with the reasons their sponsors stated."],
            [ShieldCheck, "Stay honest", "Every page states the limits: current-record snapshot, keyword-derived reasons, modest accuracy. It assists designers and never approves a protocol."]].map(([Icon, t, d]) => {
            const I = Icon as typeof BarChart3;
            return (
              <li key={t as string} className="card p-6">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent"><I size={22} aria-hidden /></span>
                <h2 className="display mt-4 text-xl font-semibold">{t as string}</h2>
                <p className="mt-1.5 leading-relaxed text-muted">{d as string}</p>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
