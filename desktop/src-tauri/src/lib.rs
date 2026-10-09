mod commands;
mod db;
mod mailer;
mod secrets;
mod templating;
mod worker;

use commands::{campaigns, contacts, smtp, system, templates};
use tauri::{Manager, WindowEvent};

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.unminimize();
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            let dir = app.path().app_data_dir()?;
            let database = db::open(&dir.join("ilpostino.db"))?;
            app.manage(database);
            app.manage(worker::WorkerPool::default());
            system::setup_tray(app.handle())?;
            worker::bootstrap(app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let db = window.app_handle().state::<db::Db>();
                // con un invio attivo e l'opzione abilitata, la finestra si nasconde nella barra di sistema
                if db.get_setting("background", "1") == "1" && db.has_active_campaigns() {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            smtp::smtp_list,
            smtp::smtp_save,
            smtp::smtp_delete,
            smtp::smtp_set_active,
            smtp::smtp_diagnose,
            smtp::smtp_send_test,
            contacts::groups_list,
            contacts::group_create,
            contacts::group_delete,
            contacts::contacts_list,
            contacts::contact_save,
            contacts::contact_delete,
            contacts::contacts_import_preview,
            contacts::contacts_import,
            contacts::contacts_export_csv,
            templates::templates_list,
            templates::template_save,
            templates::template_duplicate,
            templates::template_delete,
            templates::template_render,
            campaigns::campaigns_list,
            campaigns::campaign_create,
            campaigns::campaign_pause,
            campaigns::campaign_resume,
            campaigns::campaign_cancel,
            campaigns::campaign_delete,
            campaigns::campaign_items,
            campaigns::campaign_logs,
            campaigns::campaign_export_csv,
            system::overview,
            system::settings_get,
            system::settings_set,
            system::db_info,
            system::backup_database,
            system::import_database,
            system::write_text_file,
            system::read_text_file,
            system::open_data_folder,
        ])
        .run(tauri::generate_context!())
        .expect("errore nell'avvio di ilPostino");
}
