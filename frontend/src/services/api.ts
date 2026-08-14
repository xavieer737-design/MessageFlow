// Typed API service functions.

import { api } from '../lib/api'
import type {
  Campaign,
  CampaignValidationReport,
  CampaignStatus,
  Contact,
  ContactGroup,
  ContactGroupDetail,
  DashboardResponse,
  Device,
  ImportConfirmResponse,
  ImportUploadResponse,
  ImportValidateResponse,
  MessageLog,
  MessageTemplate,
  OptOut,
  Paginated,
  RecipientTarget,
  User,
} from '../types'

// --- Auth ---

export const authApi = {
  register: (payload: { name: string; email: string; password: string }) =>
    api.post<User>('/auth/register', payload).then((r) => r.data),
  login: (payload: { email: string; password: string }) =>
    api.post<User>('/auth/login', payload).then((r) => r.data),
  logout: () => api.post('/auth/logout').then((r) => r.data),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
  updateProfile: (name: string) => api.put<User>('/auth/me', { name }).then((r) => r.data),
  changePassword: (current_password: string, new_password: string) =>
    api.put('/auth/me/password', { current_password, new_password }).then((r) => r.data),
}

// --- Contacts ---

export interface ContactQuery {
  search?: string
  group_id?: number
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export const contactsApi = {
  list: (params: ContactQuery) =>
    api.get<Paginated<Contact>>('/contacts', { params }).then((r) => r.data),
  get: (id: number) => api.get<Contact>(`/contacts/${id}`).then((r) => r.data),
  create: (payload: Partial<Contact> & { phone: string; group_ids?: number[] }) =>
    api.post<Contact>('/contacts', payload).then((r) => r.data),
  update: (id: number, payload: Partial<Contact> & { phone: string; group_ids?: number[] }) =>
    api.put<Contact>(`/contacts/${id}`, payload).then((r) => r.data),
  remove: (id: number) => api.delete(`/contacts/${id}`).then((r) => r.data),
  bulkDelete: (ids: number[]) => api.post('/contacts/bulk-delete', ids).then((r) => r.data),
  exportUrl: (format: 'csv' | 'xlsx' = 'csv') => `/api/contacts/export?format=${format}`,
  importUpload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .post<ImportUploadResponse>('/contacts/import/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
  importValidate: (file_id: string, mapping: Record<string, string>) => {
    const form = new FormData()
    form.append('file_id', file_id)
    form.append('mapping', JSON.stringify(mapping))
    return api
      .post<ImportValidateResponse>('/contacts/import/validate', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
  importConfirm: (file_id: string, mapping: Record<string, string>) => {
    const form = new FormData()
    form.append('file_id', file_id)
    form.append('mapping', JSON.stringify(mapping))
    return api
      .post<ImportConfirmResponse>('/contacts/import/confirm', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
}

// --- Groups ---

export const groupsApi = {
  list: () => api.get<ContactGroup[]>('/groups').then((r) => r.data),
  get: (id: number) => api.get<ContactGroupDetail>(`/groups/${id}`).then((r) => r.data),
  create: (payload: { name: string; description?: string }) =>
    api.post<ContactGroup>('/groups', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; description?: string }) =>
    api.put<ContactGroup>(`/groups/${id}`, payload).then((r) => r.data),
  remove: (id: number) => api.delete(`/groups/${id}`).then((r) => r.data),
  addContacts: (id: number, contact_ids: number[]) =>
    api.post<ContactGroupDetail>(`/groups/${id}/contacts`, { contact_ids }).then((r) => r.data),
  removeContacts: (id: number, contact_ids: number[]) =>
    api.post<ContactGroupDetail>(`/groups/${id}/contacts/remove`, { contact_ids }).then((r) => r.data),
}

// --- Templates ---

export const templatesApi = {
  list: () => api.get<MessageTemplate[]>('/templates').then((r) => r.data),
  get: (id: number) => api.get<MessageTemplate>(`/templates/${id}`).then((r) => r.data),
  create: (payload: { name: string; message: string }) =>
    api.post<MessageTemplate>('/templates', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; message: string }) =>
    api.put<MessageTemplate>(`/templates/${id}`, payload).then((r) => r.data),
  duplicate: (id: number) => api.post<MessageTemplate>(`/templates/${id}/duplicate`).then((r) => r.data),
  remove: (id: number) => api.delete(`/templates/${id}`).then((r) => r.data),
  preview: (payload: { message: string; first_name?: string; company?: string }) =>
    api
      .post<{ preview: string; variables_found: string[]; variables_missing: string[] }>(
        '/templates/preview',
        payload,
      )
      .then((r) => r.data),
}

// --- Campaigns ---

export const campaignsApi = {
  list: (params: { status?: string; search?: string; page?: number; page_size?: number } = {}) =>
    api.get<Paginated<Campaign>>('/campaigns', { params }).then((r) => r.data),
  get: (id: number) => api.get<Campaign>(`/campaigns/${id}`).then((r) => r.data),
  create: (payload: {
    name: string
    message_template: string
    recipients: RecipientTarget
    status?: 'DRAFT' | 'READY'
  }) => api.post<Campaign>('/campaigns', payload).then((r) => r.data),
  update: (id: number, payload: Record<string, unknown>) =>
    api.put<Campaign>(`/campaigns/${id}`, payload).then((r) => r.data),
  remove: (id: number) => api.delete(`/campaigns/${id}`).then((r) => r.data),
  validate: (id: number) =>
    api.post<CampaignValidationReport>(`/campaigns/${id}/validate`).then((r) => r.data),
  markReady: (id: number) => api.post<Campaign>(`/campaigns/${id}/ready`).then((r) => r.data),
  duplicate: (id: number) => api.post<Campaign>(`/campaigns/${id}/duplicate`).then((r) => r.data),
  pause: (id: number) => api.post<Campaign>(`/campaigns/${id}/pause`).then((r) => r.data),
  resume: (id: number) => api.post<Campaign>(`/campaigns/${id}/resume`).then((r) => r.data),
  cancel: (id: number) => api.post<Campaign>(`/campaigns/${id}/cancel`).then((r) => r.data),
}

// --- Devices ---

export const devicesApi = {
  list: () => api.get<Device[]>('/devices').then((r) => r.data),
  register: (payload: { device_name: string; device_identifier: string; platform: string }) =>
    api.post<Device>('/devices/register', payload).then((r) => r.data),
  remove: (id: number) => api.delete(`/devices/${id}`).then((r) => r.data),
}

// --- Messages ---

export const messagesApi = {
  list: (params: { status?: string; page?: number; page_size?: number } = {}) =>
    api.get<Paginated<MessageLog>>('/messages', { params }).then((r) => r.data),
}

// --- Opt-outs ---

export const optoutsApi = {
  list: (params: { search?: string; page?: number; page_size?: number } = {}) =>
    api.get<Paginated<OptOut>>('/optouts', { params }).then((r) => r.data),
  create: (payload: { phone: string; reason?: string }) =>
    api.post<OptOut>('/optouts', payload).then((r) => r.data),
  bulk: (phones: string[]) => api.post('/optouts/bulk', { phones }).then((r) => r.data),
  remove: (id: number) => api.delete(`/optouts/${id}`).then((r) => r.data),
  exportUrl: () => '/api/optouts/export',
}

// --- Dashboard ---

export const dashboardApi = {
  stats: () => api.get<DashboardResponse>('/dashboard/stats').then((r) => r.data),
}

export type { CampaignStatus }
