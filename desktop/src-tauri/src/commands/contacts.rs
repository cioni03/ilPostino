//! Gruppi e destinatari: elenco, modifica, importazione ed esportazione.

use regex::Regex;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::db::{es, valid_email, Db};

#[derive(Serialize)]
pub struct Group {
    pub id: i64,
    pub name: String,
    pub total: i64,
}

#[tauri::command]
pub fn groups_list(db: State<Db>) -> Result<Vec<Group>, String> {
    let c = db.lock()?;
    let mut st = c
        .prepare(
            "SELECT g.id, g.name, (SELECT COUNT(*) FROM contact_group cg WHERE cg.group_id=g.id) \
             FROM groups g ORDER BY g.name COLLATE NOCASE",
        )
        .map_err(es)?;
    let rows = st
        .query_map([], |r| Ok(Group { id: r.get(0)?, name: r.get(1)?, total: r.get(2)? }))
        .map_err(es)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(es)
}

#[tauri::command]
pub fn group_create(db: State<Db>, name: String) -> Result<i64, String> {
    let name = name.trim().to_string();
    if name.is_empty() {
        return Err("Inserisci il nome del gruppo".into());
    }
    let c = db.lock()?;
    ensure_new_group(&c, &name)
}

fn ensure_new_group(c: &Connection, name: &str) -> Result<i64, String> {
    let exists: Option<i64> = c
        .query_row("SELECT id FROM groups WHERE name=?1", [name], |r| r.get(0))
        .optional()
        .map_err(es)?;
    if exists.is_some() {
        return Err(format!("Il gruppo «{name}» esiste già"));
    }
    c.execute("INSERT INTO groups(name) VALUES(?1)", [name]).map_err(es)?;
    Ok(c.last_insert_rowid())
}

#[tauri::command]
pub fn group_delete(db: State<Db>, id: i64) -> Result<(), String> {
    db.lock()?.execute("DELETE FROM groups WHERE id=?1", [id]).map_err(es)?;
    Ok(())
}

#[derive(Serialize)]
pub struct Contact {
    pub id: i64,
    pub email: String,
    pub first_name: String,
    pub last_name: String,
    pub company: String,
    pub groups: String,
    pub group_ids: Vec<i64>,
}

#[derive(Serialize)]
pub struct ContactPage {
    pub rows: Vec<Contact>,
    pub total: i64,
}

#[derive(Deserialize)]
pub struct ContactQuery {
    pub group_id: Option<i64>,
    pub search: Option<String>,
    pub page: i64,
    pub per_page: i64,
}

#[tauri::command]
pub fn contacts_list(db: State<Db>, query: ContactQuery) -> Result<ContactPage, String> {
    let c = db.lock()?;
    let search = query.search.unwrap_or_default().trim().to_lowercase();
    let like = if search.is_empty() { String::new() } else { format!("%{search}%") };
    let filter = "(?1 IS NULL OR EXISTS (SELECT 1 FROM contact_group x WHERE x.contact_id=c.id AND x.group_id=?1)) \
                  AND (?2='' OR lower(c.email) LIKE ?2 OR lower(coalesce(c.first_name,'')) LIKE ?2 \
                       OR lower(coalesce(c.last_name,'')) LIKE ?2 OR lower(coalesce(c.company,'')) LIKE ?2)";
    let total: i64 = c
        .query_row(&format!("SELECT COUNT(*) FROM contacts c WHERE {filter}"), params![query.group_id, like], |r| r.get(0))
        .map_err(es)?;
    let per_page = query.per_page.clamp(1, 1_000_000);
    let offset = (query.page.max(1) - 1) * per_page;
    let mut st = c
        .prepare(&format!(
            "SELECT c.id,c.email,c.first_name,c.last_name,c.company,\
               (SELECT group_concat(g.id) FROM contact_group cg JOIN groups g ON g.id=cg.group_id WHERE cg.contact_id=c.id),\
               (SELECT group_concat(g.name, ', ') FROM contact_group cg JOIN groups g ON g.id=cg.group_id WHERE cg.contact_id=c.id) \
             FROM contacts c WHERE {filter} ORDER BY c.email COLLATE NOCASE LIMIT ?3 OFFSET ?4"
        ))
        .map_err(es)?;
    let rows = st
        .query_map(params![query.group_id, like, per_page, offset], |r| {
            let ids: Option<String> = r.get(5)?;
            Ok(Contact {
                id: r.get(0)?,
                email: r.get(1)?,
                first_name: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
                last_name: r.get::<_, Option<String>>(3)?.unwrap_or_default(),
                company: r.get::<_, Option<String>>(4)?.unwrap_or_default(),
                group_ids: ids.unwrap_or_default().split(',').filter_map(|s| s.parse().ok()).collect(),
                groups: r.get::<_, Option<String>>(6)?.unwrap_or_default(),
            })
        })
        .map_err(es)?;
    Ok(ContactPage { rows: rows.collect::<Result<Vec<_>, _>>().map_err(es)?, total })
}

