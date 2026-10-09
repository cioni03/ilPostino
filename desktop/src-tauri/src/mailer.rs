//! Invio email via lettre, classificazione degli errori e diagnostica della connessione.

use lettre::message::{Mailbox, MultiPart};
use lettre::transport::smtp::authentication::Credentials;
use lettre::transport::smtp::Error as SmtpError;
use lettre::{Address, AsyncSmtpTransport, AsyncTransport, Message, Tokio1Executor};
use regex::Regex;
use serde::Serialize;
use std::time::{Duration, Instant};

use crate::db::es;

pub type Transport = AsyncSmtpTransport<Tokio1Executor>;

#[derive(Clone, Debug)]
pub struct SmtpCfg {
    pub host: String,
    pub port: u16,
    pub security: String, // tls (STARTTLS) | ssl | none
    pub username: Option<String>,
    pub password: Option<String>,
    pub sender_email: String,
    pub sender_name: Option<String>,
    pub reply_to: Option<String>,
}

pub fn build_transport(cfg: &SmtpCfg) -> Result<Transport, String> {
    let builder = match cfg.security.as_str() {
        "ssl" => Transport::relay(&cfg.host).map_err(es)?,
        "none" => Transport::builder_dangerous(&cfg.host),
        _ => Transport::starttls_relay(&cfg.host).map_err(es)?,
    };
    let mut builder = builder.port(cfg.port).timeout(Some(Duration::from_secs(20)));
    if let Some(user) = cfg.username.as_ref().filter(|u| !u.is_empty()) {
        builder = builder.credentials(Credentials::new(user.clone(), cfg.password.clone().unwrap_or_default()));
    }
    Ok(builder.build())
}

pub fn html_to_text(html: &str) -> String {
    let br = Regex::new(r"(?i)<br\s*/?>").unwrap();
    let p = Regex::new(r"(?i)</p\s*>").unwrap();
    let tag = Regex::new(r"<[^>]+>").unwrap();
    let text = br.replace_all(html, "\n");
    let text = p.replace_all(&text, "\n\n");
    let text = tag.replace_all(&text, "");
    let text = text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"");
    let lines: Vec<&str> = text.lines().map(|l| l.trim()).collect();
    let joined = lines.join("\n").trim().to_string();
    if joined.is_empty() { " ".to_string() } else { joined }
}

pub fn build_message(cfg: &SmtpCfg, to: &str, subject: &str, html: &str) -> Result<Message, String> {
    let from_addr: Address = cfg.sender_email.parse().map_err(|_| format!("Mittente non valido: {}", cfg.sender_email))?;
    let to_addr: Address = to.parse().map_err(|_| format!("Destinatario non valido: {to}"))?;
    let name = cfg.sender_name.clone().filter(|n| !n.is_empty());
    let mut builder = Message::builder()
        .from(Mailbox::new(name, from_addr))
        .to(Mailbox::new(None, to_addr))
        .subject(subject);
    if let Some(reply) = cfg.reply_to.as_ref().filter(|r| !r.is_empty()) {
        let addr: Address = reply.parse().map_err(|_| format!("Reply-To non valido: {reply}"))?;
        builder = builder.reply_to(Mailbox::new(None, addr));
    }
    builder
        .multipart(MultiPart::alternative_plain_html(html_to_text(html), html.to_string()))
        .map_err(es)
}

#[derive(Debug, PartialEq, Clone, Copy)]
pub enum ErrKind {
    Auth,
    Perm,
    Temp,
}

pub fn classify(err: &SmtpError) -> (ErrKind, String) {
    let msg = err.to_string();
    let low = msg.to_lowercase();
    if low.contains("authentication") || low.contains("535") || low.contains("534") || low.contains("credentials") {
        return (ErrKind::Auth, format!("Credenziali rifiutate dal server: {msg}"));
    }
    if low.contains("certificate") || low.contains("tls error") || low.contains("handshake") {
        return (ErrKind::Perm, format!("Errore TLS/certificato: {msg}"));
    }
    if low.contains("timed out") || low.contains("timeout") {
        return (ErrKind::Temp, "Timeout: il server non ha risposto in tempo".to_string());
    }
    if err.is_permanent() {
        return (ErrKind::Perm, format!("Rifiutata dal server: {msg}"));
    }
    (ErrKind::Temp, format!("Errore temporaneo: {msg}"))
}

pub async fn send(transport: &Transport, msg: Message) -> Result<(), SmtpError> {
    transport.send(msg).await.map(|_| ())
}

// ---------------------------------------------------------------- diagnostica

