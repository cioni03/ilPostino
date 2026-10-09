"""Interfaccia: layout condiviso e le cinque pagine dell'app."""

from __future__ import annotations

import html as html_module
import inspect
import math
import urllib.parse
from contextlib import contextmanager
from datetime import datetime

from nicegui import ui

from app import services, templating
from app.mailer import MailSendError, send_email

NAV_ITEMS = [
    ("/", "Nuovo invio", "rocket_launch"),
    ("/smtp", "Server SMTP", "dns"),
    ("/groups", "Destinatari", "group"),
    ("/templates", "Template email", "mark_email_read"),
    ("/activity", "Attività e log", "query_stats"),
]

CAMPAIGN_LABELS = {
    "running": ("In corso", "blue"),
    "paused": ("In pausa", "amber"),
    "scheduled": ("Programmato", "purple"),
    "completed": ("Completato", "green"),
    "cancelled": ("Annullato", "gray"),
}

ITEM_LABELS = {
    "pending": ("In coda", "gray"),
    "processing": ("Invio…", "blue"),
    "sent": ("Inviata", "green"),
    "failed_temp": ("Fallita (temp.)", "amber"),
    "failed_perm": ("Fallita", "red"),
    "skipped": ("Saltata", "purple"),
    "cancelled": ("Annullata", "gray"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --brand: #0F60F9;
  --brand-light: #EFF6FF;
  --brand-dark: #0B4ED4;
}

html, body {
  background-color: #f8fafc;
  color: #1e293b;
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}

.mono {
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* Header Navigation items */
.header-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 500;
  color: #475569;
  transition: all 0.15s ease;
  cursor: pointer;
  border: 1px solid transparent;
}
.header-nav-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
}
.header-nav-btn.active {
  background: #EFF6FF;
  color: #0F60F9;
  font-weight: 600;
  border-color: #DBEAFE;
}

/* Cards & Surfaces */
.card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 1px 3px 0 rgba(15, 23, 42, 0.04), 0 1px 2px -1px rgba(15, 23, 42, 0.03);
  transition: all 0.15s ease-in-out;
}
.card-hover:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.06), 0 2px 4px -2px rgba(15, 23, 42, 0.04);
}

