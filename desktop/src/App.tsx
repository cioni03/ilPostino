import { useEffect, useMemo, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";
import { LayoutDashboard, Minus, Send, Server, SlidersHorizontal, Square, Users, FileText, X } from "lucide-react";
import logo from "./assets/logo.png";
import { api } from "./lib/api";
import { AppContext, Page, useApp, useDialogs, useLoad } from "./lib/ui";
import Overview from "./pages/Overview";
import Campaigns from "./pages/Campaigns";
import NewCampaign from "./pages/NewCampaign";
import Recipients from "./pages/Recipients";
import Templates from "./pages/Templates";
import Smtp from "./pages/Smtp";
import Settings from "./pages/Settings";

const NAV: { page: Page; label: string; icon: typeof Send; section?: string }[] = [
  { page: "overview", label: "Panoramica", icon: LayoutDashboard, section: "Lavoro" },
  { page: "campaigns", label: "Campagne", icon: Send },
  { page: "recipients", label: "Destinatari", icon: Users },
  { page: "templates", label: "Template", icon: FileText },
  { page: "smtp", label: "Server SMTP", icon: Server, section: "Configurazione" },
  { page: "settings", label: "Impostazioni", icon: SlidersHorizontal },
];

function Titlebar() {
  const win = getCurrentWindow();
  return (
    <header className="titlebar">
      <div className="tb-brand" data-tauri-drag-region>
        <img src={logo} alt="" data-tauri-drag-region />
        ilPostino
      </div>
      <div className="tb-ctrl">
        <button aria-label="Riduci a icona" onClick={() => win.minimize()}><Minus size={14} /></button>
        <button aria-label="Ingrandisci" onClick={() => win.toggleMaximize()}><Square size={12} /></button>
        <button aria-label="Chiudi" className="close" onClick={() => win.close()}><X size={16} /></button>
      </div>
    </header>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [arg, setArg] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const { toast, ask, layer } = useDialogs();

  useEffect(() => {
    const un = listen("campaigns-changed", () => setTick((t) => t + 1));
    return () => {
      un.then((f) => f());
    };
  }, []);

  const ctx = useMemo(
    () => ({
      go: (p: Page, a?: number) => { setPage(p); setArg(a ?? null); },
      arg, tick, toast, ask,
    }),
    [arg, tick, toast, ask],
  );

  return (
    <AppContext.Provider value={ctx}>
      <Shell page={page} />
      {layer}
    </AppContext.Provider>
  );
}

function Shell({ page }: { page: Page }) {
  const campaigns = useLoad(api.campaignsList, [], true).data ?? [];
  const active = campaigns.filter((c) => c.status === "running").length;
  const body = {
    overview: <Overview />,
    campaigns: <Campaigns />,
    new: <NewCampaign />,
    recipients: <Recipients />,
    templates: <Templates />,
    smtp: <Smtp />,
    settings: <Settings />,
  }[page];

  return (
    <div className="app">
      <Titlebar />
      <div className="body">
        {page !== "new" && <Sidebar page={page} active={active} />}
        {body}
      </div>
      <footer className="statusbar">
        {active > 0 ? <span className="it"><span className="pulse" />{active === 1 ? "1 invio in corso" : `${active} invii in corso`}</span> : <span className="it">Nessun invio in corso</span>}
        <span className="it sp">I dati restano su questo computer</span>
      </footer>
    </div>
  );
}

function Sidebar({ page, active }: { page: Page; active: number }) {
  const { go } = useApp();
  return (
    <nav className="side" aria-label="Navigazione principale">
      {NAV.map((item) => (
        <div key={item.page} style={{ display: "contents" }}>
          {item.section && <div className="lbl">{item.section}</div>}
          <button className={`nav ${page === item.page ? "on" : ""}`} onClick={() => go(item.page)}>
            <item.icon size={16} />
            {item.label}
            {item.page === "campaigns" && active > 0 && <span className="dot" aria-label="Invio in corso" />}
          </button>
        </div>
      ))}
    </nav>
  );
}
