import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, ChevronDown, ChevronRight, Send, X } from "lucide-react";
import { api, Group, SmtpServer, Template } from "../lib/api";
import { Empty, Field, fmtDuration, n, Stepper, useAction, useApp, useLoad } from "../lib/ui";

type Speed = "prudent" | "standard" | "fast" | "custom";
const PROFILES: Record<Exclude<Speed, "custom">, { label: string; hint: string; tranche: number; pause: number }> = {
  prudent: { label: "Prudente", hint: "Per Gmail o Outlook gratuiti", tranche: 25, pause: 120 },
  standard: { label: "Standard", hint: "Per i provider professionali", tranche: 50, pause: 60 },
  fast: { label: "Veloce", hint: "Per un server tuo, senza limiti", tranche: 100, pause: 30 },
};
const STEPS = ["Server", "Template", "Destinatari", "Velocità", "Conferma"];

function pad(x: number) { return String(x).padStart(2, "0"); }
function tomorrowAt9() {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  return { date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: "09:00" };
}

export default function NewCampaign() {
  const { go, toast } = useApp();
  const run = useAction();
  const servers = useLoad(api.smtpList, []).data?.filter((s) => s.active) ?? null;
  const templates = useLoad(api.templatesList, []).data;
  const groups = useLoad(api.groupsList, []).data;

  const [step, setStep] = useState(0);
  const [smtpId, setSmtpId] = useState<number | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [speed, setSpeed] = useState<Speed>("standard");
  const [tranche, setTranche] = useState(50);
  const [pause, setPause] = useState(60);
  const [retries, setRetries] = useState(3);
  const [delay, setDelay] = useState(30);
  const [advanced, setAdvanced] = useState(false);
  const [later, setLater] = useState(false);
  const [when, setWhen] = useState(tomorrowAt9());
  const [testTo, setTestTo] = useState("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const server: SmtpServer | undefined = servers?.find((s) => s.id === smtpId);
  const template: Template | undefined = templates?.find((t) => t.id === templateId);
  const group: Group | undefined = groups?.find((g) => g.id === groupId);
  const count = group?.total ?? 0;

  // preselezioni ragionevoli
  useEffect(() => { if (servers && smtpId === null && servers.length === 1) setSmtpId(servers[0].id); }, [servers, smtpId]);
  useEffect(() => { if (templates && templateId === null && templates.length === 1) setTemplateId(templates[0].id); }, [templates, templateId]);

  const pickSpeed = (s: Exclude<Speed, "custom">) => { setSpeed(s); setTranche(PROFILES[s].tranche); setPause(PROFILES[s].pause); };

  const rate = server?.rate_limit ?? null;
  const estimate = useMemo(() => {
    const tranches = Math.ceil(count / Math.max(1, tranche));
    const byPauses = Math.max(0, tranches - 1) * pause + count * 1.5;
    const byRate = rate ? (count / rate) * 3600 : 0;
    return { tranches, seconds: Math.max(byPauses, byRate), limited: byRate > byPauses };
  }, [count, tranche, pause, rate]);

  const rendered = useLoad(
    () => (template ? api.templateRender({ subject: template.subject, html_body: template.html_body, group_id: groupId }) : Promise.resolve(null)),
    [templateId, groupId],
  ).data;

  const scheduledAt = later ? `${when.date} ${when.time}:00` : null;
  const laterInvalid = later && new Date(`${when.date}T${when.time}:00`).getTime() <= Date.now();

  const canNext = [
    smtpId !== null,
    templateId !== null && !(rendered?.error),
    groupId !== null && count > 0,
    !laterInvalid,
    true,
  ][step];

  const sendTest = async () => {
    if (!server || !rendered) return;
    setTestResult(null);
    const ok = await run(() => api.smtpSendTest({ smtp_id: server.id, to: testTo, subject: rendered.subject, html: rendered.html }));
    if (ok !== undefined) setTestResult(`Prova recapitata a ${testTo}`);
  };

  const launch = async () => {
    if (!server || !template || !group) return;
    setBusy(true);
    const id = await run(() => api.campaignCreate({
      name: `${template.name} · ${group.name}`, smtp_server_id: server.id, template_id: template.id, template_name: template.name,
      subject: template.subject, html_body: template.html_body, group_id: group.id, tranche_size: tranche, pause_seconds: pause,
      max_retries: retries, retry_delay_seconds: delay, scheduled_at: scheduledAt,
    }));
    setBusy(false);
    if (id !== undefined) { toast(later ? "Invio programmato" : "Invio avviato"); go("campaigns", id); }
  };

  const summary = [
    server ? server.name : "", template ? template.name : "", group ? `${group.name} · ${n(count)}` : "",
    speed === "custom" ? `${tranche} email · pausa ${pause} s` : PROFILES[speed].label, "",
  ];

  const doc = `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;padding:8px}</style></head><body>${rendered?.html ?? ""}</body></html>`;

  return (
    <main className="main" style={{ padding: "22px 40px 24px" }}>
      <div className="row">
        <button className="btn ghost s" onClick={() => go("overview")}><X size={14} />Esci</button>
        <h1 className="h1">Nuovo invio</h1>
      </div>

      <div className="row" style={{ alignItems: "flex-start", gap: 28 }}>
        <nav className="rail" aria-label="Passi dell'invio">
          {STEPS.map((label, i) => (
            <div key={label} className={`rs ${i < step ? "done" : i === step ? "cur" : ""}`} onClick={() => i < step && setStep(i)}>
              <span className="c">{i < step ? <Check size={13} /> : i + 1}</span>
              <div><div className="t">{label}</div>{summary[i] && i < step + 0 && <div className="s">{summary[i]}</div>}</div>
            </div>
          ))}
        </nav>

        <section className="card grow col" style={{ padding: 28, gap: 22 }}>
          {step === 0 && (
            <>
              <div><h2 className="h1" style={{ fontSize: 20 }}>Da quale casella spedisci?</h2><p className="muted" style={{ marginTop: 3 }}>Scegli uno dei server SMTP attivi.</p></div>
              {servers && servers.length === 0 ? (
                <div className="alert warn"><AlertTriangle size={16} style={{ marginTop: 2 }} /><div className="grow"><b>Nessun server attivo.</b> Configura o attiva almeno un server SMTP.</div><button className="btn s" onClick={() => go("smtp")}>Vai ai server</button></div>
              ) : (
                <div className="col" style={{ gap: 8 }}>
                  {(servers ?? []).map((s) => (
                    <button key={s.id} className={`radio-card ${smtpId === s.id ? "on" : ""}`} onClick={() => setSmtpId(s.id)}>
                      <span className="rd" /><div className="grow"><div className="b">{s.name}</div><div className="muted xs">{s.sender_email} · {s.host}:{s.port}{s.rate_limit ? ` · max ${n(s.rate_limit)}/ora` : ""}</div></div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {step === 1 && (
            <>
              <div><h2 className="h1" style={{ fontSize: 20 }}>Quale email invii?</h2><p className="muted" style={{ marginTop: 3 }}>Scegli un template salvato.</p></div>
              {templates && templates.length === 0 ? (
                <Empty title="Nessun template" text="Scrivi prima l'email nella sezione Template."><button className="btn pri" onClick={() => go("templates")}>Vai ai template</button></Empty>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "minmax(0,.9fr) minmax(0,1.2fr)", gap: 24 }}>
                  <div className="col" style={{ gap: 8 }}>
                    {(templates ?? []).map((t) => (
                      <button key={t.id} className={`radio-card ${templateId === t.id ? "on" : ""}`} onClick={() => setTemplateId(t.id)}>
                        <span className="rd" /><div className="grow" style={{ minWidth: 0 }}><div className="b">{t.name}</div><div className="muted xs" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.subject}</div></div>
                      </button>
                    ))}
                  </div>
                  <div className="col" style={{ gap: 8 }}>
                    {rendered?.error && <div className="alert bad" role="alert"><div><b>Questo template ha un errore.</b> {rendered.error}</div></div>}
                    {rendered && !rendered.error && (
                      <div className="mailframe"><div className="mailhead">{rendered.subject}</div><iframe title="Anteprima" sandbox="" srcDoc={doc} style={{ height: 320 }} /></div>
                    )}
                    {rendered && rendered.unknown.length > 0 && <div className="alert warn"><div className="sm">Variabili non previste: <span className="mono">{rendered.unknown.join(", ")}</span></div></div>}
                  </div>
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <div><h2 className="h1" style={{ fontSize: 20 }}>A chi lo invii?</h2><p className="muted" style={{ marginTop: 3 }}>Ogni persona del gruppo riceve l'email una sola volta.</p></div>
              {groups && groups.length === 0 ? (
                <Empty title="Nessun gruppo" text="Importa o aggiungi dei destinatari."><button className="btn pri" onClick={() => go("recipients")}>Vai ai destinatari</button></Empty>
              ) : (
                <div className="col" style={{ gap: 8 }}>
                  {(groups ?? []).map((g) => (
                    <button key={g.id} disabled={g.total === 0} className={`radio-card ${groupId === g.id ? "on" : ""}`} onClick={() => setGroupId(g.id)} style={{ opacity: g.total === 0 ? 0.5 : 1 }}>
                      <span className="rd" /><div className="b grow">{g.name}</div><span className="mono sm muted">{n(g.total)} persone</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}

          {step === 3 && (
            <>
              <div><h2 className="h1" style={{ fontSize: 20 }}>Quanto velocemente spedire?</h2><p className="muted" style={{ marginTop: 3 }}>Le email partono a gruppi, con una pausa tra l'uno e l'altro.</p></div>
              <div className="col" style={{ gap: 8 }}>
                {(Object.keys(PROFILES) as Exclude<Speed, "custom">[]).map((k) => (
                  <button key={k} className={`radio-card ${speed === k ? "on" : ""}`} onClick={() => pickSpeed(k)}>
                    <span className="rd" /><div className="grow"><div className="b">{PROFILES[k].label}</div><div className="muted xs">{PROFILES[k].hint}</div></div>
                  </button>
                ))}
                {speed === "custom" && <div className="radio-card on"><span className="rd" /><div className="b">Personalizzata</div></div>}
              </div>
              <div className="alert info" role="status"><div className="sm">{n(estimate.tranches)} gruppi da {tranche} email · durata circa <b>{fmtDuration(estimate.seconds)}</b>{estimate.limited && rate ? ` (limite del server: ${n(rate)} email all'ora)` : ""}</div></div>
              {rate && estimate.limited && <div className="alert warn" role="status"><AlertTriangle size={16} style={{ marginTop: 2 }} /><div className="sm"><b>{server?.name} permette {n(rate)} email all'ora.</b> L'invio rallenta da solo per rispettarlo.</div></div>}

              <div className="col" style={{ gap: 8 }}>
                <span className="lab" style={{ margin: 0 }}>Quando partire</span>
                <div className="row" style={{ gap: 10, alignItems: "stretch" }}>
                  <button className={`radio-card ${!later ? "on" : ""}`} onClick={() => setLater(false)}><span className="rd" /><div className="b">Subito</div></button>
                  <button className={`radio-card ${later ? "on" : ""}`} onClick={() => setLater(true)}><span className="rd" /><div className="b">Più tardi…</div></button>
                </div>
                {later && (
                  <div className="row" style={{ alignItems: "flex-start" }}>
                    <div style={{ width: 200 }}><Field label="Data" htmlFor="w-date"><input id="w-date" type="date" className="inp" value={when.date} onChange={(e) => setWhen({ ...when, date: e.target.value })} /></Field></div>
                    <div style={{ width: 140 }}><Field label="Ora" htmlFor="w-time"><input id="w-time" type="time" className="inp" value={when.time} onChange={(e) => setWhen({ ...when, time: e.target.value })} /></Field></div>
                    <div className="hint grow" style={{ alignSelf: "end", margin: 0 }}>ilPostino deve restare aperto (può stare nella barra di sistema).</div>
                  </div>
                )}
                {laterInvalid && <div className="alert bad"><div className="sm">La data di partenza deve essere futura.</div></div>}
              </div>

              <button className="btn ghost s" style={{ alignSelf: "flex-start", padding: "0 4px" }} onClick={() => setAdvanced(!advanced)}>{advanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}Opzioni avanzate</button>
              {advanced && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 14 }}>
                  <Field label="Email per gruppo"><Stepper label="Email per gruppo" value={tranche} min={1} onChange={(v) => { setTranche(v); setSpeed("custom"); }} /></Field>
                  <Field label="Pausa tra gruppi (s)"><Stepper label="Pausa tra gruppi" value={pause} onChange={(v) => { setPause(v); setSpeed("custom"); }} /></Field>
                  <Field label="Tentativi per errore"><Stepper label="Tentativi per errore" value={retries} onChange={setRetries} /></Field>
                  <Field label="Attesa tra tentativi (s)"><Stepper label="Attesa tra tentativi" value={delay} onChange={setDelay} /></Field>
                </div>
              )}
            </>
          )}

          {step === 4 && (
            <>
              <h2 className="h1" style={{ fontSize: 20 }}>Tutto pronto?</h2>
              <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.1fr)", gap: 28, alignItems: "start" }}>
                <div className="col" style={{ gap: 0 }}>
                  {[["Da", server ? `${server.sender_name ?? server.name} · ${server.sender_email}` : ""], ["A", `${group?.name ?? ""} · ${n(count)} persone`], ["Oggetto", rendered?.subject ?? ""], ["Partenza", later ? `${new Date(`${when.date}T${when.time}`).toLocaleString("it-IT", { dateStyle: "medium", timeStyle: "short" })}` : `Subito · circa ${fmtDuration(estimate.seconds)}`]].map(([k, v]) => (
                    <div key={k} className="row" style={{ minHeight: 38, borderBottom: "1px solid var(--line)" }}><span className="muted sm" style={{ width: 100, flex: "none" }}>{k}</span><span className="sm b">{v}</span></div>
                  ))}
                </div>
                <div className="col" style={{ gap: 12 }}>
                  <div className="mailframe"><div className="mailhead">{rendered?.subject}</div><iframe title="Anteprima finale" sandbox="" srcDoc={doc} style={{ height: 260 }} /></div>
                  <div className="row" style={{ gap: 8 }}>
                    <input className="inp" aria-label="Indirizzo per la prova" placeholder="tuo.indirizzo@esempio.it" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
                    <button className="btn" style={{ flex: "none" }} disabled={!testTo.includes("@")} onClick={sendTest}>Invia una prova</button>
                  </div>
                  {testResult && <div className="okc xs">{testResult}</div>}
                </div>
              </div>
            </>
          )}

          <hr className="hr" />
          <div className="row">
            {step > 0 && <button className="btn ghost" onClick={() => setStep(step - 1)}><ArrowLeft size={15} />Indietro</button>}
            {step < 4 ? (
              <button className="btn pri sp" disabled={!canNext} onClick={() => setStep(step + 1)}>Avanti<ArrowRight size={15} /></button>
            ) : (
              <button className="btn pri lg sp" disabled={busy} onClick={launch}><Send size={15} />{later ? "Programma l'invio" : `Invia a ${n(count)} persone`}</button>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