/* Typography */
.page-title {
  font-size: 21px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.page-subtitle {
  font-size: 13.5px;
  color: #64748b;
  margin-top: 2px;
}

/* Buttons */
.q-btn {
  text-transform: none !important;
  letter-spacing: 0 !important;
  font-weight: 600;
  border-radius: 10px;
  font-size: 13.5px;
  transition: all 0.15s ease;
}
.q-btn--rectangle {
  padding: 7px 16px;
}

/* Form Controls */
.q-field--outlined .q-field__control {
  border-radius: 10px !important;
  background: #ffffff;
  min-height: 44px;
  border-color: #cbd5e1;
  transition: all 0.15s ease;
}
.q-field--outlined.q-field--focused .q-field__control {
  box-shadow: 0 0 0 3px rgba(15, 96, 249, 0.15);
  border-color: #0F60F9 !important;
}
.q-field__label {
  font-size: 13.5px;
  color: #64748b;
}

/* Tables */
.q-table__container {
  border-radius: 14px !important;
  border: 1px solid #e2e8f0 !important;
  background: #ffffff !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
  overflow: hidden;
}
.q-table thead tr {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.q-table thead th {
  font-weight: 600;
  color: #475569;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
}
.q-table tbody td {
  font-size: 13.5px;
  color: #334155;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
}
.q-table tbody tr:hover {
  background: #f8fafc;
}

/* Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 16px;
  white-space: nowrap;
}
.badge-gray   { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
.badge-green  { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
.badge-red    { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.badge-amber  { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
.badge-blue   { background: #EFF6FF; color: #0F60F9; border: 1px solid #BFDBFE; }
.badge-purple { background: #faf5ff; color: #6d28d9; border: 1px solid #e9d5ff; }

/* Log Console */
.nicegui-log {
  background: #0f172a !important;
  color: #f1f5f9 !important;
  border-radius: 12px !important;
  padding: 14px 16px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
  border: 1px solid #1e293b !important;
}

/* Dialog Backdrop */
.q-dialog__backdrop {
  backdrop-filter: blur(4px);
  background: rgba(15, 23, 42, 0.45) !important;
}
.q-dialog .card {
  box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1);
}

/* Scrollbars */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* Boxa il corpo di tutte le pagine esattamente come l'header (max 1140px centrato) */
.nicegui-content {
  max-width: 1140px !important;
  margin: 0 auto !important;
  padding: 12px 24px 40px 24px !important;
  width: 100% !important;
  box-sizing: border-box !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 16px !important;
}

/* Textarea editor HTML: fa occupare a .q-field__control l'altezza massima (#c64 > label > div > div) */
.html-editor-textarea {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 auto !important;
  height: 100% !important;
}
.html-editor-textarea .q-field__inner {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 auto !important;
  height: 100% !important;
}
.html-editor-textarea .q-field__control {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 auto !important;
  height: 100% !important;
  min-height: 520px !important;
}
.html-editor-textarea .q-field__control-container {
  display: flex !important;
  flex-direction: column !important;
  flex: 1 1 auto !important;
  height: 100% !important;
}
.html-editor-textarea .q-field__native {
  flex: 1 1 auto !important;
  height: 100% !important;
  min-height: 480px !important;
  resize: vertical !important;
}
.csv-paste-field textarea {
  min-height: clamp(280px, 45vh, 480px) !important;
  resize: vertical !important;
  font-size: 12.5px;
  line-height: 1.7;
}
</style>
"""


# ---------------------------------------------------------------- helper condivisi

def shell(title: str, active_route: str) -> None:
    ui.colors(primary="#0F60F9", positive="#10b981", negative="#ef4444", warning="#f59e0b", info="#0F60F9")
    ui.add_head_html(CSS)
    ui.add_head_html('''<script>
        window.__newsletterUnsaved = false;
        window.addEventListener('beforeunload', (event) => {
            if (window.__newsletterUnsaved) {
                event.preventDefault();
                event.returnValue = '';
            }
        });
    </script>''')
    client = ui.context.client
    client._newsletter_navigation = {"dirty": False, "confirming": False}

    async def navigate(route: str) -> None:
        if route == active_route:
            return
        navigation = client._newsletter_navigation
        if navigation["confirming"]:
            return
        if navigation["dirty"]:
            navigation["confirming"] = True
            try:
                if not await ask_confirm("Modifiche non salvate",
                                         "Se cambi pagina, le modifiche non salvate andranno perse.",
                                         "Scarta e cambia pagina"):
                    return
            finally:
                navigation["confirming"] = False
        await ui.run_javascript("window.__newsletterUnsaved = false")
        ui.navigate.to(route)

    # Top Header Bar con Logo a sinistra e Voci di navigazione incorporate (Boxato a max 1140px)
    with ui.header().classes("h-[64px] bg-white border-b border-slate-200 shadow-none z-30"):
        with ui.row().classes("items-center justify-between h-full max-w-[1140px] mx-auto px-6 w-full"):
            with ui.row().classes("items-center gap-3"):
                ui.image("/brand/icon.png").classes("w-9 h-9 rounded-xl object-cover select-none").props('alt="ilPostino"')
                ui.label("ilPostino").classes("text-[17px] font-bold text-slate-900 tracking-tight leading-none")

            with ui.row().classes("items-center gap-1.5"):
                for route, label, icon in NAV_ITEMS:
                    is_active = route == active_route
                    cls = f"header-nav-btn {'active' if is_active else ''}"
                    with ui.row().classes(cls).props('role="button" tabindex="0"').on("click", lambda r=route: navigate(r)).on("keydown.enter", lambda r=route: navigate(r)):
                        ui.icon(icon, size="18px").classes("text-[#0F60F9]" if is_active else "text-slate-400")
                        ui.label(label).classes("text-[13.5px]")


def set_page_dirty(dirty: bool) -> None:
    """Protegge sia la navigazione interna sia reload, chiusura e indietro."""
    navigation = ui.context.client._newsletter_navigation
    if navigation["dirty"] == dirty:
        return
    navigation["dirty"] = dirty
    ui.run_javascript(f'window.__newsletterUnsaved = {"true" if dirty else "false"}')


def dialog_shortcuts(dialog, card, on_confirm, on_cancel=None) -> None:
    """Invio conferma; Esc annulla; nei multilinea serve Ctrl/Cmd+Invio."""
    busy = False

    async def handle(e) -> None:
        nonlocal busy
        if busy or dialog.is_deleted or not dialog.value:
            return
        busy = True
        try:
            callback = (on_cancel or dialog.close) if e.args == "cancel" else on_confirm
            result = callback()
            if inspect.isawaitable(result):
                await result
        finally:
            busy = False

    card.props('tabindex="0"')
    card.on("keydown", handle, js_handler='''(event) => {
        if (event.defaultPrevented || event.isComposing || event.repeat) return;
        // Lascia ai menu dei select la gestione della selezione e della chiusura.
        if (document.querySelector('.q-menu')) return;
        if (event.key === 'Escape') {
            event.preventDefault(); event.stopPropagation(); emit('cancel');
        } else if (event.key === 'Enter') {
            const modified = event.ctrlKey || event.metaKey;
            if (!modified && (event.target.tagName === 'TEXTAREA' || event.target.isContentEditable)) return;
            // Un pulsante focalizzato mantiene la propria azione (anche Annulla).
            if (!modified && event.target.closest('button')) return;
            event.preventDefault(); event.stopPropagation(); emit('confirm');
        }
    }''')


def guard_dialog_changes(dialog, fields) -> None:
    """Segnala modifiche dei form finché il popup rimane aperto."""
    initial = [field.value for field in fields]

    def update() -> None:
        set_page_dirty(bool(dialog.value) and [field.value for field in fields] != initial)

    for field in fields:
        field.on_value_change(lambda e: update())
    dialog.on_value_change(lambda e: update())


def title_block(title: str, subtitle: str = "") -> None:
    with ui.column().classes("gap-0.5"):
        ui.label(title).classes("page-title")
        if subtitle:
            ui.label(subtitle).classes("page-subtitle")


def badge_span(label: str, color: str = "gray") -> ui.html:
    return ui.html(f'<span class="badge badge-{color}">{label}</span>')


def fmt_dt(value) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else "—"


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"~{seconds}s"
    minutes, sec = divmod(seconds, 60)
    return f"~{minutes}m {sec:02d}s" if minutes < 60 else f"~{minutes // 60}h {minutes % 60:02d}m"


async def ask_confirm(title: str, message: str, confirm_label: str = "Conferma", danger: bool = False) -> bool:
    """Popup di conferma con supporto tastiera: Invio = conferma, Esc = annulla."""
    with ui.dialog() as dialog:
        with ui.card().classes("w-[440px] p-6 card focus:outline-none").props('tabindex="0"') as card:
            with ui.row().classes("items-center gap-3 mb-1"):
                with ui.element("div").classes(
                    f"w-10 h-10 rounded-xl flex items-center justify-center "
                    f"{'bg-rose-50 text-rose-600' if danger else 'bg-blue-50 text-[#0F60F9]'}"
                ):
                    ui.icon("warning" if danger else "help_outline", size="22px")
                ui.label(title).classes("text-lg font-bold text-slate-900")
            ui.label(message).classes("text-sm text-slate-600 leading-relaxed mb-4 pl-1")
            with ui.row().classes("w-full justify-end gap-2.5"):
                ui.button("Annulla", on_click=lambda: dialog.submit(False)).props("flat no-caps").classes("text-slate-600")
                confirm_btn = ui.button(confirm_label, on_click=lambda: dialog.submit(True)).props("unelevated no-caps autofocus")
                if danger:
                    confirm_btn.props("color=negative").classes("bg-rose-600")
                else:
                    confirm_btn.props("color=primary").classes("bg-[#0F60F9] text-white")

            dialog_shortcuts(dialog, card, lambda: dialog.submit(True), lambda: dialog.submit(False))
    return bool(await dialog)


def iframe_html(
    html: str,
    height: int = 500,
    mode: str = "desktop",
    title: str = "",
    allow_popout: bool = True,
) -> None:
    """Anteprima isolata per client email: formato Desktop (landscape 100%) o Mobile (portrait 375px)."""
    escaped = html_module.escape(html or "", quote=True)
    encoded = urllib.parse.quote(html or "")

    if mode == "mobile":
        max_w = "375px"
        device_label = "Mobile (Portrait 375px)"
    else:  # desktop landscape
        max_w = "100%"
        device_label = "Desktop (Landscape)"

    body_style = f"width:100%;height:{height}px;border:none;background:#f8fafc;display:block"

    popout_btn = (
        f'<button onclick="(() => {{ const w = window.open(); w.document.write(decodeURIComponent(\'{encoded}\')); w.document.close(); }})()" '
        f'style="background:none;border:none;cursor:pointer;color:#0F60F9;font-size:11px;font-weight:600;display:flex;align-items:center;gap:4px;padding:2px 8px;border-radius:6px;transition:background 0.15s;" '
        f'onmouseover="this.style.background=\'#eff6ff\'" onmouseout="this.style.background=\'transparent\'" '
        f'title="Apri l\'anteprima in una nuova finestra/scheda a risoluzione nativa">'
        f'↗ Apri nel browser'
        f'</button>'
    ) if allow_popout else ""

    header_title = f'<span style="font-size:11px;color:#334155;margin-left:8px;font-weight:600">{title or device_label}</span>'

    ui.html(
        f'<div style="max-width:{max_w};width:100%;margin:0 auto;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;background:#fff;box-shadow:0 2px 8px rgba(15,23,42,0.06);transition:all 0.2s ease">'
        f'  <div style="background:#f8fafc;padding:8px 14px;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;justify-content:space-between">'
        f'    <div style="display:flex;align-items:center;gap:6px">'
        f'      <span style="width:10px;height:10px;border-radius:50%;background:#f87171;display:inline-block"></span>'
        f'      <span style="width:10px;height:10px;border-radius:50%;background:#fbbf24;display:inline-block"></span>'
        f'      <span style="width:10px;height:10px;border-radius:50%;background:#34d399;display:inline-block"></span>'
        f'      {header_title}'
        f'    </div>'
        f'    {popout_btn}'
        f'  </div>'
        f'  <iframe sandbox="" srcdoc="{escaped}" style="{body_style}"></iframe>'
        f'</div>',
        sanitize=False,
    )


def variable_chips() -> None:
    with ui.row().classes("gap-1.5 flex-wrap items-center bg-slate-50 border border-slate-200/70 p-2.5 rounded-xl w-full"):
        ui.icon("info", size="16px").classes("text-slate-400 ml-1")
        ui.label("Variabili (clic per copiare):").classes("text-xs font-semibold text-slate-500 mr-1")
        for var, description in templating.KNOWN_VARIABLES.items():
            chip = ui.button(f"{{{{ {var} }}}}", on_click=lambda v=var: _copy_var(v))
            chip.props("flat dense size=sm no-caps").classes("mono text-[#0F60F9] bg-white border border-blue-200/80 rounded-lg px-2 shadow-xs hover:bg-blue-50")
            chip.tooltip(description)


def _copy_var(var: str) -> None:
    token = f"{{{{ {var} }}}}"
    ui.run_javascript(f'navigator.clipboard.writeText("{token}").catch(() => null)')
    ui.notify(f"Copiato: {token}", type="info", position="bottom")


class Wizard:
    """Stepper moderno a schede con validazione."""

    def __init__(self, labels: list[str], on_next=None, on_enter=None, finish_label="Conferma"):
        self.labels, self.index = labels, 0
        self.on_next, self.on_enter, self._finish_label = on_next, on_enter, finish_label
        self.on_finish = None

        with ui.element("div").classes("card p-4 w-full mb-1"):
            with ui.row().classes("w-full items-center justify-between"):
                self._indicators = []
                for i, label in enumerate(labels):
                    with ui.row().classes("items-center gap-2 cursor-pointer").on("click", lambda idx=i: self._try_go_to(idx)):
                        dot = ui.label(str(i + 1)).classes(
                            "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-200"
                        )
                        with ui.column().classes("gap-0"):
                            step_title = ui.label(label).classes("text-sm font-semibold transition-colors duration-200")
                            step_sub = ui.label(f"Passo {i+1}").classes("text-[11px] text-slate-400 font-medium")
                        self._indicators.append((dot, step_title, step_sub))
                    if i < len(labels) - 1:
                        ui.element("div").classes("h-[2px] bg-slate-200 flex-1 mx-3 rounded-full min-w-[24px]")

        self.main_card = ui.element("div").classes("card p-7 w-full flex flex-col gap-6")
        with self.main_card:
            self.panels: list[ui.column] = []
            self.body = ui.column().classes("w-full gap-5")

            ui.separator().classes("my-2")
            with ui.row().classes("w-full justify-between items-center"):
                self.back_btn = ui.button("Indietro", icon="arrow_back", on_click=self.prev).props("flat no-caps").classes("text-slate-600")
                self.next_btn = ui.button("Avanti", on_click=self._next_click).props("icon-right=arrow_forward unelevated no-caps").classes("bg-[#0F60F9] text-white px-5")

    @contextmanager
    def panel(self):
        with self.body:
            with ui.column().classes("w-full gap-5") as p:
                self.panels.append(p)
                yield p
        self._update()

    def prev(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._update()

    def _try_go_to(self, target: int) -> None:
        if target < self.index:
            self.index = target
            self._update()

    def set_finish_label(self, text: str) -> None:
        self._finish_label = text
        if self.index == len(self.panels) - 1:
            self.next_btn.set_text(text)

    async def _next_click(self) -> None:
        if self.index < len(self.panels) - 1:
            if self.on_next:
                result = self.on_next(self.index)
                if result is False:
                    return
                if isinstance(result, str):
                    ui.notify(result, type="warning", position="top")
                    return
            self.index += 1
            self._update()
        elif self.on_finish:
            result = self.on_finish()
            if hasattr(result, "__await__"):
                await result

    def _update(self) -> None:
        for i, panel in enumerate(self.panels):
            panel.visible = (i == self.index)

        for i, (dot, title, sub) in enumerate(self._indicators):
            if i == self.index:
                dot.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-[#0F60F9] text-white shadow-sm shadow-blue-300")
                dot.set_text(str(i + 1))
                title.classes(replace="text-sm font-bold text-[#0F60F9]")
            elif i < self.index:
                dot.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-200")
                dot.set_text("✓")
                title.classes(replace="text-sm font-semibold text-slate-800")
            else:
                dot.classes(replace="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 text-slate-500 border border-slate-200")
                dot.set_text(str(i + 1))
                title.classes(replace="text-sm font-medium text-slate-500")

        self.back_btn.visible = (self.index > 0)
        is_last = (self.index == len(self.panels) - 1)
        self.next_btn.set_text(self._finish_label if is_last else "Avanti")
        self.next_btn.props(f"icon-right={'rocket_launch' if is_last else 'arrow_forward'}")

        if self.on_enter:
            self.on_enter(self.index)


# ================================================================ DASHBOARD

@ui.page("/")
def page_dashboard() -> None:
    shell("Nuovo invio", "/")
    d = services.DEFAULT_SEND
    state = {
        "smtp_id": None, "template_id": None, "override": False, "subject": "", "html": "",
        "group_id": None, "count": 0, "batch": d["tranche_size"], "pause": d["pause_seconds"],
        "retries": d["max_retries"], "delay": d["retry_delay"], "scheduled": "", "start_mode": "now",
    }
    submission = {"done": False}

    # Rimossa la sezione 4 card statistiche in cima su richiesta
    title_block("Configura un nuovo invio", "Segui i 5 passaggi guidati per lanciare la tua newsletter in sicurezza")

    def selected_template():
        return services.get_template(state["template_id"]) if state["template_id"] else None

    def validate(step: int):
        if step == 0 and not state["smtp_id"]:
            return "Seleziona un server SMTP attivo prima di procedere."
        if step == 1:
            snap = effective_snapshot()
            if not snap["subject"].strip():
                return "L'oggetto della email non può essere vuoto."
            for label, text in (("Oggetto", snap["subject"]), ("Corpo HTML", snap["html"])):
                error = templating.check_syntax(text)
                if error:
                    return f"{label}: {error}"
            unknown = templating.unknown_variables(snap["html"])
            if unknown:
                ui.notify(f"Attenzione, variabili non previste: {', '.join(unknown)}", type="warning", position="top")
        if step == 2 and (not state["group_id"] or state["count"] <= 0):
            return "Seleziona un gruppo contenente almeno un destinatario."
        if step == 3 and state["start_mode"] == "scheduled":
            try:
                if datetime.strptime(state["scheduled"], "%Y-%m-%d %H:%M") <= datetime.now():
                    return "La data e ora programmata deve essere futura."
            except ValueError:
                return "Formato data non valido: utilizza AAAA-MM-GG HH:MM."
        return None

    def effective_snapshot() -> dict:
        if state["override"] or state["template_id"] is None:
            return {"subject": state["subject"], "html": state["html"]}
        t = selected_template()
        return {"subject": t.subject, "html": t.html_body} if t else {"subject": state["subject"], "html": state["html"]}

    def update_estimate() -> None:
        if state["count"] <= 0:
            estimate_pill.set_text("Seleziona prima i destinatari")
            return
        tranches = math.ceil(state["count"] / max(1, state["batch"]))
        total_pause = (tranches - 1) * state["pause"]
        estimate_pill.set_text(f"⚡ {tranches} tranche da max {state['batch']} email · {fmt_duration(total_pause)} di pause stimate")

    async def send_test(to_addr: str) -> None:
        server = services.get_smtp(state["smtp_id"]) if state["smtp_id"] else None
        if server is None:
            ui.notify("Seleziona prima un server SMTP", type="warning", position="top")
            return
        if not to_addr or "@" not in to_addr:
            ui.notify("Inserisci un indirizzo email valido per il test", type="warning", position="top")
            return
        smtp = {c: getattr(server, c) for c in ("host", "port", "security", "username", "password",
                                                "sender_email", "sender_name", "reply_to")}
        snap = effective_snapshot()
        recipients = services.group_contacts(state["group_id"]) if state["group_id"] else []
        ctx = templating.context_for(recipients[0]) if recipients else dict(templating.SAMPLE_CONTEXT)
        test_spinner.visible = True
        test_result.set_text("")
        try:
            await send_email(smtp, to_addr=to_addr.strip(), subject=templating.render(snap["subject"], ctx),
                             html=templating.render(snap["html"], ctx))
            services.add_log(None, "info", f"Email di test inviata a {to_addr}")
            test_result.classes(replace="text-sm font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg")
            test_result.set_text(f"✓ Email di test recapitata con successo a {to_addr}")
        except MailSendError as e:
            test_result.classes(replace="text-sm font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded-lg")
            test_result.set_text(f"✗ Invio test fallito: {e.detail}")
        finally:
            test_spinner.visible = False

    wizard = Wizard(["Server SMTP", "Template email", "Destinatari", "Parametri invio", "Riepilogo e conferma"],
                    on_next=validate, finish_label="Avvia invio")

    # -------- Passo 1: SMTP
    with wizard.panel():
        ui.label("Seleziona il server SMTP").classes("text-base font-bold text-slate-800")
        ui.label("Scegli uno dei server configurati per spedire i messaggi.").classes("text-xs text-slate-500 -mt-3")
        servers = services.list_smtp(active_only=True)
        if not servers:
            with ui.element("div").classes("p-5 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between w-full"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("warning", size="24px").classes("text-amber-600")
                    with ui.column().classes("gap-0"):
                        ui.label("Nessun server SMTP attivo").classes("font-semibold text-amber-900")
                        ui.label("Devi configurare o attivare almeno un profilo SMTP.").classes("text-xs text-amber-700")
                ui.button("Configura SMTP", icon="settings", on_click=lambda: ui.navigate.to("/smtp")).props("unelevated no-caps").classes("bg-amber-600 text-white")

        smtp_select = ui.select(
            {s.id: f"{s.name}  ({s.host}:{s.port} · {s.sender_email})" for s in servers},
            label="Server SMTP mittente",
            on_change=lambda e: state.__setitem__("smtp_id", e.value)
        ).classes("w-full").props("outlined")
        if servers:
            smtp_select.set_value(servers[0].id)
            state["smtp_id"] = servers[0].id

    # -------- Passo 2: Template con Anteprima Grafica
    with wizard.panel():
        templates = services.list_templates()
        ui.label("Scelta e anteprima grafica del messaggio").classes("text-base font-bold text-slate-800")

        def update_step2_preview() -> None:
            snap = effective_snapshot()
            step2_preview_box.clear()
            with step2_preview_box:
                try:
                    rendered = templating.render(snap["html"], dict(templating.SAMPLE_CONTEXT))
                    iframe_html(rendered, height=360)
                except Exception:
                    iframe_html(snap["html"] or "", height=360)

        def on_template_change(e) -> None:
            state["template_id"] = e.value
            t = selected_template()
            if t is not None and not state["override"]:
                state.update(subject=t.subject, html=t.html_body)
                subject_input.set_value(t.subject)
                html_area.set_value(t.html_body)
            update_step2_preview()

        def on_override(e) -> None:
            state["override"] = e.value
            for el in (subject_input, html_area):
                el.set_enabled(e.value)
            if e.value:
                t = selected_template()
                if t is not None:
                    subject_input.set_value(t.subject)
                    html_area.set_value(t.html_body)
            update_step2_preview()

        with ui.row().classes("w-full gap-6 items-start flex-wrap lg:flex-nowrap"):
            # Colonna sinistra: Controlli ed editor
            with ui.column().classes("flex-1 min-w-[340px] gap-3"):
                ui.select({t.id: f"{t.name} — «{t.subject[:50]}»" for t in templates},
                          label="Template di partenza", on_change=on_template_change).classes("w-full").props("outlined dense")

                with ui.row().classes("w-full items-center justify-between p-2.5 bg-slate-50 border border-slate-200/80 rounded-xl"):
                    with ui.column().classes("gap-0"):
                        ui.label("Personalizza solo per questo invio").classes("text-xs font-semibold text-slate-800")
                        ui.label("Non modificherà il template salvato.").classes("text-[11px] text-slate-500")
                    ui.switch("", value=False, on_change=on_override).props("dense")

                variable_chips()
                subject_input = ui.input("Oggetto", on_change=lambda e: (state.__setitem__("subject", e.value), update_step2_preview())).classes("w-full").props("outlined dense")
                html_area = (ui.textarea("Corpo HTML", on_change=lambda e: (state.__setitem__("html", e.value), update_step2_preview()))
                             .classes("w-full mono").props("outlined autogrow").style("min-height:200px;font-size:12px"))
                for el in (subject_input, html_area):
                    el.set_enabled(False)

            # Colonna destra: Anteprima grafica
            with ui.column().classes("flex-1 min-w-[340px] gap-2"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("ANTEPRIMA MESSAGGIO").classes("text-xs font-bold text-slate-500 tracking-wider")
                    ui.button("Aggiorna", icon="refresh", on_click=update_step2_preview).props("flat dense no-caps").classes("text-[#0F60F9] text-xs")
                step2_preview_box = ui.column().classes("w-full")

        if templates:
            state["template_id"] = templates[0].id
            state.update(subject=templates[0].subject, html=templates[0].html_body)
            subject_input.set_value(templates[0].subject)
            html_area.set_value(templates[0].html_body)
            update_step2_preview()

    # -------- Passo 3: Gruppo
    with wizard.panel():
        ui.label("Destinatari dell'invio").classes("text-base font-bold text-slate-800")
        groups = services.list_groups()

        def on_group_change(e) -> None:
            state["group_id"] = e.value
            g = next((x for x in services.list_groups() if x["id"] == e.value), None)
            cnt = g["total"] if g else 0
            state["count"] = cnt
            if cnt > 0:
                group_card.classes(replace="p-4 bg-blue-50/70 border border-blue-200 rounded-xl flex items-center gap-3 w-full")
                group_info.set_text(f"Gruppo selezionato: «{g['name']}» con {cnt} destinatari pronti a ricevere l'email.")
                group_icon.classes(replace="text-[#0F60F9]")
            else:
                group_card.classes(replace="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3 w-full")
                group_info.set_text("Attenzione: questo gruppo non contiene alcun destinatario.")
                group_icon.classes(replace="text-amber-600")

        ui.select({g["id"]: f"{g['name']} ({g['total']} destinatari)" for g in groups},
                  label="Gruppo di destinatari da raggiungere", on_change=on_group_change).classes("w-full").props("outlined")

        with ui.element("div").classes("p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 w-full") as group_card:
            group_icon = ui.icon("group", size="24px").classes("text-slate-400")
            group_info = ui.label("Seleziona un gruppo per visualizzare il numero di destinatari.").classes("text-sm font-medium text-slate-700")

    # -------- Passo 4: Tranche
    with wizard.panel():
        ui.label("Velocità di invio e pianificazione").classes("text-base font-bold text-slate-800")
        ui.label("Suddividi l'invio in lotti per rispettare i limiti del provider SMTP ed evitare blocchi.").classes("text-xs text-slate-500 -mt-3")

        with ui.row().classes("w-full gap-4 flex-wrap"):
            ui.number("Email per tranche", value=state["batch"], min=1, format="%.0f",
                      on_change=lambda e: (state.__setitem__("batch", int(e.value or 1)), update_estimate())).classes("flex-1 min-w-[200px]").props("outlined")
            ui.number("Pausa tra tranche (s)", value=state["pause"], min=0, format="%.0f",
                      on_change=lambda e: (state.__setitem__("pause", int(e.value or 0)), update_estimate())).classes("flex-1 min-w-[200px]").props("outlined")
            ui.number("Max tentativi retry", value=state["retries"], min=0, format="%.0f",
                      on_change=lambda e: state.__setitem__("retries", int(e.value or 0))).classes("flex-1 min-w-[200px]").props("outlined")
            ui.number("Attesa tra retry (s)", value=state["delay"], min=0, format="%.0f",
                      on_change=lambda e: state.__setitem__("delay", int(e.value or 0))).classes("flex-1 min-w-[200px]").props("outlined")

        with ui.element("div").classes("p-4 bg-blue-50/70 border border-blue-200/80 rounded-xl flex items-center gap-2.5 w-full"):
            ui.icon("timer", size="20px").classes("text-[#0F60F9]")
            estimate_pill = ui.label("Calcolo tempi…").classes("text-sm font-semibold text-blue-900")

        with ui.column().classes("gap-2 w-full pt-2"):
            ui.label("Momento di partenza").classes("text-xs font-bold text-slate-500 uppercase tracking-wider")
            with ui.row().classes("gap-4 items-center"):
                ui.radio({"now": "Partenza immediata", "scheduled": "Programma data e ora"}, value="now",
                         on_change=lambda e: (state.__setitem__("start_mode", e.value),
                                              sched_input.set_visibility(e.value == "scheduled"))).props("inline")
            sched_input = ui.input("Data e ora (AAAA-MM-GG HH:MM)", placeholder="2026-12-31 09:30",
                                   on_change=lambda e: state.__setitem__("scheduled", e.value)).classes("w-80").props("outlined dense")
            sched_input.visible = False

    # -------- Passo 5: Test e conferma con Anteprima Grafica
    with wizard.panel():
        ui.label("Verifica finale e invio di prova").classes("text-base font-bold text-slate-800")

        # Box email di prova
        with ui.element("div").classes("p-4 bg-slate-50 border border-slate-200/90 rounded-xl flex flex-col gap-3 w-full"):
            with ui.row().classes("items-center justify-between"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("science", size="20px").classes("text-[#0F60F9]")
                    ui.label("Invia una email di test").classes("text-sm font-bold text-slate-800")
                ui.label("Riceverai una copia di prova con i dati sostituiti.").classes("text-xs text-slate-500")

            with ui.row().classes("items-center gap-3 w-full"):
                test_to = ui.input(placeholder="tuo.indirizzo@example.com").classes("flex-1").props("outlined dense")
                ui.button("Invia prova", icon="send", on_click=lambda: send_test(test_to.value)).props("unelevated no-caps").classes("bg-slate-800 text-white px-4")
                test_spinner = ui.spinner(size="sm").classes("text-[#0F60F9]")
                test_spinner.visible = False
            test_result = ui.label("").classes("text-xs")

        # Scheda di riepilogo + Anteprima grafica affiancate
        summary_container = ui.column().classes("w-full")

    def _render_summary() -> None:
        snap = effective_snapshot()
        mode = f"Programmata: {state['scheduled']}" if state["start_mode"] == "scheduled" and state["scheduled"] else "Immediata"
        srv = next((s for s in services.list_smtp() if s.id == state["smtp_id"]), None)
        grp = next((g for g in services.list_groups() if g["id"] == state["group_id"]), None)
        tranches = math.ceil(state["count"] / max(1, state["batch"]))

        recipients = services.group_contacts(state["group_id"]) if state["group_id"] else []
        ctx = templating.context_for(recipients[0]) if recipients else dict(templating.SAMPLE_CONTEXT)
        try:
            final_rendered_html = templating.render(snap["html"], ctx)
            final_subject = templating.render(snap["subject"], ctx)
        except Exception:
            final_rendered_html = snap["html"]
            final_subject = snap["subject"]

        summary_container.clear()
        with summary_container:
            with ui.row().classes("w-full gap-6 items-start flex-wrap lg:flex-nowrap"):
                # Colonna Sinistra: Parametri
                with ui.element("div").classes("card p-5 flex-1 min-w-[340px] bg-slate-50/70 border border-slate-200/80"):
                    ui.label("Parametri di invio").classes("text-xs font-bold text-slate-500 uppercase tracking-wider mb-3")
                    items = [
                        ("Server SMTP", f"{srv.name} ({srv.host}:{srv.port})" if srv else "—", "dns"),
                        ("Oggetto", final_subject[:75] or "—", "title"),
                        ("Gruppo", f"{grp['name']} ({state['count']} destinatari)" if grp else "—", "group"),
                        ("Lotti invio", f"{tranches} tranche × {state['batch']} email (pausa {state['pause']}s)", "view_list"),
                        ("Retry", f"{state['retries']} tentativi (delay {state['delay']}s)", "replay"),
                        ("Partenza", mode, "schedule"),
                    ]
                    with ui.column().classes("w-full gap-3"):
                        for label, val, icon in items:
                            with ui.row().classes("items-start gap-2.5"):
                                ui.icon(icon, size="18px").classes("text-slate-400 mt-0.5")
                                with ui.column().classes("gap-0"):
                                    ui.label(label).classes("text-xs text-slate-500")
                                    ui.label(val).classes("text-sm font-semibold text-slate-800 break-words")

                # Colonna Destra: Anteprima grafica del messaggio da spedire
                with ui.column().classes("flex-1 min-w-[340px] gap-2"):
                    ui.label("ANTEPRIMA FINALE DEL MESSAGGIO").classes("text-xs font-bold text-slate-500 tracking-wider")
                    iframe_html(final_rendered_html, height=360)

            wizard.set_finish_label(f"Conferma e avvia {state['count']} invii")

    def on_wizard_enter(step: int) -> None:
        if step == 3:
            update_estimate()
        if step == 4:
            _render_summary()

    wizard.on_enter = on_wizard_enter

    async def on_finish() -> None:
        sched = None
        if state["start_mode"] == "scheduled" and state["scheduled"]:
            try:
                sched = datetime.strptime(state["scheduled"], "%Y-%m-%d %H:%M")
            except ValueError:
                ui.notify("Formato data programmata non valido", type="negative", position="top")
                return
        snap = effective_snapshot()
        try:
            campaign = services.create_campaign(
                name=f"Invio {snap['subject'][:35]}",
                smtp_server_id=state["smtp_id"],
                template_id=state["template_id"],
                template_name=next((t.name for t in services.list_templates() if t.id == state["template_id"]), ""),
                subject=snap["subject"],
                html_body=snap["html"],
                group_id=state["group_id"],
                group_name=next((g["name"] for g in services.list_groups() if g["id"] == state["group_id"]), ""),
                tranche_size=state["batch"],
                pause_seconds=state["pause"],
                max_retries=state["retries"],
                retry_delay_seconds=state["delay"],
                scheduled_at=sched,
            )
        except ValueError as e:
            ui.notify(str(e), type="negative", position="top")
            return
        from app.worker import manager

        manager.start(campaign.id)
        submission["done"] = True
        set_page_dirty(False)
        await ui.run_javascript("window.__newsletterUnsaved = false")
        ui.notify(f"Campagna creata: invio di {campaign.total_count} email in corso", type="positive", position="top")
        ui.navigate.to("/activity")

    wizard.on_finish = on_finish
    initial_state = state.copy()
    ui.timer(0.3, lambda: set_page_dirty(not submission["done"] and state != initial_state))


# ================================================================ SERVER SMTP

@ui.page("/smtp")
def page_smtp() -> None:
    shell("Server SMTP", "/smtp")
    SECURITY = {"tls": "STARTTLS (porta 587)", "ssl": "SSL/TLS (porta 465)", "none": "Nessuna cifratura (25)"}

    with ui.row().classes("w-full items-center justify-between"):
        title_block("Server SMTP", "Configura e testa i profili di invio per le tue newsletter")
        ui.button("Nuovo server SMTP", icon="add", on_click=lambda: open_editor(None)).props("unelevated no-caps").classes("bg-[#0F60F9] text-white shadow-sm")

    cards_grid = ui.element("div").classes("w-full")

    async def run_test(server_id: int) -> None:
        from app.mailer import diagnose_smtp

        client = ui.context.client
        srv = services.get_smtp(server_id)
        if srv is None:
            return

        with ui.dialog() as dialog, ui.card().classes("w-[560px] max-w-full p-6 card") as card:
            dialog_shortcuts(dialog, card, dialog.close)
            with ui.row().classes("items-center justify-between w-full mb-2"):
                with ui.row().classes("items-center gap-2.5"):
                    with ui.element("div").classes("w-9 h-9 rounded-xl bg-blue-50 text-[#0F60F9] flex items-center justify-center"):
                        ui.icon("dns", size="20px")
                    with ui.column().classes("gap-0"):
                        ui.label(f"Diagnostica SMTP: {srv.name}").classes("text-base font-bold text-slate-900")
                        ui.label(f"{srv.host}:{srv.port}").classes("text-xs text-slate-500 font-mono")
                ui.button(icon="close", on_click=dialog.close).props("flat dense round").classes("text-slate-400")

            container = ui.column().classes("w-full gap-2.5 py-3")
            with container:
                with ui.row().classes("items-center justify-center w-full py-8 gap-3"):
                    ui.spinner(size="md").classes("text-[#0F60F9]")
                    ui.label("Esecuzione test diagnostico in corso…").classes("text-sm font-medium text-slate-600")

            dialog.open()
            result = await diagnose_smtp(host=srv.host, port=srv.port, security=srv.security,
                                         username=srv.username, password=srv.password,
                                         sender_email=srv.sender_email)
            services.add_log(None, "success" if result.ok else "error", f"Test SMTP {srv.name}: {result.summary}")
            # Il test può terminare dopo la chiusura del popup o la navigazione
            # a un'altra pagina: conserva il log, ma non toccare elementi rimossi.
            if client.is_deleted or container.is_deleted or dialog.is_deleted or not dialog.value:
                return
            container.clear()
            with container:
                status_color = "bg-emerald-50 text-emerald-800 border-emerald-200" if result.ok else "bg-rose-50 text-rose-800 border-rose-200"
                with ui.row().classes(f"p-3.5 rounded-xl border {status_color} items-center gap-2.5 w-full mb-1"):
                    ui.icon("check_circle" if result.ok else "error", size="22px")
                    ui.label(result.summary).classes("font-semibold text-sm")

                for step in result.steps:
                    with ui.element("div").classes("p-3 bg-slate-50 border border-slate-200/80 rounded-xl flex items-start gap-3 w-full"):
                        ui.icon("check_circle" if step.ok else "cancel", size="18px").classes(
                            "text-emerald-600 mt-0.5" if step.ok else "text-rose-600 mt-0.5"
                        )
                        with ui.column().classes("gap-0.5 flex-1"):
                            with ui.row().classes("justify-between items-center w-full"):
                                ui.label(step.name).classes("font-semibold text-xs text-slate-800")
                                if step.ms:
                                    ui.label(f"{step.ms} ms").classes("text-[11px] font-mono text-slate-400")
                            ui.label(step.detail).classes("text-xs text-slate-600 font-mono break-all")
                            if step.hint and not step.ok:
                                ui.label(f"💡 {step.hint}").classes("text-xs text-amber-700 font-medium mt-1")

                with ui.row().classes("justify-end w-full mt-2"):
                    ui.button("Chiudi", on_click=dialog.close).props("unelevated no-caps").classes("bg-slate-800 text-white")

    def open_editor(server_id: int | None) -> None:
        srv = services.get_smtp(server_id) if server_id else None
        with ui.dialog() as dialog, ui.card().classes("w-[580px] max-w-full p-6 card") as card:
            ui.label("Modifica server SMTP" if srv else "Nuovo server SMTP").classes("text-lg font-bold text-slate-900 mb-2")
            name = ui.input("Nome profilo", value=srv.name if srv else "").classes("w-full").props("outlined dense")
            with ui.row().classes("w-full gap-3"):
                host = ui.input("Host SMTP", value=srv.host if srv else "").classes("flex-1").props("outlined dense")
                port = ui.number("Porta", value=srv.port if srv else 587, min=1, max=65535, format="%.0f").classes("w-28").props("outlined dense")
            security = ui.select(SECURITY, value=srv.security if srv else "tls", label="Sicurezza connessione").classes("w-full").props("outlined dense")
            with ui.row().classes("w-full gap-3"):
                username = ui.input("Nome utente", value=(srv.username or "") if srv else "").classes("flex-1").props("outlined dense")
                password = ui.input("Password", value="", password=True, password_toggle_button=True).classes("flex-1").props("outlined dense")
            if srv:
                password.tooltip("Lascia vuoto per non modificare la password salvata")
            with ui.row().classes("w-full gap-3"):
                sender_email = ui.input("Email mittente", value=srv.sender_email if srv else "").classes("flex-1").props("outlined dense")
                sender_name = ui.input("Nome mittente (opz.)", value=(srv.sender_name or "") if srv else "").classes("flex-1").props("outlined dense")
            reply_to = ui.input("Reply-To (opzionale)", value=(srv.reply_to or "") if srv else "").classes("w-full").props("outlined dense")
            rate = ui.number("Rate limit (email/ora, 0 = illimitato)",
                             value=srv.rate_limit_emails_per_hour if srv and srv.rate_limit_emails_per_hour else 0,
                             min=0, format="%.0f").classes("w-full").props("outlined dense")
            active = ui.switch("Profilo attivo per l'invio", value=srv.active if srv else True).props("dense")

            def save() -> None:
                try:
                    services.save_smtp(
                        server_id, name=name.value, host=host.value, port=int(port.value or 587),
                        security=security.value, username=username.value, password=password.value,
                        sender_email=sender_email.value, sender_name=sender_name.value, reply_to=reply_to.value,
                        rate_limit=int(rate.value or 0), active=active.value,
                    )
                except ValueError as e:
                    ui.notify(str(e), type="warning", position="top")
                    return
                dialog.close()
                ui.notify("Server SMTP salvato", type="positive", position="top")
                render()

            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button("Annulla", on_click=dialog.close).props("flat no-caps").classes("text-slate-600")
                ui.button("Salva profilo", on_click=save).props("unelevated no-caps").classes("bg-[#0F60F9] text-white")
            dialog_shortcuts(dialog, card, save)
            guard_dialog_changes(dialog, [name, host, port, security, username, password, sender_email, sender_name, reply_to, rate, active])
        dialog.open()

    async def duplicate(server_id: int) -> None:
        services.duplicate_smtp(server_id)
        ui.notify("Profilo duplicato (impostato come non attivo)", type="positive", position="top")
        render()

    async def remove(server_id: int) -> None:
        srv = services.get_smtp(server_id)
        if srv and await ask_confirm("Eliminare il profilo SMTP?",
                                     f"«{srv.name}» verrà rimosso. Gli invii già effettuati utilizzano uno snapshot e non subiranno modifiche.",
                                     "Elimina", danger=True):
            services.delete_smtp(server_id)
            ui.notify("Server eliminato", type="info", position="top")
            render()

    def render() -> None:
        cards_grid.clear()
        servers = services.list_smtp()
        with cards_grid:
            if not servers:
                with ui.element("div").classes("card p-12 w-full flex flex-col items-center justify-center text-center gap-3"):
                    ui.icon("dns", size="48px").classes("text-slate-300")
                    ui.label("Nessun server SMTP configurato").classes("text-base font-bold text-slate-700")
                    ui.label("Aggiungi le credenziali del tuo server di posta (es. Gmail, Brevo, Postmark, server aziendale).").classes("text-xs text-slate-500 max-w-md")
                    ui.button("Crea il primo profilo", icon="add", on_click=lambda: open_editor(None)).props("unelevated no-caps").classes("bg-[#0F60F9] text-white mt-2")
                return

            with ui.grid(columns=3).classes("w-full gap-5"):
                for s in servers:
                    with ui.element("div").classes("card card-hover p-6 flex flex-col justify-between gap-4"):
                        with ui.column().classes("gap-3 w-full"):
                            with ui.row().classes("items-start justify-between w-full"):
                                with ui.column().classes("gap-0"):
                                    ui.label(s.name).classes("font-bold text-slate-900 text-base leading-snug")
                                    ui.label(f"{s.host}:{s.port}").classes("text-xs font-mono text-slate-400")
                                ui.switch("", value=s.active, on_change=lambda e, sid=s.id: services.set_smtp_active(sid, e.value)).props("dense").tooltip("Abilita/Disabilita")

                            with ui.row().classes("gap-1.5 items-center flex-wrap"):
                                badge_span(s.security.upper(), {"tls": "green", "ssl": "blue", "none": "gray"}.get(s.security, "gray"))
                                if s.rate_limit_emails_per_hour:
                                    badge_span(f"Limit: {s.rate_limit_emails_per_hour}/h", "amber")

                            with ui.column().classes("gap-1 w-full pt-1"):
                                with ui.row().classes("items-center gap-2 text-xs text-slate-600"):
                                    ui.icon("alternate_email", size="14px").classes("text-slate-400")
                                    ui.label(f"{s.sender_name + ' <' if s.sender_name else ''}{s.sender_email}{'>' if s.sender_name else ''}").classes("truncate")
                                with ui.row().classes("items-center gap-2 text-xs text-slate-600"):
                                    ui.icon("key", size="14px").classes("text-slate-400")
                                    ui.label("Password salvata" if s.password else "Nessuna autenticazione").classes("text-slate-500")

                        with ui.element("div").classes("pt-3 border-t border-slate-100 flex items-center justify-between w-full"):
                            ui.button("Diagnostica", icon="wifi_tethering", on_click=lambda sid=s.id: run_test(sid)).props("flat dense no-caps").classes("text-[#0F60F9] text-xs")
                            with ui.row().classes("items-center gap-1"):
                                ui.button(icon="edit", on_click=lambda sid=s.id: open_editor(sid)).props("flat dense round").classes("text-slate-500").tooltip("Modifica")
                                ui.button(icon="content_copy", on_click=lambda sid=s.id: duplicate(sid)).props("flat dense round").classes("text-slate-500").tooltip("Duplica")
                                ui.button(icon="delete", on_click=lambda sid=s.id: remove(sid)).props("flat dense round").classes("text-rose-500").tooltip("Elimina")

    render()


# ================================================================ GRUPPI E DESTINATARI

@ui.page("/groups")
def page_groups() -> None:
    shell("Destinatari", "/groups")
    state = {"group_id": None, "search": "", "page": 1}
    PER_PAGE = 15

    with ui.row().classes("w-full items-center justify-between"):
        title_block("Destinatari e Gruppi", "Organizza i tuoi destinatari in liste di distribuzione")
        with ui.row().classes("gap-2 items-center"):
            ui.button("Incolla CSV", icon="content_paste", on_click=lambda: open_paste_csv()).props("outline no-caps").classes("text-slate-700 bg-white")
            ui.button("Nuovo destinatario", icon="person_add", on_click=lambda: open_contact(None)).props("unelevated no-caps").classes("bg-[#0F60F9] text-white")

    with ui.row().classes("w-full gap-6 items-start"):
        # Colonna Sinistra: Gruppi
        with ui.element("div").classes("card p-4 w-72 shrink-0 flex flex-col gap-3"):
            with ui.row().classes("items-center justify-between w-full px-1"):
                ui.label("GRUPPI").classes("text-xs font-bold text-slate-500 tracking-wider")
                ui.button(icon="add", on_click=lambda: new_group()).props("flat dense round").classes("text-[#0F60F9]").tooltip("Nuovo gruppo")
            groups_list = ui.column().classes("w-full gap-1")

        # Colonna Destra: Tabella destinatari
        with ui.element("div").classes("card p-6 flex-1 min-w-[500px] flex flex-col gap-4"):
            toolbar = ui.row().classes("w-full items-center justify-between gap-3 flex-wrap")
            table_container = ui.column().classes("w-full")

    def render_groups() -> None:
        groups_list.clear()
        total_contacts = services.dashboard_stats()["contacts"]
        with groups_list:
            is_all = (state["group_id"] is None)
            with ui.row().classes(
                f"w-full items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all "
                f"{'bg-blue-50/80 text-[#0F60F9] font-semibold' if is_all else 'hover:bg-slate-50 text-slate-700'}"
            ).on("click", lambda: select_group(None)):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("people", size="18px").classes("text-[#0F60F9]" if is_all else "text-slate-400")
                    ui.label("Tutti i destinatari").classes("text-xs")
                ui.label(str(total_contacts)).classes("badge badge-gray text-[10px]")

            for g in services.list_groups():
                is_curr = (state["group_id"] == g["id"])
                with ui.row().classes(
                    f"w-full items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-all "
                    f"{'bg-blue-50/80 text-[#0F60F9] font-semibold' if is_curr else 'hover:bg-slate-50 text-slate-700'}"
                ).on("click", lambda gid=g["id"]: select_group(gid)):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("folder", size="18px").classes("text-[#0F60F9]" if is_curr else "text-slate-400")
                        ui.label(g["name"]).classes("text-xs truncate max-w-[140px]")
                    ui.label(str(g["total"])).classes(f"badge {'badge-blue' if is_curr else 'badge-gray'} text-[10px]")

            if state["group_id"] is not None:
                ui.separator().classes("my-1")
                with ui.row().classes("w-full justify-between items-center px-1"):
                    ui.button("Elimina gruppo", icon="delete", on_click=delete_group).props("flat dense no-caps").classes("text-rose-600 text-xs")

    def select_group(group_id: int | None) -> None:
        state.update(group_id=group_id, page=1)
        render_groups()
        render_contacts()

    async def new_group() -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[380px] p-6 card") as card:
            ui.label("Nuovo gruppo di destinatari").classes("text-base font-bold text-slate-900 mb-2")
            name = ui.input("Nome del gruppo", validation=lambda v: bool((v or "").strip()) or "Inserisci un nome").classes("w-full").props("outlined dense")

            def create() -> None:
                try:
                    services.create_group(name.value)
                except ValueError as e:
                    ui.notify(str(e), type="warning", position="top")
                    return
                dialog.close()
                ui.notify("Gruppo creato con successo", type="positive", position="top")
                render_groups()

            with ui.row().classes("justify-end w-full gap-2 mt-2"):
                ui.button("Annulla", on_click=dialog.close).props("flat no-caps").classes("text-slate-600")
                ui.button("Crea gruppo", on_click=create).props("unelevated no-caps").classes("bg-[#0F60F9] text-white")
            dialog_shortcuts(dialog, card, create)
            guard_dialog_changes(dialog, [name])
        dialog.open()

    async def delete_group() -> None:
        if state["group_id"] is None:
            return
        g = state["group_id"]
        if await ask_confirm("Eliminare questo gruppo?",
                             "Il gruppo verrà eliminato. I destinatari rimarranno comunque memorizzati nell'elenco generale.",
                             "Elimina", danger=True):
            services.delete_group(g)
            state["group_id"] = None
            render_groups()
            render_contacts()

    def render_contacts() -> None:
        toolbar.clear()
        gname = next((g["name"] for g in services.list_groups() if g["id"] == state["group_id"]), "Tutti i destinatari")
        with toolbar:
            with ui.column().classes("gap-0"):
                ui.label(gname).classes("text-base font-bold text-slate-900")
                ui.label("Gestisci e filtra i destinatari registrati").classes("text-xs text-slate-500")

            with ui.row().classes("items-center gap-2"):
                ui.input(placeholder="Cerca destinatario…", value=state["search"],
                         on_change=lambda e: (state.update(search=e.value or "", page=1), render_table())).props("outlined dense clearable").classes("w-64")
                ui.button(icon="file_download", on_click=lambda: ui.download(
                    services.export_contacts_csv().encode("utf-8"), filename="destinatari.csv"
                )).props("flat dense round").classes("text-slate-600").tooltip("Esporta CSV destinatari")

        render_table()

    def render_table() -> None:
        table_container.clear()
        rows, total = services.list_contacts(group_id=state["group_id"], search=state["search"],
                                             page=state["page"], per_page=PER_PAGE)
        columns = [
            {"name": "email", "label": "Email", "field": "email", "align": "left"},
            {"name": "first_name", "label": "Nome", "field": "first_name", "align": "left"},
            {"name": "last_name", "label": "Cognome", "field": "last_name", "align": "left"},
            {"name": "company", "label": "Azienda", "field": "company", "align": "left"},
            {"name": "actions", "label": "", "field": "actions", "align": "right"},
        ]
        table_rows = [dict(r, id=r["id"]) for r in rows]

        with table_container:
            if not table_rows and not state["search"]:
                with ui.element("div").classes("p-8 w-full flex flex-col items-center justify-center text-center gap-2"):
                    ui.icon("contacts", size="36px").classes("text-slate-300")
                    ui.label("Nessun destinatario in questa lista").classes("text-sm font-semibold text-slate-600")
                    ui.label("Puoi importare velocemente una lista incollando un file CSV.").classes("text-xs text-slate-400")
                return

            table = ui.table(columns=columns, rows=table_rows, row_key="id").classes("w-full").props("flat bordered dense hide-pagination")
            table.add_slot("body-cell-email", """<q-td :props="props" class="font-medium text-slate-900">{{ props.row.email }}</q-td>""")
            table.add_slot("body-cell-actions", """<q-td :props="props" class="text-right">
                <q-btn flat dense round icon="edit" size="sm" class="text-slate-500" @click="$parent.$emit('edit', props.row)" />
                <q-btn flat dense round icon="delete" size="sm" class="text-rose-500" @click="$parent.$emit('remove', props.row)" />
            </q-td>""")
            table.on("edit", lambda e: open_contact(int(e.args["id"])))
            table.on("remove", lambda e: remove_contact(int(e.args["id"])))

            if total > PER_PAGE:
                pages = max(1, -(-total // PER_PAGE))
                with ui.row().classes("items-center justify-between w-full pt-3 px-1"):
                    ui.label(f"Pagina {state['page']} di {pages} · {total} destinatari totali").classes("text-xs text-slate-500")
                    with ui.row().classes("items-center gap-1"):
                        def go(p: int) -> None:
                            state["page"] = max(1, min(pages, p))
                            render_table()
                        ui.button(icon="chevron_left", on_click=lambda: go(state["page"] - 1)).props("flat dense round").classes("text-slate-600")
                        ui.button(icon="chevron_right", on_click=lambda: go(state["page"] + 1)).props("flat dense round").classes("text-slate-600")

    def open_contact(contact_id: int | None) -> None:
        rows, _ = services.list_contacts(per_page=1_000_000)
        contact = next((r for r in rows if r["id"] == contact_id), None)
        groups = services.list_groups()
        selected: set[int] = set()
        if contact and contact["groups"]:
            name_to_id = {g["name"]: g["id"] for g in groups}
            selected = {name_to_id[n] for n in contact["groups"].split(", ") if n in name_to_id}
        elif state["group_id"]:
            selected.add(state["group_id"])

        with ui.dialog() as dialog, ui.card().classes("w-[480px] p-6 card") as card:
            ui.label("Modifica destinatario" if contact else "Nuovo destinatario").classes("text-base font-bold text-slate-900 mb-2")
            email = ui.input("Indirizzo email", value=contact["email"] if contact else "").classes("w-full").props("outlined dense")
            with ui.row().classes("w-full gap-3"):
                first = ui.input("Nome", value=contact["first_name"] if contact else "").classes("flex-1").props("outlined dense")
                last = ui.input("Cognome", value=contact["last_name"] if contact else "").classes("flex-1").props("outlined dense")
            company = ui.input("Azienda", value=contact["company"] if contact else "").classes("w-full").props("outlined dense")

            ui.label("Gruppi · almeno uno obbligatorio").classes("text-xs font-semibold text-slate-500 mt-1")
            group_checkboxes = []
            with ui.row().classes("w-full gap-2 flex-wrap max-h-36 overflow-y-auto p-2 bg-slate-50 border border-slate-200/80 rounded-xl"):
                if not groups:
                    ui.label("Non ci sono ancora gruppi. Crea il primo qui sotto.").classes("text-xs text-slate-500")
                for g in groups:
                    group_checkboxes.append(ui.checkbox(g["name"], value=g["id"] in selected,
                                on_change=lambda e, gid=g["id"]: selected.add(gid) if e.value else selected.discard(gid)).props("dense"))
            create_group = ui.checkbox("Crea un nuovo gruppo", value=not groups).props("dense")
            group_name = ui.input("Nome del nuovo gruppo").classes("w-full").props("outlined dense").bind_visibility_from(create_group, "value")
            ui.label("Il nuovo gruppo sarà creato e assegnato quando salvi il destinatario.").classes("text-xs text-slate-500").bind_visibility_from(create_group, "value")

            def save() -> None:
                try:
                    new_group_name = (group_name.value or "").strip() if create_group.value else ""
                    if create_group.value and not new_group_name:
                        raise ValueError("Inserisci il nome del nuovo gruppo")
                    services.save_contact(contact_id, email=email.value, first_name=first.value, last_name=last.value,
                                           company=company.value, tags="", group_ids=sorted(selected),
                                           new_group_name=new_group_name)
                except ValueError as e:
                    ui.notify(str(e), type="warning", position="top")
                    return
                dialog.close()
                ui.notify("Destinatario salvato", type="positive", position="top")
                render_groups()
                render_contacts()

            with ui.row().classes("justify-end w-full gap-2 mt-3"):
                ui.button("Annulla", on_click=dialog.close).props("flat no-caps").classes("text-slate-600")
                ui.button("Salva", on_click=save).props("unelevated no-caps").classes("bg-[#0F60F9] text-white")
            dialog_shortcuts(dialog, card, save)
            guard_dialog_changes(dialog, [email, first, last, company, *group_checkboxes, create_group, group_name])
        dialog.open()

    async def remove_contact(contact_id: int) -> None:
        rows, _ = services.list_contacts(per_page=1_000_000)
        contact = next((r for r in rows if r["id"] == contact_id), None)
        if contact and await ask_confirm("Eliminare il destinatario?",
                                         f"{contact['email']} verrà eliminato definitivamente dall'elenco.", "Elimina", danger=True):
            services.delete_contact(contact_id)
            render_groups()
            render_contacts()

    def open_paste_csv() -> None:
        groups = services.list_groups()
        with ui.dialog() as dialog, ui.card().classes("w-[720px] max-w-full p-6 card") as card:
            ui.label("Incolla lista destinatari (CSV)").classes("text-base font-bold text-slate-900")
            ui.label("Incolla le righe da Excel o file di testo. Formato: email; nome; cognome; azienda").classes("text-xs text-slate-500 -mt-2")
            area = (ui.textarea(placeholder="mario.rossi@example.com; Mario; Rossi; Acme Srl\nlaura.bianchi@example.com; Laura; Bianchi; Beta Spa")
                    .classes("w-full mono csv-paste-field").props("outlined"))
            ui.label("Invio: nuova riga · Ctrl/Cmd+Invio: importa · Esc: chiudi").classes("text-xs text-slate-500")

            with ui.row().classes("w-full gap-3 items-center"):
                group_sel = ui.select({**{g["id"]: g["name"] for g in groups}, -1: "➕ Crea un nuovo gruppo…"},
                                      value=state["group_id"] if state["group_id"] else (groups[0]["id"] if groups else -1),
                                      label="Aggiungi al gruppo").classes("flex-1").props("outlined dense")
                new_name = ui.input("Nome nuovo gruppo").classes("flex-1").props("outlined dense").bind_visibility_from(group_sel, "value", backward=lambda v: v == -1)

            def do_import() -> None:
                try:
                    result = services.import_pasted_csv(area.value,
                                                       group_sel.value if group_sel.value != -1 else None,
                                                       new_name.value if group_sel.value == -1 else "")
                except ValueError as e:
                    ui.notify(str(e), type="warning", position="top")
                    return
                dialog.close()
                ui.notify(f"Importati {result['created']} destinatari ({result['skipped']} righe saltate o duplicate)"
                          + (f" nel gruppo «{result['group']}»" if result["group"] else ""),
                          type="positive", position="top", close_btn="OK")
                render_groups()
                render_contacts()

            with ui.row().classes("justify-end w-full gap-2 mt-3"):
                ui.button("Annulla", on_click=dialog.close).props("flat no-caps").classes("text-slate-600")
                ui.button("Importa destinatari", icon="upload", on_click=do_import).props("unelevated no-caps").classes("bg-[#0F60F9] text-white")
            dialog_shortcuts(dialog, card, do_import)
            guard_dialog_changes(dialog, [area, group_sel, new_name])
        dialog.open()

    render_groups()
    render_contacts()


# ================================================================ TEMPLATE

TEMPLATES_CSS = """
<style>
.templates-toolbar { padding: 16px 20px; }
.templates-workspace { width: 100%; }
.templates-editor, .templates-preview { min-width: 0; width: 100%; padding: 20px; gap: 16px; }
.templates-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; width: 100%; }
.templates-editor textarea { font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.7; min-height: 520px !important; resize: vertical; white-space: pre; overflow-wrap: normal; tab-size: 2; }
.q-dialog__inner > .templates-preview { width: 1320px; max-width: calc(100vw - 48px); max-height: calc(100dvh - 48px); overflow-y: auto; }
.templates-stage { width: 100%; min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.templates-stage.compare { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.email-device { width: 100%; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.email-device-label { font-size: 12px; font-weight: 600; color: #64748b; }
.email-viewport { width: 100%; overflow: hidden; border-radius: 10px; background: white; border: 1px solid #cbd5e1; box-shadow: 0 4px 16px #0f172a0a; }
.email-device.desktop .email-viewport { max-width: 800px; }
.email-device.mobile .email-viewport { max-width: 389px; border: 7px solid #1e293b; border-radius: 26px; }
.email-viewport iframe { display: block; border: 0; background: white; transform-origin: top left; }
.template-status { font-size: 12px; white-space: normal; overflow-wrap: anywhere; }
@media (max-width: 1100px) {
  .templates-stage.compare { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 800px) {
  .templates-fields { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .templates-editor textarea { min-height: 380px !important; }
  .q-dialog__inner > .templates-preview { max-width: calc(100vw - 24px); max-height: calc(100dvh - 24px); }
  .templates-toolbar { padding: 16px; }
  .templates-editor, .templates-preview { padding: 16px; }
  .templates-stage { padding: 12px; }
  .template-picker { width: 100% !important; }
  .nicegui-content:has(.templates-workspace) { padding-left: 12px !important; padding-right: 12px !important; }
  body:has(.templates-workspace) .q-header { height: auto !important; position: relative; }
  body:has(.templates-workspace) .q-header > div { padding: 12px; gap: 12px; }
  body:has(.templates-workspace) .q-header .header-nav-btn { padding: 6px 8px; }
  body:has(.templates-workspace) .q-page-container { padding-top: 0 !important; }
}
</style>
"""


@ui.page("/templates")
def page_templates() -> None:
    shell("Template email", "/templates")
    ui.add_head_html(TEMPLATES_CSS)
    state = {
        "template_id": None,
        "dirty": False,
        "device": "desktop",
        "loading": False,
        "saved": ("", "", ""),
    }

    def values() -> tuple[str, str, str]:
        return (name_input.value or "", subject_input.value or "", html_area.value or "")

    def has_changes() -> bool:
        return values() != state["saved"]

    def update_save_status() -> None:
        changed = has_changes()
        set_page_dirty(changed)
        save_status.set_text("Template non ancora salvato" if state["template_id"] is None else "Modifiche non salvate" if changed else "Tutte le modifiche salvate")
        save_status.classes(replace=f"text-xs {'text-amber-700' if changed else 'text-slate-500'}")
        save_button.set_enabled(changed or state["template_id"] is None)

    async def can_discard() -> bool:
        return not has_changes() or await ask_confirm(
            "Modifiche non salvate", "Se continui, le modifiche a questo template andranno perse.", "Scarta modifiche",
        )

    def current_context() -> dict:
        if contact_select.value in (None, -1):
            return dict(templating.SAMPLE_CONTEXT)
        rows, _ = services.list_contacts(per_page=1_000_000)
        contact = next((r for r in rows if r["id"] == int(contact_select.value)), None)
        return templating.context_for(contact) if contact else dict(templating.SAMPLE_CONTEXT)

    def refresh_preview() -> None:
        if not state["dirty"] or not preview_dialog.value:
            return
        state["dirty"] = False
        try:
            subj = templating.render(subject_input.value or "", current_context())
            html = templating.render(html_area.value or "", current_context())
        except templating.TemplateError as e:
            status_badge.classes(replace="template-status text-rose-600")
            status_badge.set_text(f"Anteprima non disponibile: {e}")
            preview_subject.set_text("Oggetto non disponibile")
            preview_container.clear()
            with preview_container:
                with ui.column().classes("w-full items-center p-8 gap-3"):
                    ui.icon("code_off", size="32px").classes("text-rose-400")
                    ui.label("Correggi il template per visualizzare l’email.").classes("text-sm text-slate-600 text-center")
            return
        unknown = sorted(set(templating.unknown_variables(html_area.value or "")) | set(templating.unknown_variables(subject_input.value or "")))
        if unknown:
            status_badge.classes(replace="template-status text-amber-700")
            status_badge.set_text(f"Variabili non standard: {', '.join(unknown)}")
        else:
            status_badge.classes(replace="template-status text-emerald-700")
            status_badge.set_text("✓ Template valido · Anteprima aggiornata")

        preview_subject.set_text(subj or "(Nessun oggetto)")
        preview_container.classes("compare" if state["device"] == "both" else "", remove="compare" if state["device"] != "both" else "")
        preview_container.clear()
        with preview_container:
            devices = ("desktop", "mobile") if state["device"] == "both" else (state["device"],)
            # Il viewport resta reale anche quando l'anteprima viene ridotta per entrare nel pannello.
            document = '<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>' + html + '</body></html>'
            escaped = html_module.escape(document, quote=True)
            for device in devices:
                width = 375 if device == "mobile" else 800
                label = "Mobile · 375 px" if device == "mobile" else "Desktop · 800 px"
                ui.html(
                    f'<div class="email-device {device}"><div class="email-device-label">{label}</div>'
                    f'<div class="email-viewport" data-width="{width}">'
                    f'<iframe title="Anteprima email {device}" sandbox="" srcdoc="{escaped}" '
                    f'style="width:{width}px;height:600px"></iframe></div></div>',
                    sanitize=False,
                ).classes("w-full min-w-0")
        ui.run_javascript('''
            document.querySelectorAll('.email-viewport').forEach(view => {
                const fit = () => {
                    const frame = view.querySelector('iframe');
                    const scale = Math.min(1, view.clientWidth / Number(view.dataset.width));
                    frame.style.transform = `scale(${scale})`;
                    view.style.height = `${600 * scale}px`;
                };
                const observer = new ResizeObserver(() => {
                    if (!view.isConnected) observer.disconnect(); else fit();
                });
                observer.observe(view);
                fit();
            });
        ''')

    def mark_dirty() -> None:
        state["dirty"] = True

    def open_preview() -> None:
        preview_dialog.open()
        mark_dirty()
        refresh_preview()

    def load_template() -> None:
        state["loading"] = True
        template = services.get_template(state["template_id"]) if state["template_id"] else None
        name_input.set_value(template.name if template else "Nuovo template")
        subject_input.set_value(template.subject if template else "Oggetto della newsletter")
        html_area.set_value(template.html_body if template else DEFAULT_HTML)
        state["saved"] = values()
        if state["template_id"] is not None and template_select.value != state["template_id"]:
            template_select.set_value(state["template_id"])

        rows, _ = services.list_contacts(per_page=50)
        opts = {-1: "Dati di esempio", **{r["id"]: f'{r["email"]} ({r["first_name"] or "—"})' for r in rows}}
        contact_select.set_options(opts)
        contact_select.set_value(-1)
        duplicate_button.set_enabled(template is not None)
        delete_button.set_enabled(template is not None)
        state["loading"] = False
        update_save_status()
        mark_dirty()
        refresh_preview()

    def load_list(select_id: int | None = None) -> None:
        templates = services.list_templates()
        opts = {t.id: t.name for t in templates}
        template_count.set_text(f"{len(templates)} template salvati" if templates else "Nessun template: crea il primo qui sotto")
        template_select.set_options(opts)

        target_id = None
        if select_id is not None and select_id in opts:
            target_id = select_id
        elif state["template_id"] is not None and state["template_id"] in opts:
            target_id = state["template_id"]
        elif templates:
            target_id = templates[0].id

        state["template_id"] = target_id
        template_select.set_value(target_id)
        load_template()

    def save() -> None:
        for label, text in (("Oggetto", subject_input.value or ""), ("Corpo HTML", html_area.value)):
            error = templating.check_syntax(text)
            if error:
                ui.notify(f"{label}: {error}", type="warning", position="top")
                return
        template = services.save_template(
            state["template_id"],
            name=name_input.value.strip() or "Senza nome",
            subject=subject_input.value,
            html_body=html_area.value,
        )
        state["template_id"] = template.id
        ui.notify("Template salvato con successo", type="positive", position="top")
        load_list(template.id)

    async def create_new() -> None:
        if not await can_discard():
            return
        template = services.save_template(None, name="Nuovo template", subject="Oggetto della newsletter", html_body=DEFAULT_HTML)
        load_list(template.id)

    async def duplicate() -> None:
        if state["template_id"] and await can_discard():
            copy = services.duplicate_template(state["template_id"])
            ui.notify("Template duplicato", type="positive", position="top")
            load_list(copy.id)

    async def remove() -> None:
        template = services.get_template(state["template_id"]) if state["template_id"] else None
        if template and await ask_confirm("Eliminare il template?",
                                          f"«{template.name}» verrà eliminato. Gli invii già effettuati non subiranno modifiche.",
                                          "Elimina", danger=True):
            services.delete_template(template.id)
            state["template_id"] = None
            load_list(None)

    with ui.row().classes("w-full items-center justify-between flex-wrap gap-4"):
        with ui.column().classes("gap-0"):
            ui.label("Template email").classes("page-title")
            ui.label("Scegli un template, modifica il contenuto e controlla il risultato su ogni schermo.").classes("page-subtitle")
        ui.button("Nuovo template", icon="add", on_click=create_new).props("outline no-caps").classes("bg-white text-[#0F60F9]")

    with ui.row().classes("card templates-toolbar w-full items-center justify-between gap-4"):
        with ui.row().classes("items-center gap-3 flex-wrap template-picker"):
            template_select = ui.select({}, label="Template da modificare").classes("w-64 template-picker").props("outlined dense options-dense")
            template_count = ui.label("").classes("text-xs text-slate-500")
        with ui.row().classes("items-center gap-2"):
            duplicate_button = ui.button("Duplica", icon="content_copy", on_click=duplicate).props("flat no-caps").classes("text-slate-600")
            delete_button = ui.button("Elimina", icon="delete_outline", on_click=remove).props("flat no-caps").classes("text-rose-600")

    with ui.element("div").classes("templates-workspace"):
        with ui.column().classes("card templates-editor"):
            with ui.row().classes("w-full items-center justify-between gap-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("edit_note", size="22px").classes("text-[#0F60F9]")
                    ui.label("Contenuto dell’email").classes("text-base font-bold text-slate-900")
                ui.button("Apri anteprima", icon="preview", on_click=open_preview).props("outline no-caps color=primary")
            with ui.element("div").classes("templates-fields"):
                name_input = ui.input("Nome del template").classes("w-full").props('outlined dense hint="Solo per te: non appare nell’email"')
                subject_input = ui.input("Oggetto dell’email").classes("w-full").props("outlined dense")
            html_area = ui.textarea("Codice HTML", placeholder="Incolla qui il codice della tua email").classes("w-full").props("outlined")
            with ui.expansion("Personalizza con i dati del destinatario", icon="data_object").classes("w-full text-xs text-slate-600"):
                ui.label("Copia una variabile e incollala nell’oggetto o nel codice HTML.").classes("text-xs text-slate-500 mb-2")
                variable_chips()
            ui.separator()
            with ui.row().classes("w-full items-center justify-between gap-2"):
                save_status = ui.label("").classes("text-xs text-slate-500")
                with ui.row().classes("items-center gap-2"):
                    ui.button("Anteprima", icon="preview", on_click=open_preview).props("flat no-caps color=primary")
                    save_button = ui.button("Salva template", icon="save", on_click=save).props("unelevated no-caps color=primary")

    with ui.dialog() as preview_dialog:
        with ui.column().classes("card templates-preview") as preview_card:
            dialog_shortcuts(preview_dialog, preview_card, preview_dialog.close)
            with ui.row().classes("w-full items-center justify-between gap-3"):
                with ui.column().classes("gap-1"):
                    ui.label("Anteprima email").classes("text-base font-bold text-slate-900")
                    ui.label("Include le modifiche non salvate. Chiudi per tornare al codice.").classes("text-xs text-slate-500")
                with ui.row().classes("items-center gap-3"):
                    ui.toggle(
                        {"desktop": "Desktop", "mobile": "Mobile", "both": "Confronta"}, value="desktop",
                        on_change=lambda e: (state.update(device=e.value), mark_dirty(), refresh_preview()),
                    ).props("dense unelevated no-caps toggle-color=primary").classes("bg-slate-100")
                    ui.button(icon="close", on_click=preview_dialog.close).props('flat round dense aria-label="Chiudi anteprima"').classes("text-slate-500").tooltip("Chiudi anteprima (Esc)")
            contact_select = ui.select({-1: "Dati di esempio"}, value=-1, label="Dati del destinatario per l’anteprima").classes("w-full").props("outlined dense")
            with ui.column().classes("w-full gap-1 bg-slate-50 rounded-lg p-3 border border-slate-200"):
                ui.label("OGGETTO").classes("text-[10px] font-bold tracking-wider text-slate-400")
                preview_subject = ui.label("").classes("text-sm font-semibold text-slate-800 break-words w-full")
            preview_container = ui.element("div").classes("templates-stage")
            status_badge = ui.label("").classes("template-status text-slate-500")
            ui.label("Simulazione nel browser: l’aspetto può variare in Outlook, Gmail e altri client email.").classes("text-[11px] text-slate-400")

    async def on_select_change(e):
        if state["loading"]:
            return
        if e.value is not None and e.value != state["template_id"]:
            if not await can_discard():
                template_select.set_value(state["template_id"])
                return
            state["template_id"] = e.value
            load_template()

    def on_content_change() -> None:
        if not state["loading"]:
            update_save_status()
            mark_dirty()

    template_select.on_value_change(on_select_change)
    contact_select.on_value_change(lambda e: mark_dirty())
    name_input.on_value_change(lambda e: on_content_change())
    subject_input.on_value_change(lambda e: on_content_change())
    html_area.on_value_change(lambda e: on_content_change())
    ui.timer(0.5, refresh_preview)
    load_list(None)


DEFAULT_HTML = """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; color: #1e293b; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
  <h2 style="color: #0F60F9; margin-top: 0;">Ciao {{ first_name }}!</h2>
  <p style="font-size: 15px; line-height: 1.6; color: #475569;">
    Questa è la tua nuova email inviata comodamente con <strong>ilPostino</strong>.
  </p>
  <p style="font-size: 15px; line-height: 1.6; color: #475569;">
    Puoi inserire campi personalizzati come la tua azienda: <em>{{ company }}</em>.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
  <p style="font-size: 12px; color: #94a3b8; margin-bottom: 0;">
    Ricevi questa comunicazione perché sei registrato nella nostra rubrica.
  </p>
</div>"""


# ================================================================ ATTIVITÀ E LOG

@ui.page("/activity")
def page_activity() -> None:
    shell("Attività e log", "/activity")
    state = {"selected": None, "filter": "", "page": 1, "last_log_id": 0, "refs": {}, "hash": None}
    PER_PAGE = 25

    with ui.row().classes("w-full items-center justify-between"):
        title_block("Monitoraggio Invii", "Controlla lo stato delle campagne in tempo reale e consulta i log di consegna")

    container = ui.column().classes("w-full gap-4")

    def done_of(counts: dict) -> int:
        return counts["sent"] + counts["failed_temp"] + counts["failed_perm"] + counts["skipped"] + counts["cancelled"]

    def render_controls(box, campaign) -> None:
        box.clear()
        with box:
            if campaign.status == "running":
                ui.button("Interrompi", icon="stop", on_click=lambda cid=campaign.id: interrupt(cid)).props(
                    "unelevated no-caps dense"
                ).classes("bg-rose-600 text-white text-xs px-3")
            elif campaign.status == "paused":
                ui.label(f"⚠ {campaign.auto_pause_reason or 'In pausa'}").classes("text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-1 rounded-md border border-amber-200")

    async def interrupt(campaign_id: int) -> None:
        counts = services.status_counts(campaign_id)
        if await ask_confirm("Interrompere l'invio?",
                             f"Le {counts['pending'] + counts['processing']} email ancora in coda verranno annullate.",
                             "Interrompi invio", danger=True):
            from app.worker import manager

            manager.cancel(campaign_id)
            ui.notify("Interruzione invio in corso…", type="info", position="top")
            render_all()

    def render_detail(c) -> None:
        with ui.element("div").classes("w-full mt-3 pt-4 border-t border-slate-200/90 flex flex-col gap-4"):
            stats = ui.row().classes("gap-2 flex-wrap items-center")
            render_stats(stats, c.id)

            with ui.row().classes("items-center justify-between w-full flex-wrap gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.label("Destinatari della campagna").classes("text-xs font-bold text-slate-500 uppercase tracking-wider")
                    ui.select({"": "Tutti gli stati"} | {k: v[0] for k, v in ITEM_LABELS.items()},
                              value=state["filter"], on_change=lambda e: set_filter(e.value)).props("outlined dense").classes("w-48")
                ui.button("Esporta destinatari CSV", icon="download", on_click=lambda cid=c.id: ui.download(
                    services.export_items_csv(cid).encode("utf-8"), filename=f"invio_{cid}_destinatari.csv"
                )).props("outline no-caps dense").classes("text-slate-700 text-xs bg-white")

            items_box = ui.column().classes("w-full")
            pager_box = ui.row().classes("items-center justify-between w-full pt-1 px-1")

            def set_filter(value: str) -> None:
                state.update(filter=value or "", page=1)
                render_items()

            def render_items() -> None:
                rows, total = services.campaign_items(c.id, status=state["filter"], page=state["page"], per_page=PER_PAGE)
                columns = [
                    {"name": "email", "label": "Email destinatario", "field": "email", "align": "left"},
                    {"name": "name", "label": "Nome", "field": "name", "align": "left"},
                    {"name": "status", "label": "Esito", "field": "status_label", "align": "left"},
                    {"name": "attempts", "label": "Tentativi", "field": "attempts", "align": "center"},
                    {"name": "error", "label": "Errore riscontrato", "field": "last_error", "align": "left"},
                    {"name": "sent_at", "label": "Data invio", "field": "sent_at", "align": "left"},
                ]
                table_rows = [{**r, "name": f"{r['first_name']} {r['last_name']}".strip(),
                               "status_label": ITEM_LABELS.get(r["status"], (r["status"], "gray"))[0],
                               "status_color": ITEM_LABELS.get(r["status"], ("", "gray"))[1]} for r in rows]
                items_box.clear()
                with items_box:
                    table = ui.table(columns=columns, rows=table_rows, row_key="email").classes("w-full").props("flat bordered dense hide-pagination")
                    table.add_slot("body-cell-status", """<q-td :props="props">
                        <span class="badge" :class="'badge-' + props.row.status_color">{{ props.row.status_label }}</span>
                    </q-td>""")
                    table.add_slot("body-cell-error", """<q-td :props="props" class="text-xs text-rose-600 font-mono max-w-[200px] truncate">
                        {{ props.row.last_error || '—' }}
                    </q-td>""")

                pager_box.clear()
                with pager_box:
                    pages = max(1, -(-total // PER_PAGE))
                    ui.label(f"Pagina {state['page']} di {pages} · {total} destinatari").classes("text-xs text-slate-500")
                    if pages > 1:
                        with ui.row().classes("items-center gap-1"):
                            def go(p: int) -> None:
                                state["page"] = max(1, min(pages, p))
                                render_items()
                            ui.button(icon="chevron_left", on_click=lambda: go(state["page"] - 1)).props("flat dense round").classes("text-slate-600")
                            ui.button(icon="chevron_right", on_click=lambda: go(state["page"] + 1)).props("flat dense round").classes("text-slate-600")

            render_items()
            ui.label("LOG DI CONSEGNA IN TEMPO REALE").classes("text-xs font-bold text-slate-500 tracking-wider mt-2")
            log = ui.log(max_lines=1000).classes("w-full h-52 text-xs")
            state["refs"][c.id].update(log=log, stats=stats, render_items=render_items)

    def render_stats(stats, campaign_id: int) -> None:
        counts = services.status_counts(campaign_id)
        stats.clear()
        with stats:
            for key in ("sent", "failed_perm", "failed_temp", "pending", "processing", "cancelled"):
                label, color = ITEM_LABELS[key]
                badge_span(f"{label}: {counts[key]}", color)

    def toggle_detail(campaign_id: int) -> None:
        state.update(selected=None if state["selected"] == campaign_id else campaign_id, page=1, filter="", last_log_id=0)
        render_all()

    def render_all() -> None:
        container.clear()
        state["refs"] = {}
        campaigns = services.list_campaigns()
        with container:
            if not campaigns:
                with ui.element("div").classes("card p-12 w-full flex flex-col items-center justify-center text-center gap-3"):
                    ui.icon("query_stats", size="48px").classes("text-slate-300")
                    ui.label("Nessuna campagna avviata").classes("text-base font-bold text-slate-700")
                    ui.label("Quando avvierai il tuo primo invio potrai seguire l'avanzamento minuto per minuto qui.").classes("text-xs text-slate-500 max-w-sm")
                    ui.button("Crea un nuovo invio", icon="rocket_launch", on_click=lambda: ui.navigate.to("/")).props("unelevated no-caps").classes("bg-[#0F60F9] text-white mt-2")
                return

            for c in campaigns:
                counts = services.status_counts(c.id)
                label, color = CAMPAIGN_LABELS.get(c.status, (c.status, "gray"))
                total = max(1, c.total_count)
                done = done_of(counts)
                pct = int(min(done / total, 1.0) * 100)

                with ui.element("div").classes("card p-6 w-full flex flex-col gap-3"):
                    with ui.row().classes("items-center justify-between flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-3"):
                            ui.label(f"#{c.id}").classes("text-xs font-mono font-bold text-slate-400 bg-slate-100 px-2 py-0.5 rounded")
                            ui.label(c.name).classes("font-bold text-slate-900 text-base")
                            badge_box = ui.element("span")
                            with badge_box:
                                badge_span(label, color)

                        with ui.row().classes("items-center gap-2"):
                            controls = ui.row().classes("gap-1")
                            render_controls(controls, c)
                            ui.button(
                                "Meno dettagli" if state["selected"] == c.id else "Dettagli invio",
                                icon="expand_less" if state["selected"] == c.id else "expand_more",
                                on_click=lambda cid=c.id: toggle_detail(cid)
                            ).props("outline dense no-caps").classes("text-slate-700 bg-white text-xs px-2.5")

                    with ui.row().classes("items-center gap-4 text-xs text-slate-500"):
                        ui.label(f"Gruppo: {c.group_name or '—'}")
                        ui.label("·")
                        ui.label(f"Server SMTP: {(c.smtp_snapshot or {}).get('name', '—')}")
                        ui.label("·")
                        ui.label(f"Creato: {fmt_dt(c.created_at)}")
                        if c.started_at:
                            ui.label("·")
                            ui.label(f"Avviato: {fmt_dt(c.started_at)}")

                    # Barra di avanzamento
                    with ui.column().classes("gap-1.5 w-full pt-1"):
                        with ui.row().classes("justify-between items-center w-full text-xs"):
                            ui.label(f"Avanzamento: {done}/{c.total_count} email completate ({pct}%)").classes("font-semibold text-slate-700")
                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"✓ {counts['sent']} inviate").classes("text-emerald-700 font-medium")
                                ui.label(f"✗ {counts['failed_temp'] + counts['failed_perm']} errori").classes("text-rose-600 font-medium")
                                ui.label(f"⏳ {counts['pending'] + counts['processing']} rimanenti").classes("text-slate-500 font-medium")

                        progress = ui.linear_progress(min(done / total, 1.0), show_value=False).classes("w-full h-3 rounded-full")
                        progress.props(f"color={'positive' if c.status == 'completed' else 'primary'}")

                    state["refs"][c.id] = {
                        "badge": badge_box, "progress": progress, "controls": controls,
                        "status": c.status,
                    }

                    if state["selected"] == c.id:
                        render_detail(c)

        state["hash"] = "|".join(f"{c.id}:{c.status}" for c in campaigns)

    def tick() -> None:
        if "|".join(f"{c.id}:{c.status}" for c in services.list_campaigns()) != state["hash"]:
            render_all()
            return
        for cid, ref in state["refs"].items():
            campaign = services.get_campaign(cid)
            if campaign is None:
                continue
            counts = services.status_counts(cid)
            ref["progress"].set_value(min(done_of(counts) / max(1, campaign.total_count), 1.0))
            if ref["status"] != campaign.status:
                ref["status"] = campaign.status
                label, color = CAMPAIGN_LABELS.get(campaign.status, (campaign.status, "gray"))
                ref["badge"].clear()
                with ref["badge"]:
                    badge_span(label, color)
                render_controls(ref["controls"], campaign)
            if "stats" in ref:
                render_stats(ref["stats"], cid)
            if "render_items" in ref:
                ref["render_items"]()
            if "log" in ref:
                entries = services.list_logs(cid, after_id=state["last_log_id"])
                for entry in entries:
                    tag = {"info": "INFO ", "success": "OK   ", "warning": "WARN ", "error": "ERR  ", "critical": "CRIT "}
                    ref["log"].push(f"[{entry.created_at:%H:%M:%S}] {tag.get(entry.level, 'LOG  ')} {entry.message}")
                if entries:
                    state["last_log_id"] = entries[-1].id

    render_all()
    ui.timer(1.5, tick)
