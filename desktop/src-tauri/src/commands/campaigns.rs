//! Campagne: creazione, elenco, destinatari, cronologia e controlli (pausa, ripresa, annulla).

use chrono::NaiveDateTime;
use rusqlite::params;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};

use crate::commands::contacts::csv_field;
use crate::db::{es, now, Db};
use crate::templating::{self, Recipient};
use crate::worker;

#[derive(Serialize)]
pub struct CampaignView {
    pub id: i64,
    pub name: String,
    pub status: String,
    pub group_name: String,
    pub template_name: String,
    pub smtp_name: String,
    pub total_count: i64,
    pub tranche_size: i64,
    pub pause_seconds: i64,
    pub scheduled_at: Option<String>,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub created_at: String,
    pub auto_pause_reason: Option<String>,
    pub sent: i64,
    pub failed: i64,
    pub pending: i64,
}

const LIST_SQL: &str = "SELECT c.id,c.name,c.status,coalesce(c.group_name,''),coalesce(c.template_name,''),c.smtp_snapshot,\
    c.total_count,c.tranche_size,c.pause_seconds,c.scheduled_at,c.started_at,c.completed_at,c.created_at,c.auto_pause_reason,\
    (SELECT COUNT(*) FROM send_items s WHERE s.campaign_id=c.id AND s.status='sent'),\
    (SELECT COUNT(*) FROM send_items s WHERE s.campaign_id=c.id AND s.status IN ('failed_temp','failed_perm')),\
    (SELECT COUNT(*) FROM send_items s WHERE s.campaign_id=c.id AND s.status IN ('pending','processing')) \
    FROM campaigns c";

#[tauri::command]
pub fn campaigns_list(db: State<Db>) -> Result<Vec<CampaignView>, String> {
    let c = db.lock()?;
    let mut st = c.prepare(&format!("{LIST_SQL} ORDER BY c.id DESC")).map_err(es)?;
    let rows = st
        .query_map([], |r| {
            let snapshot: String = r.get(5)?;
            let smtp_name = serde_json::from_str::<serde_json::Value>(&snapshot)
                .ok()
                .and_then(|v| v.get("name").and_then(|n| n.as_str().map(String::from)))
                .unwrap_or_default();
            Ok(CampaignView {
                id: r.get(0)?,
                name: r.get(1)?,
                status: r.get(2)?,
                group_name: r.get(3)?,
                template_name: r.get(4)?,
                smtp_name,
                total_count: r.get(6)?,
                tranche_size: r.get(7)?,
                pause_seconds: r.get(8)?,
                scheduled_at: r.get(9)?,
                started_at: r.get(10)?,
                completed_at: r.get(11)?,
                created_at: r.get(12)?,
                auto_pause_reason: r.get(13)?,
                sent: r.get(14)?,
                failed: r.get(15)?,
                pending: r.get(16)?,
            })
        })
        .map_err(es)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(es)
}

#[derive(Deserialize)]
pub struct CampaignInput {
    pub name: String,
    pub smtp_server_id: i64,
    pub template_id: Option<i64>,
    pub template_name: String,
    pub subject: String,
    pub html_body: String,
    pub group_id: i64,
    pub tranche_size: i64,
    pub pause_seconds: i64,
    pub max_retries: i64,
    pub retry_delay_seconds: i64,
    pub scheduled_at: Option<String>, // "AAAA-MM-GG HH:MM:SS" ora locale
}