#[derive(Deserialize)]
pub struct ContactInput {
    pub id: Option<i64>,
    pub email: String,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub company: Option<String>,
    pub group_ids: Vec<i64>,
    pub new_group_name: Option<String>,
}

fn opt(s: &Option<String>) -> Option<String> {
    s.as_ref().map(|v| v.trim().to_string()).filter(|v| !v.is_empty())
}

#[tauri::command]
pub fn contact_save(db: State<Db>, input: ContactInput) -> Result<i64, String> {
    let email = input.email.trim().to_lowercase();
    if !valid_email(&email) {
        return Err(format!("Email non valida: {email}"));
    }
    let c = db.lock()?;
    let clash: Option<i64> = c
        .query_row("SELECT id FROM contacts WHERE email=?1", [&email], |r| r.get(0))
        .optional()
        .map_err(es)?;
    if let Some(other) = clash {
        if Some(other) != input.id {
            return Err(format!("Esiste già un contatto con l'email {email}"));
        }
    }
    let tx = c.unchecked_transaction().map_err(es)?;
    let mut group_ids = input.group_ids.clone();
    if let Some(name) = opt(&input.new_group_name) {
        group_ids.push(ensure_new_group(&tx, &name)?);
    }
    if group_ids.is_empty() {
        return Err("Assegna il destinatario ad almeno un gruppo".into());
    }
    let id = match input.id {
        Some(id) => {
            tx.execute(
                "UPDATE contacts SET email=?1,first_name=?2,last_name=?3,company=?4,updated_at=datetime('now','localtime') WHERE id=?5",
                params![email, opt(&input.first_name), opt(&input.last_name), opt(&input.company), id],
            )
            .map_err(es)?;
            tx.execute("DELETE FROM contact_group WHERE contact_id=?1", [id]).map_err(es)?;
            id
        }
        None => {
            tx.execute(
                "INSERT INTO contacts(email,first_name,last_name,company) VALUES(?1,?2,?3,?4)",
                params![email, opt(&input.first_name), opt(&input.last_name), opt(&input.company)],
            )
            .map_err(es)?;
            tx.last_insert_rowid()
        }
    };
    for gid in group_ids {
        tx.execute("INSERT OR IGNORE INTO contact_group(contact_id,group_id) VALUES(?1,?2)", params![id, gid])
            .map_err(|_| "Uno dei gruppi selezionati non esiste più".to_string())?;
    }
    tx.commit().map_err(es)?;
    Ok(id)
}

#[tauri::command]
pub fn contact_delete(db: State<Db>, id: i64) -> Result<(), String> {
    db.lock()?.execute("DELETE FROM contacts WHERE id=?1", [id]).map_err(es)?;
    Ok(())
}

// ---------------------------------------------------------------- importazione

struct Parsed {
    email: String, // vuota se la riga non è valida
    first_name: Option<String>,
    last_name: Option<String>,
    company: Option<String>,
    raw: String,
}

fn parse_lines(text: &str) -> Vec<Parsed> {
    let splitter = Regex::new(r"[;,\t]").unwrap();
    let mut lines: Vec<&str> = text.lines().map(|l| l.trim()).filter(|l| !l.is_empty()).collect();
    // la prima riga è un'intestazione se non contiene nessuna email valida
    if let Some(first) = lines.first() {
        let has_email = splitter.split(first).any(|p| valid_email(p.trim()));
        if !has_email && first.to_lowercase().contains("email") {
            lines.remove(0);
        }
    }
    lines
        .into_iter()
        .map(|line| {
            let parts: Vec<String> = splitter.split(line).map(|p| p.trim().to_string()).collect();
            let email = parts.iter().find(|p| valid_email(p)).map(|p| p.to_lowercase()).unwrap_or_default();
            let others: Vec<&String> = parts.iter().filter(|p| p.to_lowercase() != email).collect();
            let get = |i: usize| others.get(i).map(|s| s.to_string()).filter(|s| !s.is_empty());
            Parsed { email, first_name: get(0), last_name: get(1), company: get(2), raw: line.to_string() }
        })
        .collect()
}

