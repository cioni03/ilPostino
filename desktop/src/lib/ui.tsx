import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { save } from "@tauri-apps/plugin-dialog";
import type { CampaignStatus } from "./api";
import { api, errorText } from "./api";

// ---------------------------------------------------------------- contesto app

export type Page = "overview" | "campaigns" | "new" | "recipients" | "templates" | "smtp" | "settings";

interface Ctx {
  go: (page: Page, arg?: number) => void;
  arg: number | null;
  tick: number; // aumenta a ogni evento dal worker
  toast: (message: string, error?: boolean) => void;
  ask: (title: string, message: string, confirm?: string, danger?: boolean) => Promise<boolean>;
}
export const AppContext = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(AppContext);

/** Esegue un'azione mostrando l'errore come avviso invece di lasciarlo non gestito. */
export function useAction() {
  const { toast } = useApp();
  return useCallback(
    async <T,>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> => {
      try {
        const r = await fn();
        if (ok) toast(ok);
        return r;
      } catch (e) {
        toast(errorText(e), true);
        return undefined;
      }
    },
    [toast],
  );
}

/** Carica dati dal backend e li ricarica quando cambia una dipendenza (o, se richiesto, a ogni evento del worker). */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[], live = false) {
  const { tick, toast } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [version, setVersion] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let alive = true;
    fnRef.current().then(
      (d) => alive && setData(d),
      (e) => alive && toast(errorText(e), true),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version, live ? tick : 0]);
  return { data, reload: () => setVersion((v) => v + 1) };
}

// ---------------------------------------------------------------- elementi

export const CAMPAIGN_LABELS: Record<CampaignStatus, [string, string]> = {
  running: ["In corso", "b-run"],
  paused: ["In pausa", "b-warn"],
  scheduled: ["Programmata", "b-sched"],
  completed: ["Completata", "b-ok"],
  cancelled: ["Annullata", "b-mute"],
};

export const ITEM_LABELS: Record<string, [string, string]> = {
  pending: ["In coda", "b-mute"],
  processing: ["Invio…", "b-run"],
  sent: ["Inviata", "b-ok"],
  failed_temp: ["Fallita", "b-bad"],
  failed_perm: ["Fallita", "b-bad"],
  cancelled: ["Annullata", "b-mute"],
};

export function Badge({ cls, children }: { cls: string; children: ReactNode }) {
  return <span className={`badge ${cls}`}>{children}</span>;
}

export function CampaignBadge({ status }: { status: CampaignStatus }) {
  const [label, cls] = CAMPAIGN_LABELS[status] ?? [status, "b-mute"];
  return <Badge cls={cls}>{label}</Badge>;
}

export function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <button type="button" role="switch" aria-checked={on} aria-label={label} className={`sw ${on ? "on" : ""}`} onClick={() => onChange(!on)} />;
}

export function Seg<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="group">
      {options.map(([v, label]) => (
        <button key={v} type="button" className={v === value ? "on" : ""} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

export function Stepper({ value, onChange, min = 0, step = 1, label }: { value: number; onChange: (n: number) => void; min?: number; step?: number; label: string }) {
  return (
    <div className="stepper">
      <button type="button" aria-label={`Diminuisci ${label}`} onClick={() => onChange(Math.max(min, value - step))}>−</button>
      <input aria-label={label} inputMode="numeric" value={value} onChange={(e) => onChange(Math.max(min, parseInt(e.target.value.replace(/\D/g, "") || "0", 10)))} />
      <button type="button" aria-label={`Aumenta ${label}`} onClick={() => onChange(value + step)}>+</button>
    </div>
  );
}

export function Field({ label, htmlFor, children, hint }: { label: string; htmlFor?: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label className="lab" htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function Empty({ title, text, children }: { title: string; text?: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="b ink2" style={{ fontSize: 15 }}>{title}</div>
      {text && <div className="sm">{text}</div>}
      {children}
    </div>
  );
}

export function Modal({ title, onClose, width = 560, children }: { title: string; onClose: () => void; width?: number; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-label={title} style={{ width }}>
        <div className="row" style={{ padding: "18px 22px 12px" }}>
          <h2 className="h2" style={{ fontSize: 17 }}>{title}</h2>
          <button className="btn ghost i sp" aria-label="Chiudi" onClick={onClose}><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function useDialogs() {
  const [toasts, setToasts] = useState<{ id: number; text: string; err: boolean }[]>([]);
  const [confirmState, setConfirmState] = useState<null | { title: string; message: string; confirm: string; danger: boolean; resolve: (v: boolean) => void }>(null);
  const nextId = useRef(1);

  const toast = useCallback((text: string, err = false) => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, text, err }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), err ? 7000 : 3500);
  }, []);

  const ask = useCallback(
    (title: string, message: string, confirm = "Conferma", danger = false) =>
      new Promise<boolean>((resolve) => setConfirmState({ title, message, confirm, danger, resolve })),
    [],
  );

  const layer = (
    <>
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.err ? "err" : ""}`}>{t.text}</div>)}
      </div>
      {confirmState && (
        <Modal title={confirmState.title} width={440} onClose={() => { confirmState.resolve(false); setConfirmState(null); }}>
          <div style={{ padding: "0 22px 20px" }} className="col">
            <p className="ink2">{confirmState.message}</p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => { confirmState.resolve(false); setConfirmState(null); }}>Annulla</button>
              <button autoFocus className={`btn ${confirmState.danger ? "dng" : "pri"}`} onClick={() => { confirmState.resolve(true); setConfirmState(null); }}>{confirmState.confirm}</button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
  return { toast, ask, layer };
}

// ---------------------------------------------------------------- formati

export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null;
  const d = new Date(s.replace(" ", "T"));
  return isNaN(d.getTime()) ? null : d;
}

export function fmtDate(s: string | null | undefined): string {
  const d = parseDate(s);
  return d ? d.toLocaleString("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";
}

export function fmtTime(s: string | null | undefined): string {
  const d = parseDate(s);
  return d ? d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
}

export function fmtDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${String(m % 60).padStart(2, "0")} m`;
}

export const n = (x: number) => x.toLocaleString("it-IT");

/** Chiede dove salvare un CSV e lo scrive (con BOM, per aprirlo bene in Excel). */
export async function saveCsv(defaultName: string, contents: string): Promise<boolean> {
  const path = await save({ defaultPath: defaultName, filters: [{ name: "CSV", extensions: ["csv"] }] });
  if (!path) return false;
  await api.writeTextFile(path, "﻿" + contents);
  return true;
}
