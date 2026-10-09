import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { ArrowLeft, ArrowRight, Download, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { api, Contact, Group, ImportPreview } from "../lib/api";
import { Empty, Field, Modal, n, saveCsv, useAction, useApp, useLoad } from "../lib/ui";

const PER_PAGE = 25;

export default function Recipients() {
  const { ask } = useApp();
  const run = useAction();
  const [groupId, setGroupId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Contact | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const [newGroup, setNewGroup] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setQuery(search); setPage(1); }, 250);
    return () => clearTimeout(t);
  }, [search]);

  const groups = useLoad(api.groupsList, []);
  const contacts = useLoad(() => api.contactsList({ group_id: groupId, search: query, page, per_page: PER_PAGE }), [groupId, query, page]);
  const group = groups.data?.find((g) => g.id === groupId) ?? null;
  const total = contacts.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PER_PAGE));

  const reloadAll = () => { groups.reload(); contacts.reload(); };

  return (
    <main className="main flush">
      <section style={{ width: 232, flex: "none", background: "var(--surface)", borderRight: "1px solid var(--line)", padding: "20px 12px", display: "flex", flexDirection: "column", gap: 4, overflow: "auto" }} aria-label="Gruppi">
        <div className="row" style={{ padding: "0 8px 8px" }}>
          <span className="eyebrow">Gruppi</span>
          <button className="btn ghost i s sp" aria-label="Nuovo gruppo" onClick={() => setNewGroup(true)}><Plus size={14} /></button>
        </div>
        <GroupItem label="Tutti" count={contacts.data && groupId === null ? contacts.data.total : undefined} on={groupId === null} onClick={() => { setGroupId(null); setPage(1); }} />
        {(groups.data ?? []).map((g) => <GroupItem key={g.id} label={g.name} count={g.total} on={groupId === g.id} onClick={() => { setGroupId(g.id); setPage(1); }} />)}
        {group && (
          <button className="btn ghost s dng" style={{ marginTop: 12, alignSelf: "flex-start" }} onClick={async () => {
            if (await ask("Eliminare il gruppo?", `«${group.name}» verrà eliminato. I destinatari restano nell'elenco generale.`, "Elimina", true)) {
              await run(() => api.groupDelete(group.id), "Gruppo eliminato");
              setGroupId(null); reloadAll();
            }
          }}><Trash2 size={13} />Elimina gruppo</button>
        )}
      </section>

      <section style={{ flex: 1, minWidth: 0, padding: "22px 28px 0", display: "flex", flexDirection: "column", gap: 16, overflow: "auto" }}>
        <div className="ph">
          <div><h1 className="h1">{group ? group.name : "Tutti i destinatari"}</h1><p>{n(group ? group.total : total)} persone</p></div>
          <div className="row sp" style={{ gap: 8 }}>
            <button className="btn ghost i" aria-label="Esporta tutti in CSV" title="Esporta tutti in CSV" onClick={async () => { const csv = await run(api.contactsExportCsv); if (csv) await run(() => saveCsv("destinatari.csv", csv), "File salvato"); }}><Download size={15} /></button>
            <button className="btn" onClick={() => setImporting(true)}><Upload size={15} />Importa</button>
            <button className="btn pri" onClick={() => setEditing("new")}><Plus size={15} />Nuovo</button>
          </div>
        </div>

        <div className="row inp" style={{ width: 320, gap: 8 }}>
          <Search size={14} className="muted" />
          <input aria-label="Cerca" placeholder="Cerca…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ border: 0, background: "transparent", outline: "none", flex: 1, minWidth: 0 }} />
        </div>

        <div className="card" style={{ overflow: "hidden", flex: "none" }}>
          {(contacts.data?.rows.length ?? 0) === 0 ? (
            <Empty title={query ? "Nessun risultato" : "Nessun destinatario"} text={query ? undefined : "Importa una lista incollandola oppure aggiungine uno."}>
              {!query && <button className="btn pri" onClick={() => setImporting(true)}>Importa una lista</button>}
            </Empty>
          ) : (
            <>
              <table className="tbl">
                <colgroup><col style={{ width: "32%" }} /><col style={{ width: "20%" }} /><col style={{ width: "20%" }} /><col /><col style={{ width: 84 }} /></colgroup>
                <thead><tr><th>Email</th><th>Nome</th><th>Azienda</th><th>Gruppo</th><th /></tr></thead>
                <tbody>
                  {contacts.data!.rows.map((c) => (
                    <tr key={c.id}>
                      <td className="p">{c.email}</td>
                      <td>{`${c.first_name} ${c.last_name}`.trim() || "—"}</td>
                      <td>{c.company || "—"}</td>
                      <td>{c.groups}</td>
                      <td style={{ textAlign: "right" }}>
                        <button className="btn ghost s i" aria-label={`Modifica ${c.email}`} onClick={() => setEditing(c)}><Pencil size={13} /></button>
                        <button className="btn ghost s i" aria-label={`Elimina ${c.email}`} onClick={async () => {
                          if (await ask("Eliminare il destinatario?", `${c.email} verrà eliminato definitivamente.`, "Elimina", true)) { await run(() => api.contactDelete(c.id)); reloadAll(); }
                        }}><Trash2 size={13} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="row" style={{ padding: "0 14px", height: 44, borderTop: "1px solid var(--line)", background: "var(--surface-2)" }}>
                <span className="muted sm">Pagina {page} di {pages} · {n(total)} destinatari</span>
                <div className="row sp" style={{ gap: 6 }}>
                  <button className="btn s i" aria-label="Pagina precedente" disabled={page <= 1} onClick={() => setPage(page - 1)}><ArrowLeft size={14} /></button>
                  <button className="btn s i" aria-label="Pagina successiva" disabled={page >= pages} onClick={() => setPage(page + 1)}><ArrowRight size={14} /></button>
                </div>
              </div>
            </>
          )}
        </div>
        <div style={{ height: 8, flex: "none" }} />
      </section>

      {editing && <ContactModal contact={editing === "new" ? null : editing} groups={groups.data ?? []} defaultGroup={groupId} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); reloadAll(); }} />}
      {importing && <ImportModal groups={groups.data ?? []} defaultGroup={groupId} onClose={() => setImporting(false)} onDone={() => { setImporting(false); reloadAll(); }} />}
      {newGroup && <NewGroupModal onClose={() => setNewGroup(false)} onDone={() => { setNewGroup(false); groups.reload(); }} />}    </main>
  );
}