#[derive(Serialize)]
pub struct PreviewRow {
    pub email: String,
    pub first_name: String,
    pub last_name: String,
    pub status: String, // new | existing | invalid
}

#[derive(Serialize)]
pub struct ImportPreview {
    pub new: i64,
    pub existing: i64,
    pub invalid: i64,
    pub sample: Vec<PreviewRow>,
}

#[tauri::command]
pub fn contacts_import_preview(db: State<Db>, text: String) -> Result<ImportPreview, String> {
    let c = db.lock()?;
    let mut out = ImportPreview { new: 0, existing: 0, invalid: 0, sample: vec![] };
    for p in parse_lines(&text) {
        let status = if p.email.is_empty() {
            out.invalid += 1;
            "invalid"
        } else {
            let exists: Option<i64> = c
                .query_row("SELECT id FROM contacts WHERE email=?1", [&p.email], |r| r.get(0))
                .optional()
                .map_err(es)?;
            if exists.is_some() {
                out.existing += 1;
                "existing"
            } else {
                out.new += 1;
                "new"
            }
        };
        if out.sample.len() < 6 {
            out.sample.push(PreviewRow {
                email: if p.email.is_empty() { p.raw.clone() } else { p.email.clone() },
                first_name: p.first_name.clone().unwrap_or_default(),
                last_name: p.last_name.clone().unwrap_or_default(),
                status: status.to_string(),
            });
        }
    }
    Ok(out)
}

#[derive(Deserialize)]
pub struct ImportInput {
    pub text: String,
    pub group_id: Option<i64>,
    pub new_group_name: Option<String>,
}

#[derive(Serialize)]
pub struct ImportResult {
    pub created: i64,
    pub existing: i64,
    pub invalid: i64,
    pub group: String,
}

#[tauri::command]
pub fn contacts_import(db: State<Db>, input: ImportInput) -> Result<ImportResult, String> {
    let c = db.lock()?;
    let tx = c.unchecked_transaction().map_err(es)?;
    let (group_id, group_name): (i64, String) = if let Some(name) = opt(&input.new_group_name) {
        let found: Option<i64> = tx
            .query_row("SELECT id FROM groups WHERE name=?1", [&name], |r| r.get(0))
            .optional()
            .map_err(es)?;
        match found {
            Some(id) => (id, name),
            None => {
                tx.execute("INSERT INTO groups(name) VALUES(?1)", [&name]).map_err(es)?;
                (tx.last_insert_rowid(), name)
            }
        }
    } else if let Some(id) = input.group_id {
        let name: String = tx
            .query_row("SELECT name FROM groups WHERE id=?1", [id], |r| r.get(0))
            .map_err(|_| "Gruppo non trovato".to_string())?;
        (id, name)
    } else {
        return Err("Scegli un gruppo o creane uno nuovo".into());
    };
    let (mut created, mut existing, mut invalid) = (0, 0, 0);
    for p in parse_lines(&input.text) {
        if p.email.is_empty() {
            invalid += 1;
            continue;
        }
        let found: Option<i64> = tx
            .query_row("SELECT id FROM contacts WHERE email=?1", [&p.email], |r| r.get(0))
            .optional()
            .map_err(es)?;
        let contact_id = match found {
            Some(id) => {
                existing += 1;
                id
            }
            None => {
                tx.execute(
                    "INSERT INTO contacts(email,first_name,last_name,company) VALUES(?1,?2,?3,?4)",
                    params![p.email, p.first_name, p.last_name, p.company],
                )
                .map_err(es)?;
                created += 1;
                tx.last_insert_rowid()
            }
        };
        tx.execute(
            "INSERT OR IGNORE INTO contact_group(contact_id,group_id) VALUES(?1,?2)",
            params![contact_id, group_id],
        )
        .map_err(es)?;
    }
    tx.commit().map_err(es)?;
    Ok(ImportResult { created, existing, invalid, group: group_name })
}

pub fn csv_field(s: &str) -> String {
    if s.contains(';') || s.contains('"') || s.contains('\n') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

#[tauri::command]
pub fn contacts_export_csv(db: State<Db>) -> Result<String, String> {
    let page = contacts_list(db, ContactQuery { group_id: None, search: None, page: 1, per_page: 1_000_000 })?;
    let mut out = String::from("email;nome;cognome;azienda;gruppi\n");
    for r in page.rows {
        out.push_str(&format!(
            "{};{};{};{};{}\n",
            csv_field(&r.email), csv_field(&r.first_name), csv_field(&r.last_name), csv_field(&r.company), csv_field(&r.groups)
        ));
    }
    Ok(out)
}
