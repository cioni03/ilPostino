import { useEffect, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { html } from "@codemirror/lang-html";
import { EditorView } from "@codemirror/view";
import { Check, Plus, Trash2, Copy } from "lucide-react";
import { api, RenderOutput } from "../lib/api";
import { Empty, Field, Seg, useAction, useApp, useLoad } from "../lib/ui";

const VARIABLES = ["first_name", "last_name", "email", "company", "tags"];

const DEFAULT_HTML = `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; color: #1e293b;">
  <h2 style="color: #0B5FD1; margin-top: 0;">Ciao {{ first_name }}!</h2>
  <p style="font-size: 15px; line-height: 1.6; color: #475569;">
    Questa è la tua nuova email inviata con <strong>ilPostino</strong>.
  </p>
  <p style="font-size: 12px; color: #94a3b8;">
    Ricevi questa comunicazione perché fai parte della nostra rubrica.
  </p>
</div>`;

export default function Templates() {
  const { ask } = useApp();
  const run = useAction();
  const list = useLoad(api.templatesList, []);
  const templates = list.data ?? [];

  const [id, setId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [saved, setSaved] = useState({ name: "", subject: "", body: "" });
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [out, setOut] = useState<RenderOutput | null>(null);
  const view = useRef<EditorView | null>(null);

  const dirty = name !== saved.name || subject !== saved.subject || body !== saved.body;

  const load = (t: { id: number; name: string; subject: string; html_body: string } | null) => {
    setId(t?.id ?? null);
    setName(t?.name ?? "");
    setSubject(t?.subject ?? "");
    setBody(t?.html_body ?? "");
    setSaved({ name: t?.name ?? "", subject: t?.subject ?? "", body: t?.html_body ?? "" });
  };

  // al primo caricamento apre il primo template
  useEffect(() => {
    if (id === null && templates.length && !dirty) load(templates[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templates.length]);

  // anteprima in tempo reale (con piccola attesa mentre si scrive)
  useEffect(() => {
    const t = setTimeout(() => api.templateRender({ subject, html_body: body }).then(setOut, () => setOut(null)), 250);
    return () => clearTimeout(t);
  }, [subject, body]);

  const confirmDiscard = async () => !dirty || (await ask("Modifiche non salvate", "Se continui, le modifiche a questo template andranno perse.", "Scarta modifiche", true));

  const select = async (tid: number) => {
    if (tid === id || !(await confirmDiscard())) return;
    load(templates.find((t) => t.id === tid) ?? null);
  };

  const save = async () => {
    const newId = await run(() => api.templateSave({ id, name, subject, html_body: body }), "Template salvato");
    if (newId !== undefined) { setId(newId); setSaved({ name, subject, body }); list.reload(); }
  };

  const create = async () => {
    if (!(await confirmDiscard())) return;
    const newId = await run(() => api.templateSave({ name: "Nuovo template", subject: "Oggetto della newsletter", html_body: DEFAULT_HTML }));
    if (newId !== undefined) {
      list.reload();
      load({ id: newId, name: "Nuovo template", subject: "Oggetto della newsletter", html_body: DEFAULT_HTML });
    }
  };

  const insert = (v: string) => {
    const token = `{{ ${v} }}`;
    const ev = view.current;
    if (ev) { ev.dispatch(ev.state.replaceSelection(token)); ev.focus(); } else setBody(body + token);
  };

  if (list.data !== null && templates.length === 0 && id === null) {
    return <main className="main"><div className="card"><Empty title="Nessun template" text="Un template è l'email che invii: scrivila una volta e riusala."><button className="btn pri" onClick={create}><Plus size={15} />Crea il primo template</button></Empty></div></main>;
  }

  const doc = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;padding:8px}</style></head><body>${out?.html ?? ""}</body></html>`;

  return (
    <main className="main flush" style={{ flexDirection: "column" }}>
      <div className="row" style={{ padding: "12px 24px", background: "var(--surface)", borderBottom: "1px solid var(--line)", gap: 10, flex: "none" }}>
        <label className="lab" htmlFor="tpl" style={{ margin: 0 }}>Template</label>
        <select id="tpl" className="inp" style={{ width: 250 }} value={id ?? ""} onChange={(e) => select(Number(e.target.value))}>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <span className="chip sp">{dirty ? "Modifiche non salvate" : "Tutte le modifiche salvate"}</span>
        <button className="btn" onClick={create}><Plus size={14} />Nuovo</button>
        {id !== null && <button className="btn ghost i" aria-label="Duplica" title="Duplica" onClick={async () => { if (await confirmDiscard()) { const nid = await run(() => api.templateDuplicate(id), "Template duplicato"); if (nid !== undefined) { await list.reload(); const t = (await api.templatesList()).find((x) => x.id === nid); load(t ?? null); } } }}><Copy size={15} /></button>}
        {id !== null && <button className="btn ghost i dng" aria-label="Elimina template" onClick={async () => { if (await ask("Eliminare il template?", `«${name}» verrà eliminato. Gli invii già fatti non cambiano.`, "Elimina", true)) { await run(() => api.templateDelete(id)); load(null); list.reload(); } }}><Trash2 size={15} /></button>}
        <button className="btn pri" disabled={!dirty} onClick={save}><Check size={14} />Salva</button>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <section style={{ flex: 1, minWidth: 0, padding: "16px 24px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto" }} aria-label="Editor">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 14 }}>
            <Field label="Nome (solo per te)" htmlFor="t-name"><input id="t-name" className="inp" value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Oggetto dell'email" htmlFor="t-subj"><input id="t-subj" className="inp" value={subject} onChange={(e) => setSubject(e.target.value)} /></Field>
          </div>
          <div className="row wrap" style={{ gap: 6 }}>
            <span className="eyebrow" style={{ marginRight: 4 }}>Inserisci</span>
            {VARIABLES.map((v) => <button key={v} className="chip mono" onClick={() => insert(v)}>{`{{ ${v} }}`}</button>)}
          </div>
          <div style={{ flex: 1, minHeight: 280, borderRadius: 10, overflow: "hidden", border: "1px solid #1b2a44" }}>
            <CodeMirror value={body} height="100%" theme="dark" extensions={[html(), EditorView.lineWrapping]} onChange={setBody} onCreateEditor={(v) => { view.current = v; }}
              basicSetup={{ foldGutter: false }} style={{ height: "100%" }} />
          </div>
          {out?.error && <div className="alert bad" role="alert"><div><b>Errore nel template.</b> {out.error}</div></div>}
          {!out?.error && out && out.unknown.length > 0 && <div className="alert warn" role="status"><div><b>Variabile non prevista:</b> <span className="mono xs">{out.unknown.join(", ")}</span>: non esiste nei destinatari e farebbe fallire l'invio.</div></div>}
        </section>

        <aside style={{ width: 470, flex: "none", background: "var(--surface-2)", borderLeft: "1px solid var(--line)", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto" }} aria-label="Anteprima">
          <div className="row"><span className="b">Anteprima</span><div className="sp"><Seg value={device} onChange={setDevice} options={[["desktop", "Desktop"], ["mobile", "Mobile"]]} /></div></div>
          <div className="mailframe" style={{ maxWidth: device === "mobile" ? 375 : undefined, margin: device === "mobile" ? "0 auto" : undefined, width: "100%" }}>
            <div className="mailhead">{out?.subject || "(nessun oggetto)"}</div>
            <iframe title="Anteprima email" sandbox="" srcDoc={doc} style={{ height: 460 }} />
          </div>
          <div className="muted xs">Mostra i dati di un destinatario di esempio.</div>
        </aside>
      </div>
    </main>
  );
}
