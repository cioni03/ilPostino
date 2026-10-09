//! Panoramica, impostazioni, backup, importazione da un altro database e barra di sistema.

use rusqlite::{params, OptionalExtension};
use serde::Serialize;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, State};

use crate::db::{es, Db};
use crate::secrets;

#[derive(Serialize)]
pub struct Overview {
    pub contacts: i64,
    pub groups: i64,
    pub templates: i64,
    pub smtp_active: i64,
}

#[tauri::command]
pub fn overview(db: State<Db>) -> Result<Overview, String> {
    let c = db.lock()?;
    let n = |sql: &str| c.query_row(sql, [], |r| r.get::<_, i64>(0)).map_err(es);
    Ok(Overview {
        contacts: n("SELECT COUNT(*) FROM contacts")?,
        groups: n("SELECT COUNT(*) FROM groups")?,
        templates: n("SELECT COUNT(*) FROM email_templates")?,
        smtp_active: n("SELECT COUNT(*) FROM smtp_servers WHERE active=1")?,
    })
}

#[tauri::command]
pub fn settings_get(db: State<Db>, key: String, default: String) -> String {
    db.get_setting(&key, &default)
}

#[tauri::command]
pub fn settings_set(db: State<Db>, key: String, value: String) -> Result<(), String> {
    db.set_setting(&key, &value)
}

#[derive(Serialize)]
pub struct DbInfo {
    pub path: String,
    pub size_bytes: u64,
    pub last_backup: String,
}

#[tauri::command]
pub fn db_info(db: State<Db>) -> DbInfo {
    DbInfo {
        path: db.path.to_string_lossy().to_string(),
        size_bytes: std::fs::metadata(&db.path).map(|m| m.len()).unwrap_or(0),
        last_backup: db.get_setting("last_backup", ""),
    }
}

#[tauri::command]
pub fn backup_database(db: State<Db>, dest: String) -> Result<(), String> {
    let _ = std::fs::remove_file(&dest); // VACUUM INTO richiede che il file non esista
    {
        let c = db.lock()?;
        c.execute("VACUUM INTO ?1", [&dest]).map_err(es)?;
    }
    db.set_setting("last_backup", &crate::db::now())
}

#[derive(Serialize)]
pub struct ImportSummary {
    pub groups: i64,
    pub contacts: i64,
    pub templates: i64,
    pub servers: i64,
}

