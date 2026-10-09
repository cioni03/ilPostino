//! Profili SMTP: elenco, salvataggio, diagnostica e invio di prova.

use rusqlite::params;
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::db::{es, valid_email, Db};
use crate::mailer::{self, Diagnosis, SmtpCfg};
use crate::secrets;

#[derive(Serialize)]
pub struct SmtpServer {
    pub id: i64,
    pub name: String,
    pub host: String,
    pub port: i64,
    pub security: String,
    pub username: Option<String>,
    pub has_password: bool,
    pub sender_email: String,
    pub sender_name: Option<String>,
    pub reply_to: Option<String>,
    pub rate_limit: Option<i64>,
    pub active: bool,
}

#[derive(Deserialize)]
pub struct SmtpInput {
    pub id: Option<i64>,
    pub name: String,
    pub host: String,
    pub port: i64,
    pub security: String,
    pub username: Option<String>,
    pub password: Option<String>,
    pub sender_email: String,
    pub sender_name: Option<String>,
    pub reply_to: Option<String>,
    pub rate_limit: Option<i64>,
    pub active: bool,
}

const COLS: &str = "id,name,host,port,security,username,sender_email,sender_name,reply_to,rate_limit_emails_per_hour,active";

fn map_server(r: &rusqlite::Row) -> rusqlite::Result<SmtpServer> {
    let id: i64 = r.get(0)?;
    Ok(SmtpServer {
        id,
        name: r.get(1)?,
        host: r.get(2)?,
        port: r.get(3)?,
        security: r.get(4)?,
        username: r.get(5)?,
        has_password: secrets::get(id).is_some(),
        sender_email: r.get(6)?,
        sender_name: r.get(7)?,
        reply_to: r.get(8)?,
        rate_limit: r.get(9)?,
        active: r.get::<_, i64>(10)? != 0,
    })
}

fn blank(s: &Option<String>) -> Option<String> {
    s.as_ref().map(|v| v.trim().to_string()).filter(|v| !v.is_empty())
}

/// Parametri di connessione completi di password (dal portachiavi).
pub fn load_cfg(db: &Db, id: i64) -> Result<SmtpCfg, String> {
    let c = db.lock()?;
    let (host, port, security, username, sender_email, sender_name, reply_to): (
        String, i64, String, Option<String>, String, Option<String>, Option<String>,
    ) = c
        .query_row(
            "SELECT host,port,security,username,sender_email,sender_name,reply_to FROM smtp_servers WHERE id=?1",
            [id],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?, r.get(5)?, r.get(6)?)),
        )
        .map_err(|_| "Server SMTP non trovato".to_string())?;
    Ok(SmtpCfg {
        host,
        port: port as u16,
        security,
        username,
        password: secrets::get(id),
        sender_email,
        sender_name,
        reply_to,
    })
}

#[tauri::command]
pub fn smtp_list(db: State<Db>) -> Result<Vec<SmtpServer>, String> {
    let c = db.lock()?;
    let mut st = c
        .prepare(&format!("SELECT {COLS} FROM smtp_servers ORDER BY name COLLATE NOCASE"))
        .map_err(es)?;
    let rows = st.query_map([], map_server).map_err(es)?;
    rows.collect::<Result<Vec<_>, _>>().map_err(es)
}

#[tauri::command]
pub fn smtp_save(db: State<Db>, input: SmtpInput) -> Result<i64, String> {
    let sender = input.sender_email.trim().to_lowercase();
    if !valid_email(&sender) {
        return Err(format!("Mittente non valido: {sender}"));
    }
    if input.name.trim().is_empty() || input.host.trim().is_empty() {
        return Err("Inserisci nome e host del server".into());
    }
    if !(1..=65535).contains(&input.port) {
        return Err("La porta deve essere tra 1 e 65535".into());
    }
    let reply = blank(&input.reply_to).map(|r| r.to_lowercase());
    let rate = input.rate_limit.filter(|r| *r > 0);
    let id = {
        let c = db.lock()?;
        match input.id {
            Some(id) => {
                c.execute(
                    "UPDATE smtp_servers SET name=?1,host=?2,port=?3,security=?4,username=?5,sender_email=?6,sender_name=?7,\
                     reply_to=?8,rate_limit_emails_per_hour=?9,active=?10,updated_at=datetime('now','localtime') WHERE id=?11",
                    params![
                        input.name.trim(), input.host.trim(), input.port, input.security, blank(&input.username),
                        sender, blank(&input.sender_name), reply, rate, input.active as i64, id
                    ],
                )
                .map_err(es)?;
                id
            }
            None => {
                c.execute(
                    "INSERT INTO smtp_servers(name,host,port,security,username,sender_email,sender_name,reply_to,rate_limit_emails_per_hour,active) \
                     VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
                    params![
                        input.name.trim(), input.host.trim(), input.port, input.security, blank(&input.username),
                        sender, blank(&input.sender_name), reply, rate, input.active as i64
                    ],
                )
                .map_err(es)?;
                c.last_insert_rowid()
            }
        }
    };
    if let Some(pw) = input.password.filter(|p| !p.is_empty()) {
        secrets::set(id, &pw)?;
    }
    Ok(id)
}

#[tauri::command]
pub fn smtp_delete(db: State<Db>, id: i64) -> Result<(), String> {
    db.lock()?.execute("DELETE FROM smtp_servers WHERE id=?1", [id]).map_err(es)?;
    secrets::delete(id);
    Ok(())
}

#[tauri::command]
pub fn smtp_set_active(db: State<Db>, id: i64, active: bool) -> Result<(), String> {
    db.lock()?
        .execute("UPDATE smtp_servers SET active=?1 WHERE id=?2", params![active as i64, id])
        .map_err(es)?;
    Ok(())
}

#[tauri::command]
pub async fn smtp_diagnose(db: State<'_, Db>, id: i64) -> Result<Diagnosis, String> {
    let cfg = load_cfg(&db, id)?;
    Ok(mailer::diagnose(&cfg).await)
}

#[derive(Deserialize)]
pub struct TestMail {
    pub smtp_id: i64,
    pub to: String,
    pub subject: String,
    pub html: String,
}

#[tauri::command]
pub async fn smtp_send_test(db: State<'_, Db>, input: TestMail) -> Result<(), String> {
    if !valid_email(input.to.trim()) {
        return Err("Inserisci un indirizzo email valido per la prova".into());
    }
    let cfg = load_cfg(&db, input.smtp_id)?;
    let transport = mailer::build_transport(&cfg)?;
    let msg = mailer::build_message(&cfg, input.to.trim(), &input.subject, &input.html)?;
    mailer::send(&transport, msg).await.map_err(|e| mailer::classify(&e).1)
}
