//! Worker in background: invia le campagne a tranche, con pause, nuovi tentativi, pausa automatica e ripresa.

use chrono::NaiveDateTime;
use rusqlite::params;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_notification::NotificationExt;

use crate::commands::smtp::load_cfg;
use crate::db::{es, now, Db};
use crate::mailer::{self, ErrKind};
use crate::templating::{self, Recipient};

const RUN: u8 = 0;
const PAUSE: u8 = 1;
const CANCEL: u8 = 2;

#[derive(Default)]
pub struct WorkerPool {
    running: Mutex<HashMap<i64, Arc<AtomicU8>>>,
}

struct Item {
    id: i64,
    email: String,
    first_name: String,
    last_name: String,
    company: String,
    tags: String,
}

struct Campaign {
    status: String,
    smtp_server_id: Option<i64>,
    smtp_snapshot: serde_json::Value,
    subject: String,
    html_body: String,
    tranche_size: i64,
    pause_seconds: i64,
    max_retries: i64,
    retry_delay: i64,
    scheduled_at: Option<String>,
}

fn emit(app: &AppHandle, id: i64) {
    let _ = app.emit("campaigns-changed", id);
}

fn log(db: &Db, id: i64, level: &str, message: &str) {
    if let Ok(c) = db.lock() {
        let _ = c.execute(
            "INSERT INTO log_entries(campaign_id,level,message) VALUES(?1,?2,?3)",
            params![id, level, message],
        );
    }
}

fn notify(app: &AppHandle, title: &str, body: &str) {
    if app.state::<Db>().get_setting("notifications", "1") == "1" {
        let _ = app.notification().builder().title(title).body(body).show();
    }
}

fn load(db: &Db, id: i64) -> Result<Campaign, String> {
    let c = db.lock()?;
    c.query_row(
        "SELECT status,smtp_server_id,smtp_snapshot,subject,html_body,tranche_size,pause_seconds,max_retries,retry_delay_seconds,scheduled_at \
         FROM campaigns WHERE id=?1",
        [id],
        |r| {
            let snapshot: String = r.get(2)?;
            Ok(Campaign {
                status: r.get(0)?,
                smtp_server_id: r.get(1)?,
                smtp_snapshot: serde_json::from_str(&snapshot).unwrap_or(serde_json::Value::Null),
                subject: r.get(3)?,
                html_body: r.get(4)?,
                tranche_size: r.get(5)?,
                pause_seconds: r.get(6)?,
                max_retries: r.get(7)?,
                retry_delay: r.get(8)?,
                scheduled_at: r.get(9)?,
            })
        },
    )
    .map_err(es)
}

fn set_status(db: &Db, id: i64, status: &str, reason: Option<&str>, completed: bool) {
    if let Ok(c) = db.lock() {
        let _ = c.execute(
            "UPDATE campaigns SET status=?1, auto_pause_reason=?2, \
             started_at=CASE WHEN ?1='running' AND started_at IS NULL THEN ?3 ELSE started_at END, \
             completed_at=CASE WHEN ?4=1 THEN ?3 ELSE completed_at END WHERE id=?5",
            params![status, reason, now(), completed as i64, id],
        );
    }
}

fn revert_processing(db: &Db, id: i64) {
    if let Ok(c) = db.lock() {
        let _ = c.execute("UPDATE send_items SET status='pending' WHERE campaign_id=?1 AND status='processing'", [id]);
    }
}

fn claim(db: &Db, id: i64, size: i64) -> Result<Vec<Item>, String> {
    let c = db.lock()?;
    let tx = c.unchecked_transaction().map_err(es)?;
    let items: Vec<Item> = {
        let mut st = tx
            .prepare("SELECT id,email,first_name,last_name,company,tags FROM send_items WHERE campaign_id=?1 AND status='pending' ORDER BY id LIMIT ?2")
            .map_err(es)?;
        let rows = st
            .query_map(params![id, size], |r| {
                Ok(Item {
                    id: r.get(0)?,
                    email: r.get(1)?,
                    first_name: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
                    last_name: r.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    company: r.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    tags: r.get::<_, Option<String>>(5)?.unwrap_or_default(),
                })
            })
            .map_err(es)?;
        rows.collect::<Result<Vec<_>, _>>().map_err(es)?
    };
    for it in &items {
        tx.execute("UPDATE send_items SET status='processing' WHERE id=?1", [it.id]).map_err(es)?;
    }
    tx.commit().map_err(es)?;
    Ok(items)
}

