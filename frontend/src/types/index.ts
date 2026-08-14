// Shared API types mirroring the backend Pydantic schemas.

export interface User {
  id: number
  name: string
  email: string
  created_at?: string
}

export interface GroupBrief {
  id: number
  name: string
}

export interface Contact {
  id: number
  user_id: number
  phone: string
  first_name: string | null
  last_name: string | null
  email: string | null
  company: string | null
  notes: string | null
  custom_fields: Record<string, string>
  groups: GroupBrief[]
  opted_out?: boolean
  created_at: string
  updated_at: string
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ContactGroup {
  id: number
  user_id: number
  name: string
  description: string | null
  created_at: string
  contact_count: number
}

export interface ContactGroupDetail extends ContactGroup {
  contact_ids: number[]
}

export interface MessageTemplate {
  id: number
  user_id: number
  name: string
  message: string
  created_at: string
  updated_at: string
}

export type CampaignStatus =
  | 'DRAFT'
  | 'READY'
  | 'SCHEDULED'
  | 'RUNNING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'CANCELLED'

export interface CampaignRecipient {
  id: number
  campaign_id: number
  contact_id: number | null
  personalized_message: string | null
  status: string
  error: string | null
  created_at: string
  updated_at: string
}

export interface Campaign {
  id: number
  user_id: number
  name: string
  message_template: string
  status: CampaignStatus
  scheduled_at: string | null
  recipient_scope: string
  recipient_group_id: number | null
  recipient_contact_ids: number[]
  created_at: string
  updated_at: string
  recipient_count: number
  sent_count: number
  failed_count: number
  pending_count: number
  skipped_count: number
  opted_out_count: number
  recipients: CampaignRecipient[]
}

export interface RecipientTarget {
  scope: 'all' | 'group' | 'contacts'
  group_id?: number | null
  contact_ids?: number[]
}

export interface ValidationIssue {
  severity: 'error' | 'warning' | 'info'
  category: string
  message: string
  count: number
}

export interface RecipientPreview {
  contact_id: number
  name: string
  phone: string
  preview: string | null
  status: string
  error: string | null
}

export interface CampaignValidationReport {
  campaign_id: number
  valid: boolean
  total_recipients: number
  pending: number
  skipped_invalid_phone: number
  skipped_duplicate: number
  skipped_opted_out: number
  skipped_empty_message: number
  skipped_missing_fields: number
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  infos: ValidationIssue[]
  previews: RecipientPreview[]
}

export interface Device {
  id: number
  user_id: number
  device_name: string
  device_identifier: string
  platform: string
  connection_status: string
  last_seen: string | null
  created_at: string
  updated_at: string
}

export interface MessageLog {
  id: number
  campaign_id: number | null
  contact_id: number | null
  device_id: number | null
  message: string | null
  status: string
  error: string | null
  sent_at: string | null
  created_at: string
  campaign_name: string | null
  contact_name: string | null
  phone: string | null
  device_name: string | null
}

export interface OptOut {
  id: number
  phone: string
  reason: string | null
  created_at: string
}

export interface DashboardStats {
  total_contacts: number
  active_campaigns: number
  messages_sent: number
  failed_messages: number
  opt_outs: number
  connected_devices: number
  total_campaigns: number
  total_templates: number
}

export interface RecentCampaign {
  id: number
  name: string
  status: CampaignStatus
  recipient_count: number
  created_at: string
}

export interface RecentActivity {
  id: number
  action: string
  resource_type: string | null
  resource_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export interface DeviceStatusCard {
  id: number
  device_name: string
  platform: string
  connection_status: string
  last_seen: string | null
}

export interface DashboardResponse {
  stats: DashboardStats
  recent_campaigns: RecentCampaign[]
  recent_activity: RecentActivity[]
  devices: DeviceStatusCard[]
}

export interface ImportSummary {
  total: number
  valid: number
  invalid: number
  duplicates: number
  opted_out: number
  imported?: number
}

export interface ImportUploadResponse {
  file_id: string
  filename: string
  source: string
  columns: string[]
  suggested_mapping: Record<string, string>
  total_rows: number
  summary: ImportSummary
  sample_rows: Array<Record<string, string>>
}

export interface ImportValidateRow {
  row_number: number
  values: Record<string, string>
  status: string
  errors: string[]
  warnings: string[]
}

export interface ImportValidateResponse {
  file_id: string
  summary: ImportSummary
  rows: ImportValidateRow[]
}

export interface ImportConfirmResponse extends ImportSummary {
  imported: number
}
