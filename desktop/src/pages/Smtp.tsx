import { useState } from "react";
import { CheckCircle2, Loader2, Pencil, Plus, RefreshCw, Trash2, X, XCircle } from "lucide-react";
import { api, Diagnosis, SmtpServer } from "../lib/api";
import { Badge, Empty, Field, Modal, Stepper, Switch, useAction, useApp, useLoad } from "../lib/ui";

const SECURITY: Record<string, string> = { tls: "STARTTLS (porta 587)", ssl: "SSL/TLS (porta 465)", none: "Nessuna cifratura (porta 25)" };
const SECURITY_BADGE: Record<string, [string, string]> = { tls: ["STARTTLS", "b-ok"], ssl: ["SSL/TLS", "b-run"], none: ["Non cifrato", "b-warn"] };
const DEFAULT_PORT: Record<string, number> = { tls: 587, ssl: 465, none: 25 };

export default function Smtp() {
  const { ask } = useApp();
  const run = useAction();
  const list = useLoad(api.smtpList, []);
  const [editing, setEditing] = useState<SmtpServer | "new" | null>(null);
  const [diag, setDiag] = useState<{ server: SmtpServer; result: Diagnosis | null } | null>(null);
  const servers = list.data ?? [];

  const diagnose = async (server: SmtpServer) => {
    setDiag({ server, result: null });
    const result = await run(() => api.smtpDiagnose(server.id));
    setDiag((d) => (d && d.server.id === server.id ? { server, result: result ?? { ok: false, summary: "Test non riuscito.", steps: [] } } : d));
  };

  return (
    <main className="main flush">
      <section style={{ flex: 1, minWidth: 0, padding: "22px 28px 0", display: "flex", flexDirection: "column", gap: 16, overflow: "auto" }}>
        <div className="ph">
          <div><h1 className="h1">Server SMTP</h1><p>Le caselle da cui spedisci. Le password sono custodite dal sistema operativo.</p></div>
          <button className="btn pri sp" onClick={() => setEditing("new")}><Plus size={15} />Nuovo server</button>
        </div>

        {list.data !== null && servers.length === 0 ? (
          <div className="card"><Empty title="Nessun server SMTP" text="Aggiungi le credenziali della tua casella di posta (Gmail, Outlook, Brevo, un server aziendale…)."><button className="btn pri" onClick={() => setEditing("new")}>Aggiungi il primo server</button></Empty></div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 14, alignItems: "start", paddingBottom: 24 }}>
            {servers.map((s) => {
              const [label, cls] = SECURITY_BADGE[s.security] ?? [s.security, "b-mute"];
              return (
                <article key={s.id} className="card pad col" style={{ gap: 12, background: s.active ? undefined : "var(--surface-2)", borderColor: diag?.server.id === s.id ? "var(--accent)" : undefined }}>
                  <div className="row">
                    <div className="grow"><div className="b">{s.name}</div><div className="mono xs muted">{s.host}:{s.port}</div></div>
                    <Switch on={s.active} label={`${s.name} attivo`} onChange={async (v) => { await run(() => api.smtpSetActive(s.id, v)); list.reload(); }} />
                  </div>
                  <div className="row wrap" style={{ gap: 6 }}>
                    <Badge cls={cls}>{label}</Badge>
                    {!s.active && <Badge cls="b-mute">Disattivato</Badge>}
                    {s.username && !s.has_password && <Badge cls="b-bad">Password mancante</Badge>}
                  </div>
                  <div className="sm ink2">{s.sender_name ? `${s.sender_name} <${s.sender_email}>` : s.sender_email}</div>
                  <hr className="hr" />
                  <div className="row" style={{ gap: 2 }}>
                    <button className="btn ghost s" onClick={() => diagnose(s)}>Diagnostica</button>
                    <button className="btn ghost s i sp" aria-label={`Modifica ${s.name}`} onClick={() => setEditing(s)}><Pencil size={13} /></button>
                    <button className="btn ghost s i" aria-label={`Elimina ${s.name}`} onClick={async () => {
                      if (await ask("Eliminare il server SMTP?", `«${s.name}» verrà rimosso. Gli invii già fatti non cambiano.`, "Elimina", true)) { await run(() => api.smtpDelete(s.id), "Server eliminato"); list.reload(); }
                    }}><Trash2 size={13} /></button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {diag && (
        <aside className="drawer" aria-label={`Diagnostica ${diag.server.name}`}>
          <div className="row" style={{ padding: "18px 20px 12px" }}>
            <div><div className="h2">Diagnostica · {diag.server.name}</div><div className="mono xs muted" style={{ marginTop: 2 }}>{diag.server.host}:{diag.server.port}</div></div>
            <button className="btn ghost i sp" aria-label="Chiudi" onClick={() => setDiag(null)}><X size={16} /></button>
          </div>
          {diag.result === null ? (
            <div className="row" style={{ padding: "24px 20px", gap: 10 }}><Loader2 size={18} className="spin" />Verifica in corso…</div>
          ) : (
            <>
              <div style={{ padding: "0 20px" }}><div className={`alert ${diag.result.ok ? "ok" : "bad"}`} role="status"><div><b>{diag.result.summary}</b></div></div></div>
              <div className="col" style={{ gap: 10, padding: "14px 20px" }}>
                {diag.result.steps.map((st) => (
                  <div key={st.name} className="row" style={{ alignItems: "flex-start", gap: 10 }}>
                    {st.ok ? <CheckCircle2 size={16} className="okc" style={{ marginTop: 2 }} /> : <XCircle size={16} className="badc" style={{ marginTop: 2 }} />}
                    <div className="grow">
                      <div className="row"><span className={`b sm ${st.ok ? "" : "badc"}`}>{st.name}</span>{st.ms > 0 && <span className="mono xs muted sp">{st.ms} ms</span>}</div>
                      <div className={`mono xs ${st.ok ? "muted" : "badc"}`} style={{ wordBreak: "break-word" }}>{st.detail}</div>
                      {st.hint && <div className="xs warnc" style={{ marginTop: 6, background: "var(--warn-soft)", padding: "8px 10px", borderRadius: 8 }}>{st.hint}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="row" style={{ padding: "14px 20px", marginTop: "auto", borderTop: "1px solid var(--line)" }}>
            <button className="btn" onClick={() => diagnose(diag.server)}><RefreshCw size={14} />Riesegui</button>
            <button className="btn pri sp" onClick={() => setEditing(diag.server)}>Modifica</button>
          </div>
        </aside>
      )}

      {editing && <ServerModal server={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload(); }} />}
    </main>
  );
}

function ServerModal({ server, onClose, onSaved }: { server: SmtpServer | null; onClose: () => void; onSaved: () => void }) {
  const run = useAction();
  const [f, setF] = useState({
    name: server?.name ?? "", host: server?.host ?? "", port: server?.port ?? 587, security: (server?.security ?? "tls") as string,
    username: server?.username ?? "", password: "", sender_email: server?.sender_email ?? "", sender_name: server?.sender_name ?? "",
    reply_to: server?.reply_to ?? "", rate_limit: server?.rate_limit ?? 0, active: server?.active ?? true,
  });
  const [more, setMore] = useState(Boolean(server?.reply_to || server?.rate_limit));
  const text = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });

  const submit = async () => {
    const id = await run(() => api.smtpSave({
      id: server?.id ?? null, name: f.name, host: f.host, port: f.port, security: f.security,
      username: f.username || null, password: f.password || null, sender_email: f.sender_email,
      sender_name: f.sender_name || null, reply_to: f.reply_to || null, rate_limit: f.rate_limit || null, active: f.active,
    }), "Server salvato");
    if (id !== undefined) onSaved();
  };

  return (
    <Modal title={server ? "Modifica server SMTP" : "Nuovo server SMTP"} width={580} onClose={onClose}>
      <form style={{ padding: "0 22px 20px" }} className="col" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Nome" htmlFor="s-name"><input id="s-name" autoFocus className="inp" value={f.name} onChange={text("name")} placeholder="Es. Brevo" /></Field>
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow"><Field label="Host" htmlFor="s-host"><input id="s-host" className="inp" value={f.host} onChange={text("host")} placeholder="smtp.esempio.it" /></Field></div>
          <div style={{ width: 130 }}><Field label="Porta"><Stepper label="Porta" value={f.port} min={1} onChange={(v) => setF({ ...f, port: v })} /></Field></div>
        </div>
        <Field label="Sicurezza" htmlFor="s-sec">
          <select id="s-sec" className="inp" value={f.security} onChange={(e) => setF({ ...f, security: e.target.value, port: Object.values(DEFAULT_PORT).includes(f.port) ? DEFAULT_PORT[e.target.value] : f.port })}>
            {Object.entries(SECURITY).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow"><Field label="Utente" htmlFor="s-user"><input id="s-user" className="inp" value={f.username} onChange={text("username")} autoComplete="off" /></Field></div>
          <div className="grow"><Field label="Password" htmlFor="s-pass" hint={server?.has_password ? "Lascia vuoto per non cambiarla" : undefined}><input id="s-pass" className="inp" type="password" value={f.password} onChange={text("password")} autoComplete="new-password" /></Field></div>
        </div>
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow"><Field label="Email mittente" htmlFor="s-from"><input id="s-from" className="inp" value={f.sender_email} onChange={text("sender_email")} /></Field></div>
          <div className="grow"><Field label="Nome mittente (facoltativo)" htmlFor="s-fname"><input id="s-fname" className="inp" value={f.sender_name} onChange={text("sender_name")} /></Field></div>
        </div>
        {more ? (
          <div className="row" style={{ alignItems: "flex-start" }}>
            <div className="grow"><Field label="Rispondi a (facoltativo)" htmlFor="s-reply"><input id="s-reply" className="inp" value={f.reply_to} onChange={text("reply_to")} /></Field></div>
            <div style={{ width: 200 }}><Field label="Limite email all'ora" hint="0 = nessun limite"><Stepper label="Limite email all'ora" value={f.rate_limit} step={50} onChange={(v) => setF({ ...f, rate_limit: v })} /></Field></div>
          </div>
        ) : <button type="button" className="btn ghost s" style={{ alignSelf: "flex-start" }} onClick={() => setMore(true)}>Altre opzioni</button>}
        <div className="row"><Switch on={f.active} label="Server attivo" onChange={(v) => setF({ ...f, active: v })} /><span className="sm">Attivo per l'invio</span></div>
        <div className="row" style={{ justifyContent: "flex-end" }}><button type="button" className="btn" onClick={onClose}>Annulla</button><button className="btn pri" type="submit">Salva</button></div>
      </form>
    </Modal>
  );
}