fn update_item(db: &Db, item: i64, status: &str, error: Option<&str>, attempts: i64, sent: bool) {
    if let Ok(c) = db.lock() {
        let _ = c.execute(
            "UPDATE send_items SET status=?1, last_error=?2, attempts=?3, sent_at=CASE WHEN ?4=1 THEN ?5 ELSE sent_at END WHERE id=?6",
            params![status, error, attempts, sent as i64, now(), item],
        );
    }
}

fn count_pending(db: &Db, id: i64) -> i64 {
    db.lock()
        .ok()
        .and_then(|c| {
            c.query_row("SELECT COUNT(*) FROM send_items WHERE campaign_id=?1 AND status='pending'", [id], |r| r.get(0)).ok()
        })
        .unwrap_or(0)
}

fn finalize(app: &AppHandle, id: i64, cancelled: bool) {
    let db = app.state::<Db>();
    let (sent, failed, name) = {
        let Ok(c) = db.lock() else { return };
        let _ = c.execute(
            "UPDATE send_items SET status='cancelled' WHERE campaign_id=?1 AND status IN ('pending','processing')",
            [id],
        );
        let sent: i64 = c
            .query_row("SELECT COUNT(*) FROM send_items WHERE campaign_id=?1 AND status='sent'", [id], |r| r.get(0))
            .unwrap_or(0);
        let failed: i64 = c
            .query_row(
                "SELECT COUNT(*) FROM send_items WHERE campaign_id=?1 AND status IN ('failed_temp','failed_perm')",
                [id],
                |r| r.get(0),
            )
            .unwrap_or(0);
        let name: String = c.query_row("SELECT name FROM campaigns WHERE id=?1", [id], |r| r.get(0)).unwrap_or_default();
        (sent, failed, name)
    };
    set_status(&db, id, if cancelled { "cancelled" } else { "completed" }, None, true);
    if cancelled {
        log(&db, id, "warning", &format!("Invio annullato: {sent} inviate, il resto è stato annullato"));
    } else {
        log(&db, id, "success", &format!("Invio completato: {sent} inviate, {failed} fallite"));
        notify(app, "Invio completato", &format!("«{name}»: {sent} inviate, {failed} fallite."));
    }
}

fn auto_pause(app: &AppHandle, id: i64, reason: &str) {
    let db = app.state::<Db>();
    revert_processing(&db, id);
    set_status(&db, id, "paused", Some(reason), false);
    log(&db, id, "critical", &format!("PAUSA AUTOMATICA: {reason}"));
    notify(app, "Invio in pausa", reason);
}

/// Attende `secs` secondi, interrompendosi subito se arriva una pausa o un annullamento.
async fn nap(flag: &AtomicU8, secs: f64) {
    let end = Instant::now() + Duration::from_secs_f64(secs.max(0.0));
    while flag.load(Ordering::Relaxed) == RUN && Instant::now() < end {
        let left = end.saturating_duration_since(Instant::now());
        tokio::time::sleep(left.min(Duration::from_millis(400))).await;
    }
}

// ---------------------------------------------------------------- controllo

pub fn start(app: &AppHandle, id: i64) {
    let mgr = app.state::<WorkerPool>();
    let flag = {
        let mut running = mgr.running.lock().unwrap();
        if running.contains_key(&id) {
            return;
        }
        let flag = Arc::new(AtomicU8::new(RUN));
        running.insert(id, flag.clone());
        flag
    };
    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        if let Err(err) = run(&app2, id, &flag).await {
            auto_pause(&app2, id, &format!("Errore interno: {err}"));
        }
        app2.state::<WorkerPool>().running.lock().unwrap().remove(&id);
        emit(&app2, id);
    });
    emit(app, id);
}

