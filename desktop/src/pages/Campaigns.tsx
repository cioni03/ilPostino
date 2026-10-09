import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Download, Pause, Play, Plus, Trash2 } from "lucide-react";
import { api, Campaign } from "../lib/api";
import { Badge, CampaignBadge, Empty, fmtDate, fmtTime, ITEM_LABELS, n, saveCsv, Seg, useAction, useApp, useLoad } from "../lib/ui";

const PER_PAGE = 25;

export default function Campaigns() {
  const { go, arg, ask } = useApp();
  const run = useAction();
  const list = useLoad(api.campaignsList, [], true);
  const campaigns = list.data ?? [];
  const [selected, setSelected] = useState<number | null>(arg);

  useEffect(() => {
    if (selected === null && campaigns.length) setSelected(campaigns[0].id);
  }, [campaigns, selected]);

  const current = campaigns.find((c) => c.id === selected) ?? null;

  const act = async (fn: () => Promise<void>, ok?: string) => { await run(fn, ok); list.reload(); };

  return (
    <main className="main flush">
      <section style={{ width: 320, flex: "none", background: "var(--surface)", borderRight: "1px solid var(--line)", display: "flex", flexDirection: "column", overflow: "hidden" }} aria-label="Elenco campagne">
        <div className="row" style={{ padding: "20px 18px 14px" }}>
          <h1 className="h2" style={{ fontSize: 17 }}>Campagne</h1>
          <button className="btn pri s sp" onClick={() => go("new")}><Plus size={14} />Nuova</button>
        </div>
        <hr className="hr" />
        <div style={{ overflow: "auto" }}>
          {campaigns.map((c) => (
            <button key={c.id} onClick={() => setSelected(c.id)} className="col" style={{ gap: 5, padding: "14px 18px", width: "100%", textAlign: "left", border: 0, borderBottom: "1px solid var(--line)", background: c.id === selected ? "var(--accent-soft)" : "transparent" }}>
              <div className="row" style={{ gap: 8, width: "100%" }}><span className="b grow" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</span><CampaignBadge status={c.status} /></div>
              <div className="muted xs">{c.group_name} · {c.status === "scheduled" ? fmtDate(c.scheduled_at) : `${n(c.sent)} su ${n(c.total_count)}`}</div>
            </button>
          ))}
          {campaigns.length === 0 && <Empty title="Nessuna campagna" text="Crea il tuo primo invio." />}
        </div>
      </section>

      {current ? <Detail key={current.id} c={current} act={act} onDelete={async () => {
        if (await ask("Eliminare la campagna?", `«${current.name}» e il suo storico verranno eliminati.`, "Elimina", true)) {
          await act(() => api.campaignDelete(current.id), "Campagna eliminata");
          setSelected(null);
        }
      }} /> : <div className="grow"><Empty title="Seleziona una campagna" /></div>}
    </main>
  );
}

