export const pct = (x: number, d = 1) => `${(x * 100).toFixed(d)}%`;
export const num = (x: number) => x.toLocaleString("en-US");
export const nctOk = (s: string) => /^NCT\d{8}$/i.test(s.trim());
export function aucWord(a: number) { return a < 0.55 ? "near chance" : a < 0.65 ? "weak" : a < 0.75 ? "modest" : "moderate"; }
export const bandKey = (b: string) => (b.startsWith("Lower") ? "low" : b.startsWith("Middle") ? "mid" : "high") as "low" | "mid" | "high";
export const statusText = (s: string | null) => (s ? s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : "");
