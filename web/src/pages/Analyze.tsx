import { motion } from "framer-motion";
import { ArrowRight, FlaskConical, Search } from "lucide-react";
import { FormEvent, ReactNode, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getExamples } from "../lib/api";
import { nctOk } from "../lib/format";
import { useAsync } from "../lib/hooks";
import { cx, Help, Skeleton } from "../components/ui";

const KIND_LABEL = { hit: "Retrospective hit", miss: "Retrospective miss", new: "Not yet recruiting" } as const;

function Field({ label, help, children, htmlFor }: { label: string; help?: ReactNode; children: ReactNode; htmlFor: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">{label}{help && <Help label={`About ${label}`}>{help}</Help>}</label>
      {children}
    </div>
  );
}
const Select = ({ id, value, set, options }: { id: string; value: string; set: (v: string) => void; options: [string, string][] }) => (
  <select id={id} value={value} onChange={(e) => set(e.target.value)} className="input">{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
);
const Num = ({ id, value, set, min, max }: { id: string; value: number; set: (v: number) => void; min: number; max: number }) => (
  <input id={id} type="number" className="input num" value={value} min={min} max={max} onChange={(e) => set(Number(e.target.value))} />
);

const DEFAULT_ELIG = "Inclusion Criteria:\n- Adults with type 2 diabetes\n- HbA1c 7-10%\n\nExclusion Criteria:\n- Pregnancy\n- Kidney disease";

function ManualForm({ onSubmit }: { onSubmit: (d: Record<string, unknown>) => void }) {
  const [f, setF] = useState({
    phase: "PHASE3", sponsor_class: "INDUSTRY", conditions: "Type 2 diabetes", intervention_names: "metformin, placebo",
    intervention_types: ["DRUG"] as string[], allocation: "RANDOMIZED", intervention_model: "PARALLEL", masking: "DOUBLE",
    n_arms: 2, n_interventions: 2, n_primary: 1, n_secondary: 4, eligibility: DEFAULT_ELIG, min_age: 18, max_age: 0,
    sex: "ALL", healthy_volunteers: false, has_dmc: false, fda_drug: false, start_year: new Date().getFullYear() + 1,
  });
  const set = <K extends keyof typeof f>(k: K) => (v: (typeof f)[K]) => setF((p) => ({ ...p, [k]: v }));
  const [err, setErr] = useState("");
  const toggleType = (t: string) => set("intervention_types")(f.intervention_types.includes(t) ? f.intervention_types.filter((x) => x !== t) : [...f.intervention_types, t]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!f.conditions.trim()) return setErr("Please list at least one condition.");
    if (!f.intervention_types.length) return setErr("Pick at least one intervention type.");
    setErr("");
    onSubmit({ ...f, max_age: f.max_age || null });
  };
  return (
    <form onSubmit={submit} className="space-y-8" noValidate>
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="eyebrow mb-3">1 · Basics</legend>
        <Field label="Phase" htmlFor="phase" help="Phase 2 tests efficacy and dose in patients; Phase 3 confirms in larger groups."><Select id="phase" value={f.phase} set={set("phase")} options={[["PHASE2", "Phase 2"], ["PHASE2/PHASE3", "Phase 2/3"], ["PHASE3", "Phase 3"]]} /></Field>
        <Field label="Lead sponsor class" htmlFor="sponsor" help="INDUSTRY = company. OTHER = e.g. universities and hospitals. NIH / FED / OTHER_GOV = government. NETWORK = research network. INDIV = individual."><Select id="sponsor" value={f.sponsor_class} set={set("sponsor_class")} options={["INDUSTRY", "OTHER", "NIH", "FED", "OTHER_GOV", "NETWORK", "INDIV"].map((x) => [x, x])} /></Field>
        <Field label="Condition(s), comma separated" htmlFor="conds"><input id="conds" className="input" value={f.conditions} onChange={(e) => set("conditions")(e.target.value)} aria-required /></Field>
        <Field label="Intervention name(s), comma separated" htmlFor="ints"><input id="ints" className="input" value={f.intervention_names} onChange={(e) => set("intervention_names")(e.target.value)} /></Field>
        <div className="sm:col-span-2">
          <span className="label" id="types-l">Intervention type(s)</span>
          <div role="group" aria-labelledby="types-l" className="flex flex-wrap gap-2">
            {["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "OTHER"].map((t) => (
              <button type="button" key={t} aria-pressed={f.intervention_types.includes(t)} onClick={() => toggleType(t)}
                className={cx("rounded-full border px-3.5 py-2 text-sm font-semibold min-h-[40px]", f.intervention_types.includes(t) ? "border-accent bg-accent text-accent-ink" : "border-line bg-surface text-muted hover:text-ink")}>{t}</button>
            ))}
          </div>
        </div>
      </fieldset>
      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="eyebrow mb-3">2 · Design</legend>
        <Field label="Allocation" htmlFor="alloc" help="How participants are assigned to arms."><Select id="alloc" value={f.allocation} set={set("allocation")} options={[["RANDOMIZED", "Randomized"], ["NON_RANDOMIZED", "Non-randomized"], ["NA", "Not applicable"]]} /></Field>
        <Field label="Intervention model" htmlFor="model" help="Parallel: each group gets one treatment. Crossover: everyone receives each treatment in turn."><Select id="model" value={f.intervention_model} set={set("intervention_model")} options={["PARALLEL", "CROSSOVER", "SINGLE_GROUP", "FACTORIAL", "SEQUENTIAL"].map((x) => [x, x.replace("_", " ")])} /></Field>
        <Field label="Masking (blinding)" htmlFor="mask" help="Who does not know which treatment is given."><Select id="mask" value={f.masking} set={set("masking")} options={["NONE", "SINGLE", "DOUBLE", "TRIPLE", "QUADRUPLE"].map((x) => [x, x])} /></Field>
        <Field label="Arms" htmlFor="arms"><Num id="arms" value={f.n_arms} set={set("n_arms")} min={1} max={20} /></Field>
        <Field label="Interventions" htmlFor="nint"><Num id="nint" value={f.n_interventions} set={set("n_interventions")} min={1} max={20} /></Field>
        <Field label="Planned start year" htmlFor="yr" help="Models learned from 2008–2019 starts; later years are scored as 2019."><Num id="yr" value={f.start_year} set={set("start_year")} min={2000} max={2040} /></Field>
        <Field label="Primary outcomes" htmlFor="npri"><Num id="npri" value={f.n_primary} set={set("n_primary")} min={1} max={20} /></Field>
        <Field label="Secondary outcomes" htmlFor="nsec"><Num id="nsec" value={f.n_secondary} set={set("n_secondary")} min={0} max={50} /></Field>
      </fieldset>
      <fieldset className="grid gap-4 sm:grid-cols-4">
        <legend className="eyebrow mb-3">3 · Eligibility and oversight</legend>
        <div className="sm:col-span-4">
          <Field label="Eligibility criteria" htmlFor="elig" help="Paste the text. Bulleted lines and an “Exclusion Criteria” heading are used to count inclusion and exclusion items.">
            <textarea id="elig" rows={6} className="input font-mono text-[13px]" value={f.eligibility} onChange={(e) => set("eligibility")(e.target.value)} />
          </Field>
        </div>
        <Field label="Min age (years)" htmlFor="minage"><Num id="minage" value={f.min_age} set={set("min_age")} min={0} max={120} /></Field>
        <Field label="Max age (0 = none)" htmlFor="maxage"><Num id="maxage" value={f.max_age} set={set("max_age")} min={0} max={120} /></Field>
        <Field label="Sex" htmlFor="sex"><Select id="sex" value={f.sex} set={set("sex")} options={[["ALL", "All"], ["FEMALE", "Female"], ["MALE", "Male"]]} /></Field>
        <div className="flex flex-col justify-end gap-2 pb-1">
          {([["healthy_volunteers", "Healthy volunteers", "Whether people without the condition may join."], ["has_dmc", "Data monitoring committee", "An independent group that reviews safety and efficacy data during the trial."], ["fda_drug", "FDA-regulated drug", ""]] as const).map(([k, l, h]) => (
            <label key={k} className="flex min-h-[28px] items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[rgb(var(--accent))]" checked={f[k]} onChange={(e) => set(k)(e.target.checked)} />{l}{h && <Help label={`About ${l}`}>{h}</Help>}</label>
          ))}
        </div>
      </fieldset>
      {err && <p role="alert" className="rounded-lg border border-high/40 bg-high/10 px-4 py-3 text-sm font-medium text-high">{err}</p>}
      <button type="submit" className="btn-primary w-full sm:w-auto">Analyze this design <ArrowRight size={18} aria-hidden /></button>
    </form>
  );
}