#[tauri::command]
pub fn campaign_create(app: AppHandle, db: State<Db>, input: CampaignInput) -> Result<i64, String> {
    templating::check_syntax(&input.subject).map_err(|e| format!("Oggetto: {e}"))?;
    templating::check_syntax(&input.html_body).map_err(|e| format!("Corpo HTML: {e}"))?;
    templating::render_subject(&input.subject, &Recipient::sample()).map_err(|e| format!("Oggetto: {e}"))?;
    templating::render_html(&input.html_body, &Recipient::sample()).map_err(|e| format!("Corpo HTML: {e}"))?;
    if input.subject.trim().is_empty() {
        return Err("L'oggetto dell'email non può essere vuoto".into());
    }
    let scheduled = match input.scheduled_at.as_deref().filter(|s| !s.is_empty()) {
        Some(s) => {
            let when = NaiveDateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S").map_err(|_| "Data di partenza non valida".to_string())?;
            if when <= chrono::Local::now().naive_local() {
                return Err("La data di partenza deve essere futura".into());
            }
            Some(s.to_string())
        }
        None => None,
    };
    let id = {
        let c = db.lock()?;
        let tx = c.unchecked_transaction().map_err(es)?;
        let snapshot: serde_json::Value = tx
            .query_row(
                "SELECT name,host,port,security,username,sender_email,sender_name,reply_to,rate_limit_emails_per_hour,active \
                 FROM smtp_servers WHERE id=?1",
                [input.smtp_server_id],
                |r| {
                    if r.get::<_, i64>(9)? == 0 {
                        return Err(rusqlite::Error::QueryReturnedNoRows);
                    }
                    Ok(serde_json::json!({
                        "name": r.get::<_, String>(0)?, "host": r.get::<_, String>(1)?, "port": r.get::<_, i64>(2)?,
                        "security": r.get::<_, String>(3)?, "username": r.get::<_, Option<String>>(4)?,
                        "sender_email": r.get::<_, String>(5)?, "sender_name": r.get::<_, Option<String>>(6)?,
                        "reply_to": r.get::<_, Option<String>>(7)?, "rate_limit": r.get::<_, Option<i64>>(8)?,
                    }))
                },
            )
            .map_err(|_| "Server SMTP non trovato o non attivo".to_string())?;
        let group_name: String = tx
            .query_row("SELECT name FROM groups WHERE id=?1", [input.group_id], |r| r.get(0))
            .map_err(|_| "Gruppo non trovato".to_string())?;
        let status = if scheduled.is_some() { "scheduled" } else { "running" };
        let started = if scheduled.is_some() { None } else { Some(now()) };
        tx.execute(
            "INSERT INTO campaigns(name,status,smtp_server_id,smtp_snapshot,template_id,template_name,subject,html_body,group_id,group_name,\
             tranche_size,pause_seconds,max_retries,retry_delay_seconds,scheduled_at,started_at) \
             VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16)",
            params![
                input.name.trim(), status, input.smtp_server_id, snapshot.to_string(), input.template_id, input.template_name,
                input.subject, input.html_body, input.group_id, group_name, input.tranche_size.max(1),
                input.pause_seconds.max(0), input.max_retries.max(0), input.retry_delay_seconds.max(0), scheduled, started
            ],
        )
        .map_err(es)?;
        let id = tx.last_insert_rowid();
        let added = tx
            .execute(
                "INSERT INTO send_items(campaign_id,contact_id,email,first_name,last_name,company,tags) \
                 SELECT ?1,c.id,c.email,c.first_name,c.last_name,c.company,c.tags FROM contacts c \
                 JOIN contact_group cg ON cg.contact_id=c.id WHERE cg.group_id=?2 ORDER BY c.id",
                params![id, input.group_id],
            )
            .map_err(es)?;
        if added == 0 {
            return Err("Il gruppo selezionato non ha destinatari".into());
        }
        tx.execute("UPDATE campaigns SET total_count=?1 WHERE id=?2", params![added as i64, id]).map_err(es)?;
        tx.execute(
            "INSERT INTO log_entries(campaign_id,level,message) VALUES(?1,'info',?2)",
            params![id, format!("Invio creato: {added} destinatari, tranche da {}, pausa {}s", input.tranche_size, input.pause_seconds)],
        )
        .map_err(es)?;
        tx.commit().map_err(es)?;
        id
    };
    worker::start(&app, id);
    Ok(id)
}

#[tauri::command]
pub fn campaign_pause(app: AppHandle, id: i64) -> Result<(), String> {
    worker::pause(&app, id)
}

#[tauri::command]
pub fn campaign_resume(app: AppHandle, id: i64) -> Result<(), String> {
    worker::resume(&app, id)
}

#[tauri::command]
pub fn campaign_cancel(app: AppHandle, id: i64) -> Result<(), String> {
    worker::cancel(&app, id)
}