function Detail({ c, act, onDelete }: { c: Campaign; act: (fn: () => Promise<void>, ok?: string) => Promise<void>; onDelete: () => void }) {
  const { ask } = useApp();
  const run = useAction();
  const [tab, setTab] = useState<"items" | "log">("items");
  const [page, setPage] = useState(1);
  const items = useLoad(() => api.campaignItems({ campaign_id: c.id, status: null, page, per_page: PER_PAGE }), [c.id, page], true);
  const logs = useLoad(() => api.campaignLogs(c.id), [c.id], true);
  const pct = Math.round(((c.sent + c.failed) / Math.max(1, c.total_count)) * 100);
  const pages = Math.max(1, Math.ceil((items.data?.total ?? 0) / PER_PAGE));
  const live = c.status === "running" || c.status === "paused" || c.status === "scheduled";

  return (
    <section style={{ flex: 1, minWidth: 0, padding: "22px 28px 0", display: "flex", flexDirection: "column", gap: 16, overflow: "auto" }}>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div className="grow">
          <div className="row" style={{ gap: 10 }}><h2 className="h1">{c.name}</h2><CampaignBadge status={c.status} /></div>
          <p className="muted sm" style={{ marginTop: 3 }}>
            {c.group_name} · via {c.smtp_name}
            {c.status === "scheduled" ? ` · parte ${fmtDate(c.scheduled_at)}` : c.started_at ? ` · avviata ${fmtDate(c.started_at)}` : ""}
          </p>
        </div>
        {c.status === "running" && <button className="btn" onClick={() => act(() => api.campaignPause(c.id))}><Pause size={14} />Pausa</button>}
        {c.status === "paused" && <button className="btn pri" onClick={() => act(() => api.campaignResume(c.id))}><Play size={14} />Riprendi</button>}
        {live && <button className="btn dng" onClick={async () => { if (await ask("Interrompere l'invio?", `Le ${n(c.pending)} email ancora da inviare verranno annullate.`, "Interrompi", true)) act(() => api.campaignCancel(c.id)); }}>Interrompi</button>}
        {!live && <button className="btn ghost i" aria-label="Elimina campagna" onClick={onDelete}><Trash2 size={15} /></button>}
      </div>

      {c.status === "paused" && c.auto_pause_reason && <div className="alert warn" role="status"><div><b>In pausa.</b> {c.auto_pause_reason}</div></div>}

      <div className="card pad col" style={{ gap: 14 }}>
        <div className="row" style={{ gap: 40, alignItems: "flex-end" }}>
          <div className="stat"><span className="v">{n(c.sent)}<span className="muted" style={{ fontSize: 14, fontWeight: 500 }}> / {n(c.total_count)}</span></span><span className="l">inviate</span></div>
          <div className="stat"><span className={`v ${c.failed ? "badc" : ""}`}>{n(c.failed)}</span><span className="l">errori</span></div>
          <div className="stat"><span className="v">{n(c.pending)}</span><span className="l">ancora da inviare</span></div>
        </div>
        <div className={`bar ${c.status === "completed" ? "ok" : ""}`}><i style={{ width: `${pct}%` }} /></div>
      </div>

      <div className="card" style={{ overflow: "hidden", flex: "none" }}>
        <div className="row" style={{ padding: "10px 14px" }}>
          <Seg value={tab} onChange={setTab} options={[["items", "Destinatari"], ["log", "Cronologia"]]} />
          <button className="btn s sp" onClick={async () => { const csv = await run(() => api.campaignExportCsv(c.id)); if (csv) await run(() => saveCsv(`invio_${c.id}.csv`, csv), "File salvato"); }}><Download size={13} />Esporta</button>
        </div>
        {tab === "items" ? (
          <>
            <table className="tbl">
              <colgroup><col style={{ width: "38%" }} /><col style={{ width: "18%" }} /><col /></colgroup>
              <thead><tr><th>Email</th><th>Esito</th><th>Dettaglio</th></tr></thead>
              <tbody>
                {(items.data?.rows ?? []).map((r) => {
                  const [label, cls] = ITEM_LABELS[r.status] ?? [r.status, "b-mute"];
                  return (
                    <tr key={r.email}>
                      <td className="p">{r.email}</td><td><Badge cls={cls}>{label}</Badge></td>
                      <td className={r.last_error ? "badc" : ""} title={r.last_error}>{r.last_error || (r.sent_at ? fmtTime(r.sent_at) : "—")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="row" style={{ padding: "0 14px", height: 44, borderTop: "1px solid var(--line)", background: "var(--surface-2)" }}>
              <span className="muted sm">{n(items.data?.total ?? 0)} destinatari · pagina {page} di {pages}</span>
              <div className="row sp" style={{ gap: 6 }}>
                <button className="btn s i" aria-label="Pagina precedente" disabled={page <= 1} onClick={() => setPage(page - 1)}><ArrowLeft size={14} /></button>
                <button className="btn s i" aria-label="Pagina successiva" disabled={page >= pages} onClick={() => setPage(page + 1)}><ArrowRight size={14} /></button>
              </div>
            </div>
          </>
        ) : (
          <div className="log" style={{ borderRadius: 0, maxHeight: 380 }} role="log">
            {(logs.data ?? []).map((l) => (
              <div key={l.id}><span className="t">{fmtTime(l.created_at)}</span><span className={`lv ${l.level}`}>{l.level.toUpperCase()}</span>{l.message}</div>
            ))}
          </div>
        )}
      </div>
      <div style={{ height: 8, flex: "none" }} />
    </section>
  );
}
