# ilPostino Desktop

Versione desktop di ilPostino: newsletter spedite dai tuoi server SMTP, tutto in locale.
Costruita con **Tauri 2** (Rust) e **React + TypeScript**.

## Requisiti

- Node.js 20+
- Rust (stable) e, su Windows, i *Visual Studio Build Tools* con il carico di lavoro «Sviluppo di applicazioni desktop con C++»
- WebView2 (già presente in Windows 11)

## Sviluppo

```bash
npm install
npm run tauri dev
```

## Build

```bash
npm run tauri build
```

L'installer finisce in `src-tauri/target/release/bundle/`.

## Struttura

| Percorso | Contenuto |
|---|---|
| `src/` | Interfaccia React (`pages/` una per sezione, `lib/api.ts` i comandi verso Rust) |
| `src-tauri/src/db.rs` | SQLite (rusqlite) e migrazioni |
| `src-tauri/src/worker.rs` | Invio a tranche: pausa, ripresa, nuovi tentativi, pausa automatica |
| `src-tauri/src/mailer.rs` | SMTP con lettre, classificazione errori, diagnostica |
| `src-tauri/src/templating.rs` | Template con sintassi Jinja2 (minijinja) |
| `src-tauri/src/secrets.rs` | Password SMTP nel portachiavi del sistema |
| `src-tauri/src/commands/` | Comandi esposti all'interfaccia |

## Dati

Il database è `ilpostino.db` nella cartella dati dell'app (Impostazioni → «Apri cartella»).
Le password SMTP non stanno nel database: sono nel portachiavi del sistema operativo.
«Importa da un file…» unisce un backup o il vecchio `ilpostino.db` della versione Python.
