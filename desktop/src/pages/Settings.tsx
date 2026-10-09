import { useEffect, useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { applyTheme, getThemeMode, ThemeMode } from "../lib/theme";
import { Seg, Stepper, Switch, useAction, useApp, useLoad } from "../lib/ui";

function useSetting(key: string, def: string) {
  const [value, setValue] = useState(def);
  useEffect(() => { api.settingsGet(key, def).then(setValue); }, [key, def]);
  const set = (v: string) => { setValue(v); api.settingsSet(key, v); };
  return [value, set] as const;
}

export default function Settings() {
  const { ask, toast } = useApp();
  const run = useAction();
  const info = useLoad(api.dbInfo, []);
  const [theme, setTheme] = useState<ThemeMode>(getThemeMode());
  const [background, setBackground] = useSetting("background", "1");
  const [notifications, setNotifications] = useSetting("notifications", "1");
  const [threshold, setThreshold] = useSetting("error_threshold", "8");

  const backup = async () => {
    const stamp = new Date().toISOString().slice(0, 10);
    const dest = await save({ defaultPath: `ilpostino-backup-${stamp}.db`, filters: [{ name: "Database ilPostino", extensions: ["db"] }] });
    if (dest) { await run(() => api.backupDatabase(dest), "Copia salvata"); info.reload(); }
  };

  const importFile = async () => {
    const src = await open({ multiple: false, filters: [{ name: "Database ilPostino", extensions: ["db", "sqlite"] }] });
    if (typeof src !== "string") return;
    if (!(await ask("Importare i dati da questo file?", "Contatti, template e server vengono aggiunti a quelli esistenti: nulla viene sovrascritto. Il file originale non viene modificato.", "Importa"))) return;
    const r = await run(() => api.importDatabase(src));
    if (r) toast(`Importati ${r.contacts} destinatari, ${r.groups} gruppi, ${r.templates} template, ${r.servers} server (disattivati: riattivali dopo aver controllato).`);
  };

  const mb = info.data ? (info.data.size_bytes / 1024 / 1024).toFixed(1).replace(".", ",") : "…";

  return (
    <main className="main">
      <div className="ph"><div><h1 className="h1">Impostazioni</h1></div></div>
      <div className="col" style={{ gap: 14, maxWidth: 720, paddingBottom: 24 }}>
        <section className="card pad col" style={{ gap: 16 }}>
          <div className="row"><div className="grow b">Tema</div><Seg value={theme} onChange={(m) => { setTheme(m); applyTheme(m); }} options={[["light", "Chiaro"], ["dark", "Scuro"], ["system", "Come il sistema"]]} /></div>
          <hr className="hr" />
          <div className="row"><div className="grow"><div className="b">Continua in background quando chiudo la finestra</div><div className="muted xs">Solo se c'è un invio in corso o programmato</div></div><Switch on={background === "1"} label="Continua in background" onChange={(v) => setBackground(v ? "1" : "0")} /></div>
          <hr className="hr" />
          <div className="row"><div className="grow b">Avvisami quando un invio finisce o si ferma</div><Switch on={notifications === "1"} label="Notifiche" onChange={(v) => setNotifications(v ? "1" : "0")} /></div>
          <hr className="hr" />
          <div className="row"><div className="grow"><div className="b">Pausa automatica dopo errori consecutivi</div><div className="muted xs">L'invio si ferma e puoi riprenderlo quando vuoi</div></div><div style={{ width: 120 }}><Stepper label="Errori consecutivi" value={parseInt(threshold, 10) || 8} min={1} onChange={(v) => setThreshold(String(v))} /></div></div>
        </section>

        <section className="card pad col" style={{ gap: 14 }}>
          <div className="row"><div className="grow"><div className="b">I tuoi dati</div><div className="muted xs" style={{ marginTop: 2 }}>Salvati solo su questo computer · {mb} MB</div></div><button className="btn s" onClick={() => run(api.openDataFolder)}>Apri cartella</button></div>
          {info.data && !info.data.last_backup && <div className="alert warn"><AlertTriangle size={16} style={{ marginTop: 2 }} /><div className="sm">Non hai ancora fatto un backup.</div></div>}
          {info.data?.last_backup && <div className="muted xs">Ultimo backup: {info.data.last_backup}</div>}
          <div className="row" style={{ gap: 8 }}><button className="btn pri" onClick={backup}>Salva una copia</button><button className="btn ghost sp" onClick={importFile}>Importa da un file…</button></div>
          <div className="hint" style={{ marginTop: 0 }}>«Importa» accetta un backup o il file <span className="mono">ilpostino.db</span> della vecchia versione Python (contatti, template e server; le password passano nel portachiavi).</div>
        </section>
      </div>
    </main>
  );
}
