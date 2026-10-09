//! Template email: elenco, salvataggio e anteprima con i dati di un destinatario.

use rusqlite::{params, OptionalExtension};
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::db::{es, Db};
use crate::templating::{self, Recipient};

#[derive(Serialize)]
pub struct Template {
    pub id: i64,
    pub name: String,
    pub subject: String,
    pub html_body: String,
    pub updated_at: String,
}

#[tauri::command]
pub fn templates_list(db: State<Db>) -> Result<Vec<Template>, String> {
    let c = db.lock()?;
    let mut st = c
        .prepare("SELECT id,name,subject,html_body,updated_at FROM email_templates ORDER BY name COLLATE NOCASE")
        .map_err(es)?;
    let rows = st
        .query_map([], |r| {
            Ok(Template { id: r.get(0)?, name: r.get(1)?, subject: r.get(2)?, html_body: r.get(3)?, updated_at: r.get(4)? })
        })
        .map_err(es)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(es)
}

#[derive(Deserialize)]
pub struct TemplateInput {
    pub id: Option<i64>,
    pub name: String,
    pub subject: String,
    pub html_body: String,
}

#[tauri::command]
pub fn template_save(db: State<Db>, input: TemplateInput) -> Result<i64, String> {
    templating::check_syntax(&input.subject).map_err(|e| format!("Oggetto: {e}"))?;
    templating::check_syntax(&input.html_body).map_err(|e| format!("Corpo HTML: {e}"))?;
    let name = if input.name.trim().is_empty() { "Senza nome".to_string() } else { input.name.trim().to_string() };
    let c = db.lock()?;
    match input.id {
        Some(id) => {
            c.execute(
                "UPDATE email_templates SET name=?1,subject=?2,html_body=?3,updated_at=datetime('now','localtime') WHERE id=?4",
                params![name, input.subject, input.html_body, id],
            )
            .map_err(es)?;
            Ok(id)
        }
        None => {
            c.execute(
                "INSERT INTO email_templates(name,subject,html_body) VALUES(?1,?2,?3)",
                params![name, input.subject, input.html_body],
            )
            .map_err(es)?;
            Ok(c.last_insert_rowid())
        }
    }
}

#[tauri::command]
pub fn template_duplicate(db: State<Db>, id: i64) -> Result<i64, String> {
    let c = db.lock()?;
    c.execute(
        "INSERT INTO email_templates(name,subject,html_body) SELECT name || ' (copia)', subject, html_body FROM email_templates WHERE id=?1",
        [id],
    )
    .map_err(es)?;
    Ok(c.last_insert_rowid())
}

#[tauri::command]
pub fn template_delete(db: State<Db>, id: i64) -> Result<(), String> {
    db.lock()?.execute("DELETE FROM email_templates WHERE id=?1", [id]).map_err(es)?;
    Ok(())
}

#[derive(Deserialize)]
pub struct RenderInput {
    pub subject: String,
    pub html_body: String,
    pub contact_id: Option<i64>,
    pub group_id: Option<i64>,
}

#[derive(Serialize, Default)]
pub struct RenderOutput {
    pub subject: String,
    pub html: String,
    pub error: Option<String>,
    pub unknown: Vec<String>,
}

fn recipient_for(db: &Db, contact_id: Option<i64>, group_id: Option<i64>) -> Result<Recipient, String> {
    let c = db.lock()?;
    let sql = "SELECT email,first_name,last_name,company,tags FROM contacts";
    let row = |r: &rusqlite::Row| -> rusqlite::Result<Recipient> {
        Ok(Recipient {
            email: r.get(0)?,
            first_name: r.get::<_, Option<String>>(1)?.unwrap_or_default(),
            last_name: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
            company: r.get::<_, Option<String>>(3)?.unwrap_or_default(),
            tags: r.get::<_, Option<String>>(4)?.unwrap_or_default(),
        })
    };
    let found = if let Some(id) = contact_id {
        c.query_row(&format!("{sql} WHERE id=?1"), [id], row).optional().map_err(es)?
    } else if let Some(gid) = group_id {
        c.query_row(
            &format!("{sql} WHERE id IN (SELECT contact_id FROM contact_group WHERE group_id=?1) ORDER BY id LIMIT 1"),
            [gid],
            row,
        )
        .optional()
        .map_err(es)?
    } else {
        None
    };
    Ok(found.unwrap_or_else(Recipient::sample))
}

/// Anteprima + validazione: restituisce l'errore invece di fallire, così la UI lo mostra accanto al codice.
#[tauri::command]
pub fn template_render(db: State<Db>, input: RenderInput) -> Result<RenderOutput, String> {
    let who = recipient_for(&db, input.contact_id, input.group_id)?;
    let mut unknown = templating::unknown_variables(&input.html_body);
    unknown.extend(templating::unknown_variables(&input.subject));
    unknown.sort();
    unknown.dedup();
    let subject = templating::render_subject(&input.subject, &who);
    let html = templating::render_html(&input.html_body, &who);
    match (subject, html) {
        (Ok(subject), Ok(html)) => Ok(RenderOutput { subject, html, error: None, unknown }),
        (s, h) => {
            let err = s.err().map(|e| format!("Oggetto: {e}")).or(h.err().map(|e| format!("Corpo HTML: {e}")));
            Ok(RenderOutput { error: err, unknown, ..Default::default() })
        }
    }
}
