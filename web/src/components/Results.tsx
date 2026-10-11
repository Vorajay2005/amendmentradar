import { motion, useReducedMotion } from "framer-motion";
import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { Analysis, Driver, SimilarTrial } from "../lib/api";
import { bandKey, pct } from "../lib/format";
import { cx, CountUp, Help } from "./ui";

const BANDS = ["Lower third", "Middle third", "Upper third"] as const;
const BAND_CLASS = { low: "bg-low text-low", mid: "bg-mid text-mid", high: "bg-high text-high" } as const;

/** Three-segment meter. Position and text carry the meaning, not colour alone. */
export function RiskMeter({ band }: { band: string }) {
  const i = BANDS.indexOf(band as (typeof BANDS)[number]);
  return (
    <div role="img" aria-label={`Relative risk band: ${band}, segment ${i + 1} of 3`}>
      <div className="relative grid grid-cols-3 gap-1.5">
        {BANDS.map((b, k) => {
          const key = ["low", "mid", "high"][k] as "low" | "mid" | "high";
          return (
            <div key={b}>
              <div className={cx("h-3 rounded-full", BAND_CLASS[key].split(" ")[0], k === i ? "opacity-100" : "opacity-20")} />
              <p className={cx("mt-1.5 text-[11px] font-semibold uppercase tracking-wide", k === i ? "text-ink" : "text-muted")}>{["Lower", "Middle", "Upper"][k]}</p>
            </div>
          );
        })}
        <motion.span aria-hidden className="absolute -top-2 h-0 w-0 border-x-[6px] border-t-[8px] border-x-transparent border-t-ink"
          initial={false} animate={{ left: `calc(${(i + 0.5) * 33.333}% - 6px)` }} transition={{ type: "spring", stiffness: 140, damping: 18 }} />
      </div>
    </div>
  );
}

export function RiskCard({ a }: { a: Analysis }) {
  const l = a.low_accrual;
  const k = bandKey(l.band);
  return (
    <section aria-labelledby="risk-h" className="card h-full p-5">
      <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div>
          <p className="eyebrow">Lead result</p>
          <h2 id="risk-h" className="mt-1 text-[15px] font-semibold">
            Risk of early termination for low accrual
            <Help label="What is low accrual?">Too few participants joined the trial. “Accrual” and “enrollment” mean the same thing here.</Help>
          </h2>
          <p className={cx("display mt-2 text-[2.4rem] font-semibold leading-none", BAND_CLASS[k].split(" ")[1])}>{l.band}</p>
          <p className="mt-1.5 text-sm text-muted">relative to trials starting 2017–2019</p>
        </div>
        <div className="flex flex-col justify-end">
          <RiskMeter band={l.band} />
          <dl className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <dt className="text-xs text-muted">Estimated chance
                <Help label="How good is this number?">Calibration was good on 2017–2019 trials (see “How reliable is this?” below), but this is a base-rate-anchored estimate, not a prediction for this specific trial.</Help>
              </dt>
              <dd className="display text-2xl font-semibold"><CountUp value={l.probability} /></dd>
            </div>
            <div>
              <dt className="text-xs text-muted">2017–2019 average</dt>
              <dd className="display text-2xl font-semibold text-muted"><span className="num">{pct(l.average_2017_2019)}</span></dd>
            </div>
          </dl>
        </div>
      </div>
      <div className="mt-4 grid gap-2 border-t border-line pt-3 text-[13px] leading-snug text-muted sm:grid-cols-2 sm:gap-8">
        {l.band_observed_rate != null && (
          <p>In 2017–2019, <strong className="num text-ink">{pct(l.band_observed_rate)}</strong> of trials in this band were terminated for low accrual. Ranking skill is modest (AUC <span className="num">{l.test_auc.toFixed(2)}</span>).</p>
        )}
        <p><strong className="text-ink">Overall termination (any reason):</strong> {a.overall.band.toLowerCase()}, relative only.
          <Help label="Why no percentage?">The overall model ranks trials only weakly (AUC {a.overall.test_auc.toFixed(2)}) and under-predicts for 2017–2019 starts (partly COVID-19), so we show a relative band, never a percentage.</Help>
        </p>
      </div>
    </section>
  );
}

export function SimilarShare({ a }: { a: Analysis }) {
  const reduce = useReducedMotion();
  const s = a.similar;
  if (!s.found) return null;
  return (
    <section aria-labelledby="share-h" className="card h-full p-5">
      <p className="eyebrow">Similar trials</p>
      <h2 id="share-h" className="mt-1">
        <span className="display text-[2.4rem] font-semibold leading-none"><CountUp value={s.n_terminated} decimals={0} suffix="" scale={1} /> of the 25</span>
        <span className="mt-1 block text-[15px] font-semibold">most similar trials were terminated</span>
      </h2>
      <div className="mt-3 flex items-center gap-4">
        <div className="grid shrink-0 grid-cols-5 gap-1.5" role="img" aria-label={`${s.n_terminated} of 25 similar trials were terminated`}>
          {Array.from({ length: 25 }, (_, i) => (
            <motion.span key={i} className={cx("h-3.5 w-3.5 rounded-full border", i < s.n_terminated ? "border-high bg-high" : "border-line bg-surface2")}
              initial={reduce ? false : { scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.02 * i, type: "spring", stiffness: 260, damping: 18 }} />
          ))}
        </div>
        <p className="text-[13px] leading-snug text-muted">
          <strong className="num text-ink">{pct(s.n_terminated / 25, 0)}</strong> here, versus <strong className="num text-ink">{pct(s.base_rate_all)}</strong> across all trials in the data.
        </p>
      </div>
    </section>
  );
}