export default function Analyze() {
  const nav = useNavigate();
  const ex = useAsync(getExamples, []);
  const [tab, setTab] = useState<"nct" | "manual">("nct");
  const [nct, setNct] = useState("");
  const [err, setErr] = useState("");
  const go = (id: string) => nav(`/results?nct=${encodeURIComponent(id.trim().toUpperCase())}`);
  const submitNct = (e: FormEvent) => {
    e.preventDefault();
    if (!nctOk(nct)) return setErr("An NCT ID looks like NCT01234567 (NCT followed by 8 digits).");
    go(nct);
  };
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="display text-4xl font-semibold sm:text-5xl">Analyze a trial</h1>
      <p className="mt-3 max-w-2xl text-lg leading-relaxed text-muted">Look up a registered trial by its NCT ID (works for trials that have not started yet) or describe a design you are planning.</p>

      <section aria-labelledby="demo-h" className="mt-8">
        <h2 id="demo-h" className="eyebrow mb-3">Demo examples · one click</h2>
        <ul className="grid gap-3 md:grid-cols-3">
          {ex.loading ? [0, 1, 2].map((i) => <li key={i}><Skeleton className="h-36" /></li>) : ex.data?.map((e, i) => (
            <motion.li key={e.nct_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 * i }}>
              <button onClick={() => go(e.nct_id)} className="card group flex h-full w-full flex-col p-4 text-left transition-colors hover:border-accent">
                <span className="flex items-center justify-between gap-2">
                  <span className="chip border-line bg-surface2 text-ink">{KIND_LABEL[e.kind]}</span>
                  <ArrowRight size={16} className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
                </span>
                <span className="mt-2 text-[15px] font-semibold leading-snug">{e.title}</span>
                <span className="num text-xs font-semibold text-accent">{e.nct_id}</span>
                <span className="mt-1 text-[13px] leading-snug text-muted">{e.blurb}</span>
                <span className="mt-auto pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{e.tag}</span>
              </button>
            </motion.li>
          ))}
          {ex.error && <li className="text-sm text-muted md:col-span-3">Examples could not be loaded, but you can still enter an NCT ID below.</li>}
        </ul>
      </section>

      <section className="card mt-8 p-5 sm:p-7">
        <div role="tablist" aria-label="Input method" className="mb-6 inline-flex rounded-xl border border-line bg-bg p-1">
          {([["nct", "NCT ID", Search], ["manual", "Manual design", FlaskConical]] as const).map(([k, l, I]) => (
            <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls={`panel-${k}`} onClick={() => setTab(k)}
              className={cx("inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold min-h-[44px]", tab === k ? "bg-accent text-accent-ink" : "text-muted hover:text-ink")}><I size={16} aria-hidden />{l}</button>
          ))}
        </div>
        {tab === "nct" ? (
          <form role="tabpanel" id="panel-nct" aria-labelledby="tab-nct" onSubmit={submitNct} noValidate>
            <label htmlFor="nct" className="label">ClinicalTrials.gov NCT ID</label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input id="nct" className="input num sm:max-w-sm" placeholder="NCT01234567" value={nct} autoComplete="off" spellCheck={false}
                aria-invalid={!!err} aria-describedby={err ? "nct-err" : undefined} onChange={(e) => { setNct(e.target.value); setErr(""); }} />
              <button className="btn-primary" type="submit">Analyze <ArrowRight size={18} aria-hidden /></button>
            </div>
            {err && <p id="nct-err" role="alert" className="mt-2 text-sm font-medium text-high">{err}</p>}
            <p className="mt-3 text-sm text-muted">We fetch the current public record from ClinicalTrials.gov. If you are offline, stored copies are used for trials in our data.</p>
          </form>
        ) : (
          <div role="tabpanel" id="panel-manual" aria-labelledby="tab-manual">
            <ManualForm onSubmit={(d) => { try { sessionStorage.setItem("tr-design", JSON.stringify(d)); } catch { /* ignore */ } nav("/results?manual=1"); }} />
          </div>
        )}
      </section>
    </div>
  );
}