/// Unisce i dati di un altro file ilpostino.db (backup o vecchia versione Python): nulla viene sovrascritto.
#[tauri::command]
pub fn import_database(db: State<Db>, src: String) -> Result<ImportSummary, String> {
    let c = db.lock()?;
    c.execute("ATTACH DATABASE ?1 AS old", [&src]).map_err(|e| format!("File non leggibile: {e}"))?;
    let result = (|| -> Result<ImportSummary, String> {
        let before = |sql: &str| c.query_row(sql, [], |r| r.get::<_, i64>(0)).map_err(es);
        let (g0, c0, t0) = (
            before("SELECT COUNT(*) FROM groups")?,
            before("SELECT COUNT(*) FROM contacts")?,
            before("SELECT COUNT(*) FROM email_templates")?,
        );
        let has = |t: &str| -> bool {
            c.query_row("SELECT 1 FROM old.sqlite_master WHERE type='table' AND name=?1", [t], |r| r.get::<_, i64>(0))
                .optional()
                .ok()
                .flatten()
                .is_some()
        };
        if !has("contacts") && !has("email_templates") && !has("smtp_servers") {
            return Err("Il file non sembra un database di ilPostino".into());
        }
        let tx = c.unchecked_transaction().map_err(es)?;
        if has("groups") {
            tx.execute("INSERT OR IGNORE INTO groups(name) SELECT name FROM old.groups", []).map_err(es)?;
        }
        if has("contacts") {
            tx.execute(
                "INSERT OR IGNORE INTO contacts(email,first_name,last_name,company,tags) \
                 SELECT email,first_name,last_name,company,tags FROM old.contacts",
                [],
            )
            .map_err(es)?;
        }
        if has("contact_group") {
            tx.execute(
                "INSERT OR IGNORE INTO contact_group(contact_id,group_id) \
                 SELECT nc.id, ng.id FROM old.contact_group ocg \
                 JOIN old.contacts oc ON oc.id=ocg.contact_id JOIN old.groups og ON og.id=ocg.group_id \
                 JOIN contacts nc ON nc.email=oc.email JOIN groups ng ON ng.name=og.name",
                [],
            )
            .map_err(es)?;
        }
        if has("email_templates") {
            tx.execute(
                "INSERT INTO email_templates(name,subject,html_body) SELECT name,subject,html_body FROM old.email_templates ot \
                 WHERE NOT EXISTS (SELECT 1 FROM email_templates t WHERE t.name=ot.name AND t.html_body=ot.html_body)",
                [],
            )
            .map_err(es)?;
        }
        let mut servers = 0;
        if has("smtp_servers") {
            let rows: Vec<(String, String, i64, String, Option<String>, Option<String>, String, Option<String>, Option<String>, Option<i64>)> = {
                let mut st = tx
                    .prepare(
                        "SELECT name,host,port,security,username,password,sender_email,sender_name,reply_to,rate_limit_emails_per_hour \
                         FROM old.smtp_servers",
                    )
                    .map_err(es)?;
                let it = st
                    .query_map([], |r| {
                        Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?, r.get(5)?, r.get(6)?, r.get(7)?, r.get(8)?, r.get(9)?))
                    })
                    .map_err(es)?;
                it.collect::<Result<Vec<_>, _>>().map_err(es)?
            };
            for (name, host, port, security, username, password, sender, sname, reply, rate) in rows {
                let exists: Option<i64> = tx
                    .query_row(
                        "SELECT id FROM smtp_servers WHERE host=?1 AND coalesce(username,'')=coalesce(?2,'') AND sender_email=?3",
                        params![host, username, sender],
                        |r| r.get(0),
                    )
                    .optional()
                    .map_err(es)?;
                if exists.is_some() {
                    continue;
                }
                tx.execute(
                    "INSERT INTO smtp_servers(name,host,port,security,username,sender_email,sender_name,reply_to,rate_limit_emails_per_hour,active) \
                     VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,0)",
                    params![name, host, port, security, username, sender, sname, reply, rate],
                )
                .map_err(es)?;
                let new_id = tx.last_insert_rowid();
                if let Some(pw) = password.filter(|p| !p.is_empty()) {
                    secrets::set(new_id, &pw)?;
                }
                servers += 1;
            }
        }
        tx.commit().map_err(es)?;
        Ok(ImportSummary {
            groups: before("SELECT COUNT(*) FROM groups")? - g0,
            contacts: before("SELECT COUNT(*) FROM contacts")? - c0,
            templates: before("SELECT COUNT(*) FROM email_templates")? - t0,
            servers,
        })
    })();
    let _ = c.execute("DETACH DATABASE old", []);
    result
}

#[tauri::command]
pub fn write_text_file(path: String, contents: String) -> Result<(), String> {
    std::fs::write(path, contents).map_err(es)
}

#[tauri::command]
pub fn read_text_file(path: String) -> Result<String, String> {
    let bytes = std::fs::read(&path).map_err(es)?;
    if bytes.len() > 20 * 1024 * 1024 {
        return Err("Il file è troppo grande (massimo 20 MB)".into());
    }
    Ok(String::from_utf8_lossy(&bytes).trim_start_matches('\u{feff}').to_string())
}

#[tauri::command]
pub fn open_data_folder(db: State<Db>) -> Result<(), String> {
    let dir = db.path.parent().ok_or("Cartella non trovata")?.to_path_buf();
    #[cfg(windows)]
    std::process::Command::new("explorer").arg(&dir).spawn().map_err(es)?;
    #[cfg(target_os = "macos")]
    std::process::Command::new("open").arg(&dir).spawn().map_err(es)?;
    #[cfg(target_os = "linux")]
    std::process::Command::new("xdg-open").arg(&dir).spawn().map_err(es)?;
    Ok(())
}

// ---------------------------------------------------------------- barra di sistema

fn show_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

pub fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Apri ilPostino", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Esci", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quit])?;
    let mut builder = TrayIconBuilder::new().tooltip("ilPostino").menu(&menu).show_menu_on_left_click(false);
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                show_main(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}