pub fn pause(app: &AppHandle, id: i64) -> Result<(), String> {
    let mgr = app.state::<WorkerPool>();
    let flag = mgr.running.lock().unwrap().get(&id).cloned();
    match flag {
        Some(f) => f.store(PAUSE, Ordering::Relaxed),
        None => {
            let db = app.state::<Db>();
            set_status(&db, id, "paused", Some("Messa in pausa"), false);
            log(&db, id, "info", "Invio messo in pausa");
        }
    }
    emit(app, id);
    Ok(())
}

pub fn resume(app: &AppHandle, id: i64) -> Result<(), String> {
    let db = app.state::<Db>();
    let status = load(&db, id)?.status;
    if status != "paused" {
        return Err("Solo un invio in pausa può essere ripreso".into());
    }
    set_status(&db, id, "running", None, false);
    log(&db, id, "info", "Invio ripreso");
    start(app, id);
    Ok(())
}

pub fn cancel(app: &AppHandle, id: i64) -> Result<(), String> {
    let mgr = app.state::<WorkerPool>();
    let flag = mgr.running.lock().unwrap().get(&id).cloned();
    match flag {
        Some(f) => f.store(CANCEL, Ordering::Relaxed),
        None => {
            let db = app.state::<Db>();
            let status = load(&db, id)?.status;
            if matches!(status.as_str(), "running" | "paused" | "scheduled") {
                finalize(app, id, true);
            }
        }
    }
    emit(app, id);
    Ok(())
}

/// All'avvio: gli invii interrotti dalla chiusura dell'app riprendono da soli.
pub fn bootstrap(app: &AppHandle) {
    let db = app.state::<Db>();
    let ids: Vec<i64> = {
        let Ok(c) = db.lock() else { return };
        let _ = c.execute("UPDATE send_items SET status='pending' WHERE status='processing'", []);
        let Ok(mut st) = c.prepare("SELECT id FROM campaigns WHERE status IN ('running','scheduled')") else { return };
        let Ok(rows) = st.query_map([], |r| r.get::<_, i64>(0)) else { return };
        rows.flatten().collect()
    };
    for id in ids {
        start(app, id);
    }
}

// ---------------------------------------------------------------- esecuzione