#[derive(Serialize)]
pub struct Step {
    pub name: String,
    pub ok: bool,
    pub ms: u64,
    pub detail: String,
    pub hint: String,
}

#[derive(Serialize)]
pub struct Diagnosis {
    pub ok: bool,
    pub summary: String,
    pub steps: Vec<Step>,
}

fn step(name: &str, ok: bool, started: Instant, detail: String, hint: &str) -> Step {
    Step {
        name: name.to_string(),
        ok,
        ms: started.elapsed().as_millis() as u64,
        detail,
        hint: if ok { String::new() } else { hint.to_string() },
    }
}

pub async fn diagnose(cfg: &SmtpCfg) -> Diagnosis {
    let mut steps = Vec::new();

    let t = Instant::now();
    let sender_ok = crate::db::valid_email(&cfg.sender_email);
    steps.push(step("Mittente", sender_ok, t, cfg.sender_email.clone(), "L'indirizzo del mittente non è un'email valida."));
    if !sender_ok {
        return Diagnosis { ok: false, summary: "Il mittente non è valido.".into(), steps };
    }

    let t = Instant::now();
    let addr = (cfg.host.as_str(), cfg.port);
    match tokio::time::timeout(Duration::from_secs(5), tokio::net::lookup_host(addr)).await {
        Ok(Ok(_)) => steps.push(step("Risoluzione DNS", true, t, format!("{} risolto", cfg.host), "")),
        Ok(Err(e)) => {
            steps.push(step("Risoluzione DNS", false, t, e.to_string(), "Controlla il nome host: potrebbe essere errato o non raggiungibile dalla tua rete."));
            return Diagnosis { ok: false, summary: "Impossibile risolvere il nome host.".into(), steps };
        }
        Err(_) => {
            steps.push(step("Risoluzione DNS", false, t, "Timeout".into(), "Controlla la connessione internet."));
            return Diagnosis { ok: false, summary: "Impossibile risolvere il nome host.".into(), steps };
        }
    }

    let t = Instant::now();
    match tokio::time::timeout(Duration::from_secs(8), tokio::net::TcpStream::connect(addr)).await {
        Ok(Ok(_)) => steps.push(step("Connessione", true, t, format!("Connesso a {}:{}", cfg.host, cfg.port), "")),
        Ok(Err(e)) => {
            steps.push(step("Connessione", false, t, e.to_string(), "Controlla la porta e che firewall o antivirus non blocchino la connessione in uscita."));
            return Diagnosis { ok: false, summary: "Connessione al server non riuscita.".into(), steps };
        }
        Err(_) => {
            steps.push(step("Connessione", false, t, "Timeout".into(), "Controlla la porta e il firewall."));
            return Diagnosis { ok: false, summary: "Connessione al server non riuscita.".into(), steps };
        }
    }

    let t = Instant::now();
    let transport = match build_transport(cfg) {
        Ok(tr) => tr,
        Err(e) => {
            steps.push(step("Sicurezza", false, t, e, "Controlla la modalità di sicurezza scelta."));
            return Diagnosis { ok: false, summary: "Configurazione non valida.".into(), steps };
        }
    };
    match transport.test_connection().await {
        Ok(true) => {
            let detail = if cfg.username.as_deref().unwrap_or("").is_empty() {
                "Canale stabilito, accesso non richiesto".to_string()
            } else {
                format!("Accesso riuscito come {}", cfg.username.clone().unwrap_or_default())
            };
            steps.push(step("Sicurezza e accesso", true, t, detail, ""));
            Diagnosis { ok: true, summary: "Tutto a posto: il server è pronto all'invio.".into(), steps }
        }
        Ok(false) => {
            steps.push(step("Sicurezza e accesso", false, t, "Il server ha chiuso la sessione".into(), "Possibili limiti del provider."));
            Diagnosis { ok: false, summary: "Il server non ha accettato la sessione.".into(), steps }
        }
        Err(e) => {
            let (kind, detail) = classify(&e);
            let (hint, summary) = match kind {
                ErrKind::Auth => (
                    "Utente o password errati. Con Gmail e Outlook serve una «password per app».",
                    "Credenziali rifiutate.",
                ),
                _ => (
                    "Il server potrebbe non supportare questa modalità di sicurezza: prova a cambiare porta (465 o 587).",
                    "Negoziazione sicura non riuscita.",
                ),
            };
            steps.push(step("Sicurezza e accesso", false, t, detail, hint));
            Diagnosis { ok: false, summary: summary.into(), steps }
        }
    }
}
