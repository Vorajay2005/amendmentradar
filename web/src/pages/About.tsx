import { getReliability } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { ReliabilityPanel } from "../components/Reliability";
import { Accordion, ErrorState, SectionTitle, Skeleton } from "../components/ui";

const GLOSSARY: [string, string][] = [
  ["Terminated", "The registry status is TERMINATED: the trial stopped early."],
  ["Low accrual", "Terminated because too few participants joined. “Accrual” and “enrollment” mean the same here."],
  ["ROC-AUC", "How well a score ranks trials. 0.5 is a coin flip, 1.0 is perfect."],
  ["Calibration", "Whether “5%” really means about 5 in 100."],
  ["Band relative to 2017–2019", "Lower, middle or upper third of the model's scores for trials that started in 2017–2019."],
  ["Masking / allocation", "Who does not know which treatment a participant gets / whether assignment is random."],
  ["Data monitoring committee", "An independent group that reviews data during a trial."],
  ["Phase 2 / 3", "Mid-stage (efficacy, dosing) and late-stage (confirmatory) trials."],
];

export default function About() {
  const rel = useAsync(getReliability, []);
  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="display text-4xl font-semibold sm:text-5xl">About & limits</h1>
      <div className="mt-6 space-y-4 text-[17px] leading-relaxed">
        <p><strong>What TrialRadar does.</strong> It learned from every Phase 2 and 3 drug or biological trial (including Phase 1/2 and 2/3 designs; see Scope below) in ClinicalTrials.gov that started in 2008–2019 and ended as completed or terminated. From design fields only (phase, masking, arms and outcomes, eligibility length, sponsor type, therapeutic area…) it estimates how likely a similar design was to stop early, and shows the most similar past trials with the reasons they gave.</p>
        <p><strong>What it is not.</strong> It does not approve or reject a design, and it never says that changing a value will change an outcome. It describes associations in past records; it does not establish causes.</p>
        <p className="rounded-xl border border-line bg-surface2 px-4 py-3 text-[15px]"><strong>Registry edits are the data, not the truth.</strong> The API returns each trial's <em>current</em> record, so the “registered design” features may include edits made after registration. Public version histories could not be obtained, so we could not check this directly.</p>
      </div>

      <section className="mt-12" aria-labelledby="rel-about">
        <SectionTitle eyebrow="Benchmark" title="How reliable is this?">
          <span id="rel-about" className="sr-only">reliability</span>Time split by start year: trained on 2008–2016, tested once on 2017–2019. Hyperparameters were fixed in advance and nothing was tuned on the test set. Read from BENCHMARK.md.
        </SectionTitle>
        {rel.loading ? <Skeleton className="h-96" /> : rel.data ? <ReliabilityPanel data={rel.data} full /> : <ErrorState kind="offline" title="Benchmark unavailable" message="BENCHMARK.md could not be read by the server." />}
      </section>

      <section className="mt-12">
        <SectionTitle eyebrow="Method" title="How labels are decided" />
        <div className="space-y-3">
          <Accordion title="Terminated and low accrual" defaultOpen>
            <p><strong>terminated</strong> is 1 for status TERMINATED and 0 for COMPLETED. <strong>terminated for low accrual</strong> is terminated <em>and</em> the stated reason matches a recruitment word together with a difficulty word (slow, low, poor, insufficient, lack of, unable…). Bare words such as “patients” or “slow” alone never match.</p>
            <p className="mt-2">Reasons are classified by ordered keyword rules, <strong>first match wins</strong>: safety, then efficacy or futility, then sponsor or business, then low accrual, then other or unspecified. Negations such as “not based on safety concerns” are removed first.</p>
          </Accordion>
          <Accordion title="Known keyword misfires and the rule-order effect">
            <p>A trial that states an accrual problem and then says “the sponsor decided to stop” is labeled sponsor / business, so low accrual is <strong>undercounted</strong>. Passing mentions can inflate the safety class (for example a plan that “provided safety data”). A reason with a typo or no recruitment word (“lack of patients number”) falls in other / unspecified. Details and examples are in docs/labels.md in the repository.</p>
          </Accordion>
          <Accordion title="Features and leakage guard">
            <p>Features are registered-design proxies only: phase, masking, allocation, arms, interventions, outcome counts, eligibility length and counts, ages, sex, conditions, therapeutic area, sponsor class, start year, monitoring committee. Enrollment, locations, status, other dates, reasons for stopping and results are never used as features, and an automated test fails if one reaches the model.</p>
          </Accordion>
          <Accordion title="Scope: Phase 1/2 trials are included" defaultOpen>
            <p>{"The data set includes 4,848 Phase 1/2 trials (11.7%): the API's Phase 2 filter admits them."}</p>
          </Accordion>
          <Accordion title="Near-duplicate neighbours" defaultOpen>
            <p>{"About 10% of trials have a near-duplicate neighbour (similarity >= 0.95), such as a sister or extension study, which can influence the 'X of 25' share for those trials."}</p>
          </Accordion>
          <Accordion title="Selection effect">
            <p>Withdrawn, unknown-status and still-running trials are excluded, so the observed termination rate (17.1%) probably understates true non-completion across the registry.</p>
          </Accordion>
        </div>
      </section>

      <section className="mt-12">
        <SectionTitle eyebrow="Reference" title="Glossary" />
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">{GLOSSARY.map(([t, d]) => <div key={t}><dt className="font-semibold">{t}</dt><dd className="text-muted">{d}</dd></div>)}</dl>
      </section>

      <section className="mt-12">
        <SectionTitle eyebrow="Provenance" title="Sources and license" />
        <p className="leading-relaxed text-muted">
          Data: <a className="underline" href="https://clinicaltrials.gov" target="_blank" rel="noreferrer">ClinicalTrials.gov</a>, U.S. National Library of Medicine, public API v2 (no key).
          Context: Tufts CSDD figures quoted on the Regeneron challenge sheet “Site Unseen”: about 11% of chosen sites enroll zero patients and 37% enroll fewer than promised.
          Code: MIT license, <a className="underline" href="https://github.com/Vorajay2005/amendmentradar" target="_blank" rel="noreferrer">github.com/Vorajay2005/amendmentradar</a>. No LLMs and no API keys are used.
        </p>
      </section>
    </div>
  );
}