function GroupItem({ label, count, on, onClick }: { label: string; count?: number; on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className="nav" style={{ height: 34, color: on ? "var(--accent-fg)" : "var(--ink-2)", background: on ? "var(--accent-soft)" : "transparent", fontWeight: on ? 600 : 500 }}>
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      {count !== undefined && <span className="mono xs sp">{n(count)}</span>}
    </button>
  );
}

function NewGroupModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const run = useAction();
  const [name, setName] = useState("");
  const submit = async () => { if (await run(() => api.groupCreate(name), "Gruppo creato") !== undefined) onDone(); };
  return (
    <Modal title="Nuovo gruppo" width={400} onClose={onClose}>
      <form style={{ padding: "0 22px 20px" }} className="col" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Nome del gruppo" htmlFor="g-name"><input id="g-name" autoFocus className="inp" value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <div className="row" style={{ justifyContent: "flex-end" }}><button type="button" className="btn" onClick={onClose}>Annulla</button><button className="btn pri" type="submit">Crea</button></div>
      </form>
    </Modal>
  );
}

function ContactModal({ contact, groups, defaultGroup, onClose, onSaved }: { contact: Contact | null; groups: Group[]; defaultGroup: number | null; onClose: () => void; onSaved: () => void }) {
  const run = useAction();
  const [f, setF] = useState({ email: contact?.email ?? "", first: contact?.first_name ?? "", last: contact?.last_name ?? "", company: contact?.company ?? "", newGroup: "" });
  const [sel, setSel] = useState<number[]>(contact?.group_ids ?? (defaultGroup ? [defaultGroup] : []));
  const submit = async () => {
    const id = await run(() => api.contactSave({
      id: contact?.id ?? null, email: f.email, first_name: f.first, last_name: f.last, company: f.company,
      group_ids: sel, new_group_name: f.newGroup.trim() || null,
    }), "Destinatario salvato");
    if (id !== undefined) onSaved();
  };
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Modal title={contact ? "Modifica destinatario" : "Nuovo destinatario"} width={480} onClose={onClose}>
      <form style={{ padding: "0 22px 20px" }} className="col" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label="Email" htmlFor="c-email"><input id="c-email" autoFocus className="inp" value={f.email} onChange={set("email")} /></Field>
        <div className="row" style={{ alignItems: "flex-start" }}>
          <div className="grow"><Field label="Nome" htmlFor="c-first"><input id="c-first" className="inp" value={f.first} onChange={set("first")} /></Field></div>
          <div className="grow"><Field label="Cognome" htmlFor="c-last"><input id="c-last" className="inp" value={f.last} onChange={set("last")} /></Field></div>
        </div>
        <Field label="Azienda" htmlFor="c-company"><input id="c-company" className="inp" value={f.company} onChange={set("company")} /></Field>
        <div>
          <span className="lab">Gruppi (almeno uno)</span>
          <div className="row wrap" style={{ gap: 12, maxHeight: 110, overflow: "auto" }}>
            {groups.map((g) => (
              <label key={g.id} className="row sm" style={{ gap: 6 }}>
                <input type="checkbox" checked={sel.includes(g.id)} onChange={(e) => setSel(e.target.checked ? [...sel, g.id] : sel.filter((x) => x !== g.id))} />{g.name}
              </label>
            ))}
            {groups.length === 0 && <span className="muted sm">Non ci sono ancora gruppi: creane uno qui sotto.</span>}
          </div>
          <input className="inp" style={{ marginTop: 8 }} aria-label="Nuovo gruppo" placeholder="oppure crea un nuovo gruppo…" value={f.newGroup} onChange={set("newGroup")} />
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}><button type="button" className="btn" onClick={onClose}>Annulla</button><button className="btn pri" type="submit">Salva</button></div>
      </form>
    </Modal>
  );
}