#[tauri::command]
pub fn campaign_delete(db: State<Db>, id: i64) -> Result<(), String> {
    let c = db.lock()?;
    let status: String = c.query_row("SELECT status FROM campaigns WHERE id=?1", [id], |r| r.get(0)).map_err(es)?;
    if status == "running" || status == "scheduled" {
        return Err("Interrompi la campagna prima di eliminarla".into());
    }
    c.execute("DELETE FROM campaigns WHERE id=?1", [id]).map_err(es)?;
    Ok(())
}

#[derive(Serialize)]
pub struct ItemRow {
    pub email: String,
    pub name: String,
    pub status: String,
    pub attempts: i64,
    pub last_error: String,
    pub sent_at: String,
}

#[derive(Serialize)]
pub struct ItemPage {
    pub rows: Vec<ItemRow>,
    pub total: i64,
}

#[derive(Deserialize)]
pub struct ItemQuery {
    pub campaign_id: i64,
    pub status: Option<String>,
    pub page: i64,
    pub per_page: i64,
}

#[tauri::command]
pub fn campaign_items(db: State<Db>, query: ItemQuery) -> Result<ItemPage, String> {
    let c = db.lock()?;
    let status = query.status.unwrap_or_default();
    let filter = "campaign_id=?1 AND (?2='' OR status=?2 OR (?2='failed' AND status IN ('failed_temp','failed_perm')) \
                  OR (?2='pending' AND status IN ('pending','processing')))";
    let total: i64 = c
        .query_row(&format!("SELECT COUNT(*) FROM send_items WHERE {filter}"), params![query.campaign_id, status], |r| r.get(0))
        .map_err(es)?;
    let per_page = query.per_page.clamp(1, 1_000_000);
    let offset = (query.page.max(1) - 1) * per_page;
    let mut st = c
        .prepare(&format!(
            "SELECT email,first_name,last_name,status,attempts,last_error,sent_at FROM send_items WHERE {filter} ORDER BY id LIMIT ?3 OFFSET ?4"
        ))
        .map_err(es)?;
    let rows = st
        .query_map(params![query.campaign_id, status, per_page, offset], |r| {
            let first = r.get::<_, Option<String>>(1)?.unwrap_or_default();
            let last = r.get::<_, Option<String>>(2)?.unwrap_or_default();
            Ok(ItemRow {
                email: r.get(0)?,
                name: format!("{first} {last}").trim().to_string(),
                status: r.get(3)?,
                attempts: r.get(4)?,
                last_error: r.get::<_, Option<String>>(5)?.unwrap_or_default(),
                sent_at: r.get::<_, Option<String>>(6)?.unwrap_or_default(),
            })
        })
        .map_err(es)?;
    Ok(ItemPage { rows: rows.collect::<Result<Vec<_>, _>>().map_err(es)?, total })
}

#[derive(Serialize)]
pub struct LogRow {
    pub id: i64,
    pub level: String,
    pub message: String,
    pub created_at: String,
}

#[tauri::command]
pub fn campaign_logs(db: State<Db>, campaign_id: i64, limit: Option<i64>) -> Result<Vec<LogRow>, String> {
    let c = db.lock()?;
    let mut st = c
        .prepare("SELECT id,level,message,created_at FROM log_entries WHERE campaign_id=?1 ORDER BY id DESC LIMIT ?2")
        .map_err(es)?;
    let rows = st
        .query_map(params![campaign_id, limit.unwrap_or(300)], |r| {
            Ok(LogRow { id: r.get(0)?, level: r.get(1)?, message: r.get(2)?, created_at: r.get(3)? })
        })
        .map_err(es)?;
    let mut v = rows.collect::<Result<Vec<_>, _>>().map_err(es)?;
    v.reverse();
    Ok(v)
}

#[tauri::command]
pub fn campaign_export_csv(db: State<Db>, id: i64) -> Result<String, String> {
    let page = campaign_items(db, ItemQuery { campaign_id: id, status: None, page: 1, per_page: 1_000_000 })?;
    let mut out = String::from("email;nome;stato;tentativi;ultimo_errore;inviata_il\n");
    for r in page.rows {
        out.push_str(&format!(
            "{};{};{};{};{};{}\n",
            csv_field(&r.email), csv_field(&r.name), r.status, r.attempts, csv_field(&r.last_error), r.sent_at
        ));
    }
    Ok(out)
}
