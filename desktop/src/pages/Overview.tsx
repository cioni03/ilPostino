import { ArrowRight, Pause, Play, Plus } from "lucide-react";
import { api } from "../lib/api";
import { CampaignBadge, Empty, fmtDate, n, useAction, useApp, useLoad } from "../lib/ui";

export default function Overview() {
  const { go } = useApp();
  const run = useAction();
  const campaigns = useLoad(api.campaignsList, [], true);
  const info = useLoad(api.dbInfo, []);
  const list = campaigns.data ?? [];
  const current = list.find((c) => c.status === "running");
  const paused = list.filter((c) => c.status === "paused");
  const pct = current ? Math.round(((current.sent + current.failed) / Math.max(1, current.total_count)) * 100) : 0;
  const noBackup = info.data !== null && !info.data.last_backup;

  const toggle = async (id: number, resume: boolean) => {
    await run(() => (resume ? api.campaignResume(id) : api.campaignPause(id)));
    campaigns.reload();
  };

  return (
    <main className="main">
      <div className="ph">
        <div>
          <h1 className="h1">Panoramica</h1>
          <p>{current ? "Un invio in corso" : "Nessun invio in corso"}</p>
        </div>
        <button className="btn pri lg sp" onClick={() => go("new")}><Plus size={16} />Nuovo invio</button>
      </div>

      {current ? (
        <section className="card pad col" style={{ gap: 16 }} aria-label="Invio in corso">
          <div className="row">
            <div className="grow">
              <div className="row" style={{ gap: 10 }}><h2 className="h2">{current.name}</h2><CampaignBadge status={current.status} /></div>
              <div className="muted sm" style={{ marginTop: 2 }}>{current.group_name} · via {current.smtp_name}</div>
            </div>
            <button className="btn" onClick={() => toggle(current.id, false)}><Pause size={14} />Pausa</button>
            <button className="btn ghost" onClick={() => go("campaigns", current.id)}>Dettagli<ArrowRight size={14} /></button>
          </div>
          <div className="row" style={{ gap: 40, alignItems: "flex-end" }}>
            <div className="stat"><span className="v">{n(current.sent)}<span className="muted" style={{ fontSize: 14, fontWeight: 500 }}> / {n(current.total_count)}</span></span><span className="l">inviate</span></div>
            <div className="stat"><span className={`v ${current.failed ? "badc" : ""}`}>{n(current.failed)}</span><span className="l">errori</span></div>
            <div className="stat"><span className="v">{n(current.pending)}</span><span className="l">ancora da inviare</span></div>
          </div>
          <div className="bar"><i style={{ width: `${pct}%` }} /></div>
        </section>
      ) : (
        <section className="card"><Empty title="Nessun invio in corso" text="Quando avvii una campagna la vedi qui, con l'avanzamento in tempo reale."><button className="btn pri" onClick={() => go("new")}>Crea il primo invio</button></Empty></section>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)", gap: 14, alignItems: "start", paddingBottom: 24 }}>
        <section className="card" style={{ overflow: "hidden" }}>
          <div className="row pad-s" style={{ paddingBottom: 12 }}><h2 className="h2">Ultime campagne</h2><button className="btn ghost s sp" onClick={() => go("campaigns")}>Vedi tutte<ArrowRight size={14} /></button></div>
          {list.length === 0 ? <div className="pad-s muted">Ancora nessuna campagna.</div> : (
            <table className="tbl">
              <colgroup><col style={{ width: "40%" }} /><col style={{ width: "22%" }} /><col style={{ width: "20%" }} /><col /></colgroup>
              <thead><tr><th>Campagna</th><th>Stato</th><th>Inviate</th><th>Data</th></tr></thead>
              <tbody>
                {list.slice(0, 4).map((c) => (
                  <tr key={c.id} className="click" onClick={() => go("campaigns", c.id)}>
                    <td className="p">{c.name}</td><td><CampaignBadge status={c.status} /></td>
                    <td className="mono">{n(c.sent)}/{n(c.total_count)}</td><td>{fmtDate(c.started_at ?? c.scheduled_at ?? c.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card pad-s col">
          <h2 className="h2">Richiede attenzione</h2>
          {paused.map((c) => (
            <div key={c.id} className="row" style={{ alignItems: "flex-start" }}>
              <div className="grow"><div className="b sm">«{c.name}» è in pausa</div><div className="muted xs">{c.auto_pause_reason ?? "Messa in pausa"}</div></div>
              <button className="btn s" onClick={() => toggle(c.id, true)}><Play size={13} />Riprendi</button>
            </div>
          ))}
          {noBackup && (
            <div className="row" style={{ alignItems: "flex-start" }}>
              <div className="grow"><div className="b sm">Nessun backup</div><div className="muted xs">I dati sono in un solo file</div></div>
              <button className="btn s" onClick={() => go("settings")}>Salva copia</button>
            </div>
          )}
          {paused.length === 0 && !noBackup && <div className="muted sm">Tutto a posto.</div>}
        </section>
      </div>
    </main>
  );
}
