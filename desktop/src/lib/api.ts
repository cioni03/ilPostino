import { invoke } from "@tauri-apps/api/core";

// ---------------------------------------------------------------- tipi

export interface SmtpServer {
  id: number; name: string; host: string; port: number; security: "tls" | "ssl" | "none";
  username: string | null; has_password: boolean; sender_email: string; sender_name: string | null;
  reply_to: string | null; rate_limit: number | null; active: boolean;
}
export interface SmtpInput {
  id?: number | null; name: string; host: string; port: number; security: string; username: string | null;
  password: string | null; sender_email: string; sender_name: string | null; reply_to: string | null;
  rate_limit: number | null; active: boolean;
}
export interface Step { name: string; ok: boolean; ms: number; detail: string; hint: string }
export interface Diagnosis { ok: boolean; summary: string; steps: Step[] }

export interface Group { id: number; name: string; total: number }
export interface Contact {
  id: number; email: string; first_name: string; last_name: string; company: string; groups: string; group_ids: number[];
}
export interface ContactPage { rows: Contact[]; total: number }
export interface ContactInput {
  id?: number | null; email: string; first_name: string; last_name: string; company: string;
  group_ids: number[]; new_group_name: string | null;
}
export interface ImportPreview {
  new: number; existing: number; invalid: number;
  sample: { email: string; first_name: string; last_name: string; status: "new" | "existing" | "invalid" }[];
}
export interface ImportResult { created: number; existing: number; invalid: number; group: string }

export interface Template { id: number; name: string; subject: string; html_body: string; updated_at: string }
export interface RenderOutput { subject: string; html: string; error: string | null; unknown: string[] }

export type CampaignStatus = "running" | "paused" | "scheduled" | "completed" | "cancelled";
export interface Campaign {
  id: number; name: string; status: CampaignStatus; group_name: string; template_name: string; smtp_name: string;
  total_count: number; tranche_size: number; pause_seconds: number; scheduled_at: string | null;
  started_at: string | null; completed_at: string | null; created_at: string; auto_pause_reason: string | null;
  sent: number; failed: number; pending: number;
}
export interface CampaignInput {
  name: string; smtp_server_id: number; template_id: number | null; template_name: string; subject: string;
  html_body: string; group_id: number; tranche_size: number; pause_seconds: number; max_retries: number;
  retry_delay_seconds: number; scheduled_at: string | null;
}
export interface ItemRow { email: string; name: string; status: string; attempts: number; last_error: string; sent_at: string }
export interface LogRow { id: number; level: string; message: string; created_at: string }
export interface Overview { contacts: number; groups: number; templates: number; smtp_active: number }
export interface DbInfo { path: string; size_bytes: number; last_backup: string }
export interface ImportSummary { groups: number; contacts: number; templates: number; servers: number }

// ---------------------------------------------------------------- comandi

export const api = {
  smtpList: () => invoke<SmtpServer[]>("smtp_list"),
  smtpSave: (input: SmtpInput) => invoke<number>("smtp_save", { input }),
  smtpDelete: (id: number) => invoke<void>("smtp_delete", { id }),
  smtpSetActive: (id: number, active: boolean) => invoke<void>("smtp_set_active", { id, active }),
  smtpDiagnose: (id: number) => invoke<Diagnosis>("smtp_diagnose", { id }),
  smtpSendTest: (input: { smtp_id: number; to: string; subject: string; html: string }) =>
    invoke<void>("smtp_send_test", { input }),

  groupsList: () => invoke<Group[]>("groups_list"),
  groupCreate: (name: string) => invoke<number>("group_create", { name }),
  groupDelete: (id: number) => invoke<void>("group_delete", { id }),
  contactsList: (query: { group_id: number | null; search: string; page: number; per_page: number }) =>
    invoke<ContactPage>("contacts_list", { query }),
  contactSave: (input: ContactInput) => invoke<number>("contact_save", { input }),
  contactDelete: (id: number) => invoke<void>("contact_delete", { id }),
  importPreview: (text: string) => invoke<ImportPreview>("contacts_import_preview", { text }),
  importContacts: (input: { text: string; group_id: number | null; new_group_name: string | null }) =>
    invoke<ImportResult>("contacts_import", { input }),
  contactsExportCsv: () => invoke<string>("contacts_export_csv"),

  templatesList: () => invoke<Template[]>("templates_list"),
  templateSave: (input: { id?: number | null; name: string; subject: string; html_body: string }) =>
    invoke<number>("template_save", { input }),
  templateDuplicate: (id: number) => invoke<number>("template_duplicate", { id }),
  templateDelete: (id: number) => invoke<void>("template_delete", { id }),
  templateRender: (input: { subject: string; html_body: string; contact_id?: number | null; group_id?: number | null }) =>
    invoke<RenderOutput>("template_render", { input }),

  campaignsList: () => invoke<Campaign[]>("campaigns_list"),
  campaignCreate: (input: CampaignInput) => invoke<number>("campaign_create", { input }),
  campaignPause: (id: number) => invoke<void>("campaign_pause", { id }),
  campaignResume: (id: number) => invoke<void>("campaign_resume", { id }),
  campaignCancel: (id: number) => invoke<void>("campaign_cancel", { id }),
  campaignDelete: (id: number) => invoke<void>("campaign_delete", { id }),
  campaignItems: (query: { campaign_id: number; status: string | null; page: number; per_page: number }) =>
    invoke<{ rows: ItemRow[]; total: number }>("campaign_items", { query }),
  campaignLogs: (campaignId: number) => invoke<LogRow[]>("campaign_logs", { campaignId, limit: 300 }),
  campaignExportCsv: (id: number) => invoke<string>("campaign_export_csv", { id }),

  overview: () => invoke<Overview>("overview"),
  settingsGet: (key: string, def: string) => invoke<string>("settings_get", { key, default: def }),
  settingsSet: (key: string, value: string) => invoke<void>("settings_set", { key, value }),
  dbInfo: () => invoke<DbInfo>("db_info"),
  backupDatabase: (dest: string) => invoke<void>("backup_database", { dest }),
  importDatabase: (src: string) => invoke<ImportSummary>("import_database", { src }),
  writeTextFile: (path: string, contents: string) => invoke<void>("write_text_file", { path, contents }),
  readTextFile: (path: string) => invoke<string>("read_text_file", { path }),
  openDataFolder: () => invoke<void>("open_data_folder"),
};

export function errorText(e: unknown): string {
  return typeof e === "string" ? e : e instanceof Error ? e.message : JSON.stringify(e);
}
