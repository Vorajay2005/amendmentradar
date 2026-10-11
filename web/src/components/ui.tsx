import { animate, useMotionValue, useReducedMotion } from "framer-motion";
import { AlertTriangle, ChevronDown, Info, SearchX, WifiOff } from "lucide-react";
import { ReactNode, useEffect, useId, useRef, useState } from "react";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={cx("skeleton", className)} />;
}

export function CountUp({ value, decimals = 1, suffix = "%", scale = 100 }: { value: number; decimals?: number; suffix?: string; scale?: number }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(reduce ? value * scale : 0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const render = (v: number) => { if (ref.current) ref.current.textContent = v.toFixed(decimals) + suffix; };
    if (reduce) { render(value * scale); return; }
    const c = animate(mv, value * scale, { duration: 0.9, ease: [0.16, 1, 0.3, 1], onUpdate: render });
    return () => c.stop();
  }, [value, decimals, suffix, scale, reduce, mv]);
  return <span ref={ref} className="num">{(value * scale).toFixed(decimals) + suffix}</span>;
}

/** Accessible tooltip for jargon: focusable trigger, shown on hover/focus, described via aria-describedby. */
export function Help({ children, label = "More information" }: { children: ReactNode; label?: string }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle">
      <button type="button" aria-label={label} aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        className="ml-1 rounded-full p-0.5 text-muted hover:text-ink">
        <Info size={15} aria-hidden />
      </button>
      {open && (
        <span id={id} role="tooltip" className="absolute left-1/2 top-full z-30 mt-2 w-64 -translate-x-1/2 rounded-lg border border-line bg-surface p-3 text-xs font-normal leading-relaxed text-ink shadow-card">
          {children}
        </span>
      )}
    </span>
  );
}

export function Accordion({ title, children, defaultOpen = false }: { title: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className="rounded-xl border border-line bg-surface">
      <h3>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}
          className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left text-[15px] font-semibold min-h-[44px]">
          <span>{title}</span>
          <ChevronDown size={18} aria-hidden className={cx("shrink-0 text-muted transition-transform", open && "rotate-180")} />
        </button>
      </h3>
      {open && <div id={id} className="border-t border-line px-4 py-4 text-[15px] leading-relaxed text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ title, message, onRetry, kind = "error" }: { title: string; message: string; onRetry?: () => void; kind?: "error" | "offline" | "empty" }) {
  const Icon = kind === "offline" ? WifiOff : kind === "empty" ? SearchX : AlertTriangle;
  return (
    <div role="alert" className="card mx-auto max-w-xl p-8 text-center">
      <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full bg-surface2 text-high"><Icon size={24} aria-hidden /></div>
      <h2 className="display text-2xl font-semibold">{title}</h2>
      <p className="mt-2 text-muted">{message}</p>
      {onRetry && <button className="btn-primary mt-6" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function SectionTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-4">
      {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
      <h2 className="display text-2xl font-semibold sm:text-[1.75rem]">{title}</h2>
      {children && <p className="mt-1.5 max-w-3xl text-[15px] leading-relaxed text-muted">{children}</p>}
    </div>
  );
}

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <aside aria-label="Important limits" className="rounded-xl border border-mid/40 bg-mid/10 px-4 py-3 text-[13px] leading-relaxed text-ink">
      <strong className="font-semibold">Please read. </strong>
      Data are a <strong>current-record snapshot</strong> of ClinicalTrials.gov (records may have been edited after registration).
      Reasons for stopping are <strong>keyword-derived labels</strong>, not human review.
      TrialRadar <strong>assists trial designers</strong>; it is <strong>not an approval tool</strong>.
      {!compact && " It describes patterns in past trials and never says that changing a design will change its outcome."}
    </aside>
  );
}
