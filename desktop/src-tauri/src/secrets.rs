//! Password SMTP nel portachiavi del sistema operativo (mai nel database).

use keyring::Entry;

const SERVICE: &str = "ilPostino";

fn entry(id: i64) -> Result<Entry, String> {
    Entry::new(SERVICE, &format!("smtp-{id}")).map_err(|e| e.to_string())
}

pub fn set(id: i64, password: &str) -> Result<(), String> {
    entry(id)?.set_password(password).map_err(|e| e.to_string())
}

pub fn get(id: i64) -> Option<String> {
    entry(id).ok()?.get_password().ok()
}

pub fn delete(id: i64) {
    if let Ok(e) = entry(id) {
        let _ = e.delete_credential();
    }
}
