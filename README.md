<p align="center">
  <img src="app/ilPostino_icon.png" width="140" alt="ilPostino">
</p>

<h1 align="center">ilPostino</h1>

<p align="center">
  <a href="#what-it-does"><img src="https://img.shields.io/badge/Privacy-Zero%20Data%20Collection-16a34a?style=for-the-badge" alt="Privacy - Zero Data Collection"></a>
  <a href="#your-data"><img src="https://img.shields.io/badge/Hosting-100%25%20Local-0F60F9?style=for-the-badge" alt="Hosting - 100% Local"></a>
  <a href="#requirements"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="#your-data"><img src="https://img.shields.io/badge/Database-SQLite-475569?style=for-the-badge&logo=sqlite&logoColor=white" alt="Database - SQLite"></a>
</p>

<p align="center">
A small local app for managing your newsletters and send it from your own SMTP accounts. 
Everything runs on your computer and all your data stays in a local database — nothing is sent to any external service.
</p>

## What it does

- **Contacts & groups** — keep all your recipients organized in groups.
  Every contact belongs to at least one group, and you can add a new group on
  the fly while creating a contact. You can also import a list of contacts by
  simply pasting it.
- **Email templates** — write your newsletter once, save it as a template and
  reuse it. Templates support personalized placeholders (first name, company,
  and more) that are filled in for each recipient.
- **SMTP servers** — configure one or more of your own mail accounts. Each
  server can have its own sending limits, so you stay within what your
  provider allows.
- **Campaigns** — send a template to a whole group. Emails go out in small
  batches with pauses in between, so you don't overload your mail server.
  Failed deliveries are retried automatically, campaigns can be scheduled for
  later, and you can pause and resume them at any time.
- **Activity log** — follow each campaign as it runs: what was sent, what
  failed and why, for every single recipient.

## Requirements

- Python 3.12 or newer

## Installation

Open a terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

```bash
python run.py
```

## Run it

```bash
python run.py
```

The app starts and opens your browser at **http://127.0.0.1:8090**.
The first run creates the settings file and the database automatically —
there is nothing else to set up.

## Configuration

Settings live in the `.env` file (created on the first run from
`.env.example`). There you can change:

- the port the app runs on,
- whether the browser opens automatically on start,
- where the database file is stored.

## Your data

All your contacts, templates and campaign history are stored in a single
SQLite database file (by default `data/ilpostino.db`). To make a backup,
just copy that file while the app is closed.

## Note

This is a local tool for your own machine. It is not meant to be exposed to
the internet as a public website.
