//! Motore template (sintassi Jinja2 via minijinja) e variabili dei destinatari.

use minijinja::{AutoEscape, Environment, UndefinedBehavior};
use serde::Serialize;

pub const KNOWN_VARIABLES: [&str; 5] = ["first_name", "last_name", "email", "company", "tags"];

#[derive(Serialize, Clone, Default)]
pub struct Recipient {
    pub first_name: String,
    pub last_name: String,
    pub email: String,
    pub company: String,
    pub tags: String,
}

impl Recipient {
    pub fn sample() -> Self {
        Recipient {
            first_name: "Luca".into(),
            last_name: "Rossi".into(),
            email: "luca.rossi@example.com".into(),
            company: "Acme Srl".into(),
            tags: "clienti, vip".into(),
        }
    }
}

fn env(escape: bool) -> Environment<'static> {
    let mut e = Environment::new();
    e.set_undefined_behavior(UndefinedBehavior::Strict);
    if escape {
        e.set_auto_escape_callback(|_| AutoEscape::Html);
    }
    e
}

/// Corpo HTML: i valori dei contatti vengono "escapati".
pub fn render_html(src: &str, who: &Recipient) -> Result<String, String> {
    env(true).render_str(src, who).map_err(|e| e.to_string())
}

/// Oggetto: testo semplice, nessun escape.
pub fn render_subject(src: &str, who: &Recipient) -> Result<String, String> {
    env(false).render_str(src, who).map_err(|e| e.to_string())
}

pub fn check_syntax(src: &str) -> Result<(), String> {
    env(false).template_from_str(src).map(|_| ()).map_err(|e| e.to_string())
}

/// Variabili usate nel template che non esistono nei contatti.
pub fn unknown_variables(src: &str) -> Vec<String> {
    let e = env(false);
    let Ok(t) = e.template_from_str(src) else { return vec![] };
    let mut v: Vec<String> = t
        .undeclared_variables(false)
        .into_iter()
        .filter(|name| !KNOWN_VARIABLES.contains(&name.as_str()))
        .collect();
    v.sort();
    v
}