async fn run(app: &AppHandle, id: i64, flag: &Arc<AtomicU8>) -> Result<(), String> {
    let db = app.state::<Db>();
    let mut camp = load(&db, id)?;

    // attesa della partenza programmata
    while camp.status == "scheduled" && flag.load(Ordering::Relaxed) == RUN {
        let due = camp
            .scheduled_at
            .as_deref()
            .and_then(|s| NaiveDateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S").ok())
            .map(|t| t <= chrono::Local::now().naive_local())
            .unwrap_or(true);
        if due {
            set_status(&db, id, "running", None, false);
            log(&db, id, "info", "Partenza dell'invio programmato");
            camp = load(&db, id)?;
            break;
        }
        tokio::time::sleep(Duration::from_secs(1)).await;
    }

    match flag.load(Ordering::Relaxed) {
        CANCEL => {
            finalize(app, id, true);
            return Ok(());
        }
        PAUSE => {
            if camp.status == "scheduled" {
                set_status(&db, id, "paused", Some("Messa in pausa"), false);
            }
            return Ok(());
        }
        _ => {}
    }
    if camp.status != "running" {
        return Ok(());
    }
    set_status(&db, id, "running", None, false);
    emit(app, id);

    let server_id = camp.smtp_server_id.ok_or("Il server SMTP è stato eliminato")?;
    let cfg = load_cfg(&db, server_id)?;
    let transport = mailer::build_transport(&cfg)?;
    let threshold: i64 = db.get_setting("error_threshold", "8").parse().unwrap_or(8);
    let rate_limit = camp.smtp_snapshot.get("rate_limit").and_then(|v| v.as_i64()).filter(|v| *v > 0);
    let rate_interval = rate_limit.map(|r| 3600.0 / r as f64).unwrap_or(0.0);
    let mut consecutive_errors: i64 = 0;

    'outer: while flag.load(Ordering::Relaxed) == RUN {
        let items = claim(&db, id, camp.tranche_size)?;
        if items.is_empty() {
            break;
        }
        for item in items {
            if flag.load(Ordering::Relaxed) != RUN {
                break 'outer;
            }
            let who = Recipient {
                first_name: item.first_name.clone(),
                last_name: item.last_name.clone(),
                email: item.email.clone(),
                company: item.company.clone(),
                tags: item.tags.clone(),
            };
            let subject = templating::render_subject(&camp.subject, &who);
            let html = templating::render_html(&camp.html_body, &who);
            let (subject, html) = match (subject, html) {
                (Ok(s), Ok(h)) => (s, h),
                (s, h) => {
                    let why = s.err().or(h.err()).unwrap_or_default();
                    update_item(&db, item.id, "failed_perm", Some(&format!("errore nel template: {why}")), 1, false);
                    consecutive_errors += 1;
                    continue;
                }
            };
            let message = match mailer::build_message(&cfg, &item.email, &subject, &html) {
                Ok(m) => m,
                Err(e) => {
                    update_item(&db, item.id, "failed_perm", Some(&e), 1, false);
                    log(&db, id, "error", &format!("{}: {e}", item.email));
                    consecutive_errors += 1;
                    continue;
                }
            };

            let mut attempts: i64 = 0;
            loop {
                match mailer::send(&transport, message.clone()).await {
                    Ok(()) => {
                        update_item(&db, item.id, "sent", None, attempts + 1, true);
                        consecutive_errors = 0;
                        break;
                    }
                    Err(err) => {
                        attempts += 1;
                        let (kind, detail) = mailer::classify(&err);
                        match kind {
                            ErrKind::Auth => {
                                update_item(&db, item.id, "failed_perm", Some(&detail), attempts, false);
                                auto_pause(app, id, &format!("Credenziali SMTP rifiutate: {detail}"));
                                return Ok(());
                            }
                            ErrKind::Perm => {
                                update_item(&db, item.id, "failed_perm", Some(&detail), attempts, false);
                                log(&db, id, "error", &format!("{}: {detail}", item.email));
                                consecutive_errors += 1;
                                break;
                            }
                            ErrKind::Temp => {
                                if attempts > camp.max_retries {
                                    update_item(&db, item.id, "failed_temp", Some(&detail), attempts, false);
                                    log(&db, id, "error", &format!("{}: {detail}", item.email));
                                    consecutive_errors += 1;
                                    break;
                                }
                                log(
                                    &db, id, "warning",
                                    &format!("{}: nuovo tentativo tra {}s ({}/{})", item.email, camp.retry_delay, attempts, camp.max_retries),
                                );
                                update_item(&db, item.id, "processing", Some(&detail), attempts, false);
                                nap(flag, camp.retry_delay as f64).await;
                                if flag.load(Ordering::Relaxed) != RUN {
                                    update_item(&db, item.id, "pending", Some(&detail), attempts, false);
                                    break 'outer;
                                }
                            }
                        }
                    }
                }
            }
            emit(app, id);
            if consecutive_errors >= threshold {
                auto_pause(app, id, &format!("{consecutive_errors} errori consecutivi"));
                return Ok(());
            }
            if rate_interval > 0.0 {
                nap(flag, rate_interval).await;
            }
        }
        if count_pending(&db, id) > 0 && flag.load(Ordering::Relaxed) == RUN {
            log(&db, id, "info", &format!("Tranche completata · pausa di {}s", camp.pause_seconds));
            nap(flag, camp.pause_seconds as f64).await;
        }
    }

    match flag.load(Ordering::Relaxed) {
        CANCEL => finalize(app, id, true),
        PAUSE => {
            revert_processing(&db, id);
            set_status(&db, id, "paused", Some("Messa in pausa"), false);
            log(&db, id, "info", "Invio messo in pausa");
        }
        _ => finalize(app, id, false),
    }
    Ok(())
}