const REASON_STYLE: Record<string, string> = {
  low_accrual: "border-accent/50 bg-accent-soft text-ink",
  safety: "border-high/50 bg-high/10 text-high",
  efficacy_futility: "border-mid/50 bg-mid/10 text-mid",
  sponsor_business: "border-line bg-surface2 text-ink",
  other_unspecified: "border-dashed border-muted/50 bg-transparent text-muted",
};
export function ReasonChip({ code, label }: { code: string; label: string }) {
  return <span className={cx("chip", REASON_STYLE[code] ?? REASON_STYLE.other_unspecified)}>{label}</span>;
}

export function SimilarCard({ t, i, compact = false }: { t: SimilarTrial; i: number; compact?: boolean }) {
  return (
    <motion.li initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 * i, duration: 0.35 }}
      className="card h-full p-4">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted">
        <a href={t.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-accent underline-offset-2 hover:underline">
          {t.nct_id}<ExternalLink size={12} aria-label="opens ClinicalTrials.gov in a new tab" />
        </a>
        <span>· started {t.start_year}</span><span>· similarity <span className="num">{t.similarity.toFixed(2)}</span></span>
      </div>
      <h3 className={cx("mt-1 text-sm font-semibold leading-snug", compact && "line-clamp-2")} title={t.title}>{t.title}</h3>
      <div className="mt-2"><ReasonChip code={t.stop_reason} label={t.stop_reason_label} /></div>
      <p className="mt-1.5 text-[13px] leading-snug text-muted">
        {t.why_stopped ? <q className={cx("italic", compact && "line-clamp-2")}>{t.why_stopped}</q> : <span className="italic">No reason was given.</span>}
      </p>
    </motion.li>
  );
}

export function PercentileBars({ checks }: { checks: Analysis["design_checks"] }) {
  if (!checks.length) return <p className="text-muted">Design percentiles need at least one similar trial.</p>;
  return (
    <ul className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
      {checks.map((c, i) => (
        <li key={c.measure}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-medium">{c.measure}</span>
            <span className="num text-muted"><strong className="text-ink">{c.value}</strong> · similar median {c.similar_median}</span>
          </div>
          <div className="relative mt-2 h-2.5 rounded-full bg-surface2" role="img" aria-label={`${c.measure}: higher than about ${c.percentile}% of the 25 similar trials`}>
            <motion.div className="h-full rounded-full bg-accent/70" initial={{ width: 0 }} animate={{ width: `${Math.max(c.percentile, 2)}%` }} transition={{ delay: 0.05 * i, duration: 0.7, ease: [0.16, 1, 0.3, 1] }} />
            <span className="absolute top-1/2 h-4 w-0.5 -translate-y-1/2 bg-muted/60" style={{ left: "50%" }} aria-hidden />
          </div>
          <p className="mt-1 text-xs text-muted">
            Higher than about <span className="num font-semibold text-ink">{c.percentile}%</span> of similar trials
            {c.note && <span className="ml-1.5 rounded bg-surface2 px-1.5 py-0.5 font-semibold text-ink">{c.note}</span>}
          </p>
        </li>
      ))}
    </ul>
  );
}

function DriverList({ items }: { items: Driver[] }) {
  if (!items.length) return null;
  return (
    <ul className="space-y-2">
      {items.map((d) => (
        <li key={d.feature} className="flex items-start gap-3 rounded-lg bg-surface2 px-3 py-2.5 text-sm">
          {d.direction === "up" ? <ArrowUp size={16} className="mt-0.5 shrink-0 text-high" aria-label="raises the estimate" /> : <ArrowDown size={16} className="mt-0.5 shrink-0 text-low" aria-label="lowers the estimate" />}
          <span><strong>{d.name}</strong>: <span className="num">{d.value}</span> <span className="text-muted">(typical trial: <span className="num">{d.typical}</span>)</span></span>
        </li>
      ))}
    </ul>
  );
}

export function Drivers({ a }: { a: Analysis }) {
  const [tab, setTab] = useState<"low_accrual" | "overall">("low_accrual");
  const d = a.drivers[tab];
  return (
    <div>
      <div role="tablist" aria-label="Which estimate" className="mb-3 inline-flex rounded-xl border border-line bg-surface p-1">
        {([["low_accrual", "Low accrual"], ["overall", "Overall termination"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cx("rounded-lg px-3.5 py-2 text-sm font-semibold min-h-[40px]", tab === k ? "bg-accent text-accent-ink" : "text-muted hover:text-ink")}>{l}</button>
        ))}
      </div>
      <div role="tabpanel" className="space-y-2">
        {!d.up.length && !d.down.length ? <p className="text-muted">No single feature stands out from a typical trial.</p> : (<><DriverList items={d.up} /><DriverList items={d.down} /></>)}
      </div>
      <p className="mt-3 text-xs text-muted">▲ raises / ▼ lowers the estimate compared with a typical 2008–2016 trial. These are associations in past records, not causes, and not advice to change anything.</p>
    </div>
  );
}
