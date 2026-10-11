import { ExternalLink, Info, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { analyze, Analysis, ApiError, getReliability } from "../lib/api";
import { statusText } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { Drivers, PercentileBars, RiskCard, SimilarCard, SimilarShare } from "../components/Results";
import { ReliabilityPanel } from "../components/Reliability";
import { ErrorState, SectionTitle, Skeleton } from "../components/ui";

function ResultSkeleton({ slow }: { slow: boolean }) {
  return (
    <div aria-busy="true">
      <p role="status" className="mb-4 text-sm text-muted">{slow ? "Still working. ClinicalTrials.gov can be slow; stored data are used if it does not answer." : "Fetching the record and finding similar trials…"}</p>
      <Skeleton className="mb-5 h-16" />
      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-5"><Skeleton className="h-60" /><Skeleton className="h-44" /></div>
        <div className="space-y-4 lg:col-span-7"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
      </div>
    </div>
  );
}

function Body({ a }: { a: Analysis }) {
  const rel = useAsync(getReliability, []);
  const s = a.similar, top = s.nearest_terminated;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="min-w-0 max-w-3xl">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            {a.trial.nct_id ? <a href={a.trial.link!} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-accent hover:underline num">{a.trial.nct_id}<ExternalLink size={13} aria-label="opens ClinicalTrials.gov in a new tab" /></a> : <span className="font-semibold text-accent">Manual design</span>}
            {a.trial.status && <span className="chip border-line bg-surface2 text-ink">{statusText(a.trial.status)}</span>}
            {a.source === "stored_snapshot" && <span className="chip border-mid/50 bg-mid/10 text-ink" title={a.source_note ?? undefined}><Info size={12} aria-hidden />Stored copy: status may be out of date</span>}
            <span className="chip border-line bg-surface2 text-ink">Phase {a.trial.phase}</span>
            <span className="chip border-line bg-surface2 text-ink">{a.trial.therapeutic_area}</span>
          </p>
          <h1 className="display mt-1 line-clamp-2 text-xl font-semibold leading-tight sm:text-2xl">{a.trial.title}</h1>
        </div>
        <Link to="/analyze" className="btn-ghost !min-h-[40px] !py-1.5 text-sm"><Search size={15} aria-hidden /> New analysis</Link>
      </div>


      <div className="grid gap-4 lg:grid-cols-12">
        <div className="lg:col-span-7"><RiskCard a={a} /></div>
        <div className="lg:col-span-5"><SimilarShare a={a} /></div>
      </div>

      <section aria-labelledby="near-h" className="mt-4">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h2 id="near-h" className="text-[15px] font-semibold">Nearest terminated trials and why they stopped</h2>
          <span className="hidden text-xs text-muted sm:inline">reasons as written in the registry, with our classification</span>
        </div>
        <p className="mb-3 text-[13px] leading-snug text-muted">Similarity is text-based (conditions, interventions, design), not biological mechanism. Scores of 0.4–0.5 mean moderately related, so read these as context, not as matches.</p>
        {!s.found ? <ErrorState kind="empty" title="No similar trials found" message="No past trial shares condition or intervention words with this design, so there is nothing to compare against." />
          : <ul className="grid gap-3 md:grid-cols-3">{top.slice(0, 3).map((t, i) => <SimilarCard key={t.nct_id} t={t} i={i} compact />)}</ul>}
        {s.found && top.length > 3 && (
          <ul className="mt-3 grid gap-3 md:grid-cols-2" aria-label="More nearest terminated trials">{top.slice(3).map((t, i) => <SimilarCard key={t.nct_id} t={t} i={i + 3} />)}</ul>
        )}
      </section>

      {(a.notes.length > 0 || a.source_note) && (
        <ul className="mt-6 space-y-2">
          {a.source_note && <li className="flex gap-2.5 rounded-xl border border-mid/40 bg-mid/10 px-4 py-2.5 text-[13px]"><Info size={16} className="mt-0.5 shrink-0 text-mid" aria-hidden />{a.source_note}</li>}
          {a.notes.map((n) => <li key={n.kind} className="flex gap-2.5 rounded-xl border border-line bg-surface2 px-4 py-2.5 text-[13px] text-muted"><Info size={16} className="mt-0.5 shrink-0" aria-hidden />{n.text}</li>)}
        </ul>
      )}

      <div className="mt-14 grid gap-12 lg:grid-cols-2">
        <section aria-labelledby="drv-h">
          <SectionTitle eyebrow="Descriptive" title="What moves the estimate"><span id="drv-h" className="sr-only">drivers</span>Features that differ from a typical trial and shift the estimate. Associations in past records, not causes.</SectionTitle>
          <Drivers a={a} />
        </section>
        <section aria-labelledby="chk-h">
          <SectionTitle eyebrow="Descriptive" title="Design checks"><span id="chk-h" className="sr-only">checks</span>Where this design sits among its 25 most similar trials. An extreme value is only unusual for that group; it does not say anything is wrong or what would change the outcome.</SectionTitle>
          <PercentileBars checks={a.design_checks} />
        </section>
      </div>

      <section className="mt-14" aria-labelledby="rel-h">
        <SectionTitle eyebrow="Calibrate your trust" title="How reliable is this?"><span id="rel-h" className="sr-only">reliability</span>
          Numbers below are read from the benchmark report (BENCHMARK.md) on trials that started in 2017–2019, which the models never saw during training.
        </SectionTitle>
        {rel.loading ? <Skeleton className="h-64" /> : rel.data ? <ReliabilityPanel data={rel.data} /> : <p className="text-muted">Reliability figures could not be loaded.</p>}
      </section>
    </div>
  );
}

export default function Results() {
  const [sp] = useSearchParams();
  const nct = sp.get("nct"), manual = sp.get("manual");
  const [state, setState] = useState<{ a?: Analysis; err?: ApiError; loading: boolean }>({ loading: true });
  const [slow, setSlow] = useState(false);
  const [tick, setTick] = useState(0);

  const run = useCallback(() => {
    const ctl = new AbortController();
    let body: { nct_id?: string; design?: Record<string, unknown> } | null = null;
    if (nct) body = { nct_id: nct };
    else if (manual) { try { body = { design: JSON.parse(sessionStorage.getItem("tr-design") || "null") }; } catch { body = null; } }
    if (!body || (!body.nct_id && !body.design)) { setState({ loading: false, err: new ApiError("empty", "There is nothing to analyze yet. Enter an NCT ID or describe a design.", 0) }); return () => ctl.abort(); }
    setState({ loading: true }); setSlow(false);
    const t = setTimeout(() => setSlow(true), 4000);
    analyze(body, ctl.signal).then((a) => { clearTimeout(t); setState({ a, loading: false }); document.title = `${a.trial.nct_id ?? "Manual design"} · TrialRadar`; },
      (e) => { clearTimeout(t); if ((e as Error).name !== "AbortError") setState({ loading: false, err: e instanceof ApiError ? e : new ApiError("server_error", "Something went wrong.", 0) }); });
    return () => { clearTimeout(t); ctl.abort(); };
  }, [nct, manual]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(run, [run, tick]);

  const { a, err, loading } = state;
  return (
    <div className="mx-auto max-w-6xl px-4 py-3 sm:px-6 sm:py-4">
      {loading && <ResultSkeleton slow={slow} />}
      {err && (
        <ErrorState kind={err.code === "unreachable" || err.code === "server_down" ? "offline" : err.code === "not_found" || err.code === "empty" ? "empty" : "error"}
          title={err.code === "not_found" ? "Trial not found" : err.code === "invalid_nct" ? "That doesn't look like an NCT ID" : err.code === "unreachable" || err.code === "server_down" ? "Can't reach the data" : err.code === "empty" ? "Nothing to analyze" : "Something went wrong"}
          message={err.message} onRetry={err.code === "empty" || err.code === "invalid_nct" || err.code === "not_found" ? undefined : () => setTick((n) => n + 1)} />
      )}
      {a && <Body a={a} />}
    </div>
  );
}
