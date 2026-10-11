export type Band = "Lower third" | "Middle third" | "Upper third";
export interface SimilarTrial {
  nct_id: string; title: string; start_year: number; similarity: number;
  stop_reason: string; stop_reason_label: string; why_stopped: string; link: string;
}
export interface Driver { feature: string; name: string; value: string; typical: string; direction: "up" | "down" }
export interface Analysis {
  source: "live" | "stored_snapshot" | "manual"; source_note: string | null;
  notes: { kind: string; text: string }[];
  trial: { nct_id: string | null; title: string; status: string | null; link: string | null;
    start_year_on_record: number | null; therapeutic_area: string; phase: string; sponsor_class: string };
  low_accrual: { probability: number; band: Band; band_phrase: string; average_2017_2019: number;
    band_observed_rate: number | null; test_auc: number };
  overall: { band: Band; band_phrase: string; band_observed_rate: number | null; test_auc: number };
  similar: { found: boolean; size: number; n_terminated: number; share_terminated: number | null;
    base_rate_all: number; nearest_terminated: SimilarTrial[] };
  drivers: Record<"low_accrual" | "overall", { up: Driver[]; down: Driver[] }>;
  design_checks: { measure: string; value: string; similar_median: string; percentile: number; note: string }[];
}
export interface Row { key: string; label: string; trials: number; terminated_pct: number; low_accrual_pct: number }
export interface Dashboard {
  totals: { trials: number; terminated: number; terminated_pct: number; low_accrual: number; low_accrual_pct: number };
  by_area: Row[]; by_phase: Row[]; by_sponsor: Row[]; by_year: Row[];
  reasons: { key: string; label: string; trials: number; pct_of_terminated: number }[];
  other_area: { trials: number; pct: number };
  other_reason: { trials: number; pct_of_terminated: number; no_reason_given: number; no_reason_pct_of_terminated: number };
}
export interface AucRow { label: string; model: string; auc: number; ci_low: number | null; ci_high: number | null; pr_auc?: number }
export interface Reliability {
  main_results: AucRow[]; cv: AucRow[]; limits: string[]; drift_note: string; test_n: number; n_trials: number;
  test_positives: Record<string, number>;
  band_rates: Record<string, Record<string, number>>;
  band_table: { label: string; band: string; trials: number; observed_rate: number; share_of_positives: number }[];
  calibration: { label: string; model: string; mean_predicted: number; observed: number }[];
  drift: { year: number; trials: number; terminated_pct: number; low_accrual_pct: number; covid_cited_pct: number }[];
}
export interface Example { nct_id: string; kind: "hit" | "miss" | "new"; title: string; blurb: string; tag: string }
export type DesignInput = Record<string, unknown>;

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try { r = await fetch(url, init); }
  catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("server_down", "Can't reach the TrialRadar server. Is it running (make run)?", 0);
  }
  if (!r.ok) {
    let body: any = null;
    try { body = await r.json(); } catch { /* not json */ }
    if (body?.error) throw new ApiError(body.error.code, body.error.message, r.status);
    if (r.status === 422 && body?.detail) {
      const first = Array.isArray(body.detail) ? body.detail[0] : null;
      const msg = first?.msg ? String(first.msg).replace(/^Value error, /, "") : "Some inputs are not valid.";
      throw new ApiError("invalid", msg, 422);
    }
    throw new ApiError("server_error", "The server hit an unexpected problem. Please try again.", r.status);
  }
  return r.json();
}

export const analyze = (body: { nct_id?: string; design?: DesignInput }, signal?: AbortSignal) =>
  j<Analysis>("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
export const getDashboard = () => j<Dashboard>("/api/dashboard");
export const getReliability = () => j<Reliability>("/api/reliability");
export const getExamples = () => j<Example[]>("/api/examples");
