/* Minimal shadcn/ui-style primitives (hand-written, Tailwind-based, no runtime dependencies). */
import { forwardRef, useEffect, useRef, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes,
  type ReactNode, type SelectHTMLAttributes, type TdHTMLAttributes, type TextareaHTMLAttributes, type ThHTMLAttributes } from "react";
import { AlertTriangle, ChevronLeft, ChevronRight, Inbox, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n";

type Variant = "default" | "outline" | "ghost" | "destructive" | "secondary" | "link";
const VARIANTS: Record<Variant, string> = {
  default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm",
  outline: "border border-border bg-white hover:bg-muted",
  ghost: "hover:bg-muted",
  destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  secondary: "bg-muted text-foreground hover:bg-muted/70",
  link: "text-primary underline-offset-4 hover:underline px-0",
};
const SIZES = { sm: "h-8 px-3 text-xs", md: "h-9 px-4 text-sm", lg: "h-11 px-6 text-base", icon: "h-9 w-9" };

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant; size?: keyof typeof SIZES; loading?: boolean;
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", loading, disabled, children, type = "button", ...p }, ref) => (
    <button ref={ref} type={type} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:pointer-events-none disabled:opacity-50",
        VARIANTS[variant], SIZES[size], className)} {...p}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  ));
Button.displayName = "Button";

const field = "w-full rounded-md border border-border bg-white px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn(field, "h-9", className)} {...p} />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(field, "min-h-[80px] py-2", className)} {...p} />
));
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, ref) => (
  <select ref={ref} className={cn(field, "h-9 pr-8", className)} {...p}>{children}</select>
));
Select.displayName = "Select";

export function Label({ className, ...p }: HTMLAttributes<HTMLLabelElement> & { htmlFor?: string }) {
  return <label className={cn("text-xs font-medium text-muted-foreground", className)} {...p} />;
}

export function Field({ label, error, children, hint, htmlFor }: { label: string; error?: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
    </div>
  );
}

export function Switch({ checked, onChange, label, id }: { checked: boolean; onChange: (v: boolean) => void; label?: string; id?: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm" htmlFor={id}>
      <button id={id} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cn("relative h-5 w-9 rounded-full transition-colors", checked ? "bg-primary" : "bg-slate-300")}>
        <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </button>
      {label && <span>{label}</span>}
    </label>
  );
}

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-border bg-card shadow-sm", className)} {...p} />;
}
export function CardHeader({ title, description, action, className }: { title: ReactNode; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-2 border-b border-border px-5 py-4", className)}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function CardBody({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...p} />;
}

type Tone = "default" | "green" | "amber" | "red" | "blue" | "violet" | "slate";
const TONES: Record<Tone, string> = {
  default: "bg-muted text-foreground", green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200", red: "bg-red-50 text-red-700 ring-red-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200", violet: "bg-violet-50 text-violet-700 ring-violet-200",
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
};
export function Badge({ tone = "default", className, ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ring-transparent", TONES[tone], className)} {...p} />;
}

export function Table({ className, ...p }: HTMLAttributes<HTMLTableElement>) {
  return <div className="w-full overflow-x-auto"><table className={cn("w-full text-sm", className)} {...p} /></div>;
}
export function Th({ className, ...p }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("whitespace-nowrap border-b border-border bg-slate-50 px-3 py-2 text-left text-xs font-medium text-muted-foreground", className)} {...p} />;
}
export function Td({ className, ...p }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b border-border px-3 py-2 align-top", className)} {...p} />;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-muted-foreground", className)} aria-label="loading" />;
}

export function LoadingState({ label }: { label?: string }) {
  const { t } = useI18n();
  return <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground" role="status"><Spinner />{label ?? t("common.loading")}</div>;
}

export function EmptyState({ title, description, action }: { title?: string; description?: string; action?: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <Inbox className="h-8 w-8 text-slate-300" aria-hidden />
      <p className="text-sm font-medium">{title ?? t("common.empty")}</p>
      {description && <p className="max-w-md text-xs text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const msg = error instanceof Error ? error.message : String(error ?? "");
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center" role="alert">
      <AlertTriangle className="h-7 w-7 text-destructive" aria-hidden />
      <p className="text-sm font-medium">{t("common.error")}</p>
      {msg && <p className="max-w-lg text-xs text-muted-foreground">{msg}</p>}
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}>{t("common.retry")}</Button>}
    </div>
  );
}

export function Alert({ tone = "amber", children, className }: { tone?: "amber" | "blue" | "red" | "green"; children: ReactNode; className?: string }) {
  const tones = { amber: "border-amber-200 bg-amber-50 text-amber-900", blue: "border-sky-200 bg-sky-50 text-sky-900",
    red: "border-red-200 bg-red-50 text-red-900", green: "border-emerald-200 bg-emerald-50 text-emerald-900" };
  return <div className={cn("rounded-md border px-3 py-2 text-xs", tones[tone], className)}>{children}</div>;
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const { t } = useI18n();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between gap-2 px-1 py-3 text-xs text-muted-foreground">
      <span>{t("common.pageOf", { page, pages, total })}</span>
      <div className="flex gap-1">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t("common.prev")}><ChevronLeft className="h-4 w-4" /></Button>
        <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t("common.next")}><ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

export function Dialog({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/40 p-4" onMouseDown={onClose}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        className={cn("max-h-[90vh] w-full overflow-y-auto rounded-lg bg-white shadow-xl outline-none", wide ? "max-w-3xl" : "max-w-lg")}>
        <div className="border-b border-border px-5 py-3 text-sm font-semibold">{title}</div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, message, onConfirm, onCancel, destructive, loading }: {
  open: boolean; title: string; message: string; onConfirm: () => void; onCancel: () => void; destructive?: boolean; loading?: boolean }) {
  const { t } = useI18n();
  return (
    <Dialog open={open} onClose={onCancel} title={title}
      footer={<>
        <Button variant="outline" onClick={onCancel}>{t("common.cancel")}</Button>
        <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} loading={loading}>{t("common.confirm")}</Button>
      </>}>
      <p className="text-sm text-muted-foreground">{message}</p>
    </Dialog>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { value: T; label: string }[] }) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-lg bg-muted p-1" role="tablist">
      {items.map((i) => (
        <button key={i.value} role="tab" aria-selected={value === i.value} onClick={() => onChange(i.value)}
          className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors", value === i.value ? "bg-white shadow-sm" : "text-muted-foreground hover:text-foreground")}>
          {i.label}
        </button>
      ))}
    </div>
  );
}

export function Stat({ label, value, sub, icon }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">{label}{icon}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </Card>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