function ImportModal({ groups, defaultGroup, onClose, onDone }: { groups: Group[]; defaultGroup: number | null; onClose: () => void; onDone: () => void }) {
  const run = useAction();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [groupId, setGroupId] = useState<number | -1>(defaultGroup ?? groups[0]?.id ?? -1);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    if (!text.trim()) { setPreview(null); return; }
    const t = setTimeout(() => api.importPreview(text).then(setPreview, () => setPreview(null)), 200);
    return () => clearTimeout(t);
  }, [text]);

  const pickFile = async () => {
    const path = await open({ multiple: false, filters: [{ name: "Testo / CSV", extensions: ["csv", "txt", "tsv"] }] });
    if (typeof path === "string") { const t = await run(() => api.readTextFile(path)); if (t !== undefined) setText(t); }
  };
  const count = preview ? preview.new + preview.existing : 0;
  const submit = async () => {
    const r = await run(() => api.importContacts({ text, group_id: groupId === -1 ? null : groupId, new_group_name: groupId === -1 ? newName : null }));
    if (r) { onDone(); }
  };
  const label: Record<string, [string, string]> = { new: ["Nuovo", "okc"], existing: ["Già presente", "acc"], invalid: ["Non valida", "badc"] };

  return (
    <Modal title="Importa destinatari" width={860} onClose={onClose}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1.3fr)", gap: 22, padding: "6px 22px 18px" }}>
        <div className="col" style={{ gap: 8 }}>
          <label className="lab" htmlFor="i-text" style={{ margin: 0 }}>Incolla le righe (email; nome; cognome; azienda)</label>
          <textarea id="i-text" className="inp m" rows={10} style={{ resize: "none", lineHeight: 1.7, whiteSpace: "pre" }} value={text} onChange={(e) => setText(e.target.value)} placeholder={"mario.rossi@example.com; Mario; Rossi; Acme Srl"} />
        </div>
        <div className="col" style={{ gap: 8 }}>
          <span className="lab" style={{ margin: 0 }}>Anteprima</span>
          {preview ? (
            <>
              <div className="card" style={{ overflow: "hidden" }}>
                <table className="tbl">
                  <colgroup><col style={{ width: "46%" }} /><col style={{ width: "24%" }} /><col /></colgroup>
                  <thead><tr><th>Email</th><th>Nome</th><th>Esito</th></tr></thead>
                  <tbody>{preview.sample.map((r, i) => <tr key={i}><td className="p">{r.email}</td><td>{`${r.first_name} ${r.last_name}`.trim() || "—"}</td><td className={label[r.status][1]}>{label[r.status][0]}</td></tr>)}</tbody>
                </table>
              </div>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="badge b-ok">{n(preview.new)} nuovi</span>
                <span className="badge b-run">{n(preview.existing)} già presenti</span>
                {preview.invalid > 0 && <span className="badge b-bad">{n(preview.invalid)} non validi</span>}
              </div>
            </>
          ) : <div className="muted sm" style={{ padding: "24px 0" }}>Incolla una lista o scegli un file per vedere l'anteprima.</div>}
        </div>
      </div>
      <hr className="hr" />
      <div className="row" style={{ padding: "14px 22px", gap: 12 }}>
        <label className="lab" htmlFor="i-group" style={{ margin: 0 }}>Aggiungi al gruppo</label>
        <select id="i-group" className="inp" style={{ width: 200 }} value={groupId} onChange={(e) => setGroupId(Number(e.target.value))}>
          {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          <option value={-1}>＋ Nuovo gruppo…</option>
        </select>
        {groupId === -1 && <input className="inp" style={{ width: 180 }} aria-label="Nome del nuovo gruppo" placeholder="Nome del gruppo" value={newName} onChange={(e) => setNewName(e.target.value)} />}
        <button className="btn ghost s" onClick={pickFile}><Upload size={13} />Scegli un file…</button>
        <button className="btn sp" onClick={onClose}>Annulla</button>
        <button className="btn pri" disabled={!count || (groupId === -1 && !newName.trim())} onClick={submit}>Importa {count ? n(count) : ""} destinatari</button>
      </div>
    </Modal>
  );
}
