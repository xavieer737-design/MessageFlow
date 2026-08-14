import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useToast } from '../ui/Toast'
import { Button } from '../ui/Button'
import { Field, Input, Select, Textarea } from '../ui/Form'
import { Modal } from '../ui/Modal'
import { getErrorMessage } from '../../lib/api'
import { contactsApi, groupsApi } from '../../services/api'
import type { Contact, ContactGroup } from '../../types'

export function ContactFormModal({
  open,
  onClose,
  contact,
  onSaved,
}: {
  open: boolean
  onClose: () => void
  contact?: Contact | null
  onSaved: () => void
}) {
  const { success, error } = useToast()
  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list, enabled: open })

  const [form, setForm] = useState({
    phone: '',
    first_name: '',
    last_name: '',
    email: '',
    company: '',
    notes: '',
    group_ids: [] as number[],
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setForm({
      phone: contact?.phone ?? '',
      first_name: contact?.first_name ?? '',
      last_name: contact?.last_name ?? '',
      email: contact?.email ?? '',
      company: contact?.company ?? '',
      notes: contact?.notes ?? '',
      group_ids: contact?.groups.map((g) => g.id) ?? [],
    })
  }, [open, contact])

  const set = (key: keyof typeof form, value: string | number[]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const payload = {
        phone: form.phone.trim(),
        first_name: form.first_name.trim() || null,
        last_name: form.last_name.trim() || null,
        email: form.email.trim() || null,
        company: form.company.trim() || null,
        notes: form.notes.trim() || null,
        group_ids: form.group_ids,
      }
      if (contact) {
        await contactsApi.update(contact.id, payload)
        success('Contact updated')
      } else {
        await contactsApi.create(payload)
        success('Contact added')
      }
      onSaved()
      onClose()
    } catch (err) {
      error(getErrorMessage(err, 'Could not save contact'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={contact ? 'Edit contact' : 'Add contact'}
      description="Phone numbers are normalized to international format automatically."
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="contact-form" loading={saving}>
            {contact ? 'Save changes' : 'Add contact'}
          </Button>
        </>
      }
    >
      <form id="contact-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Phone" required hint="e.g. 9876543210 or +91 98765 43210">
          <Input
            value={form.phone}
            onChange={(event) => set('phone', event.target.value)}
            placeholder="9876543210"
            required
          />
        </Field>
        <Field label="Company">
          <Input
            value={form.company}
            onChange={(event) => set('company', event.target.value)}
            placeholder="ABC Ltd"
          />
        </Field>
        <Field label="First name">
          <Input value={form.first_name} onChange={(event) => set('first_name', event.target.value)} placeholder="Rahul" />
        </Field>
        <Field label="Last name">
          <Input value={form.last_name} onChange={(event) => set('last_name', event.target.value)} placeholder="Sharma" />
        </Field>
        <Field label="Email">
          <Input
            type="email"
            value={form.email}
            onChange={(event) => set('email', event.target.value)}
            placeholder="rahul@example.com"
          />
        </Field>
        <Field label="Groups">
          <Select
            value=""
            onChange={(event) => {
              const id = Number(event.target.value)
              if (id && !form.group_ids.includes(id)) set('group_ids', [...form.group_ids, id])
            }}
          >
            <option value="">Add to a group…</option>
            {groups?.map((group: ContactGroup) => (
              <option key={group.id} value={group.id}>{group.name}</option>
            ))}
          </Select>
        </Field>
        {form.group_ids.length > 0 && (
          <div className="flex flex-wrap gap-1.5 sm:col-span-2">
            {form.group_ids.map((id) => {
              const group = groups?.find((g) => g.id === id)
              return (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"
                >
                  {group?.name ?? `#${id}`}
                  <button
                    type="button"
                    onClick={() => set('group_ids', form.group_ids.filter((g) => g !== id))}
                    className="text-brand-400 hover:text-brand-600"
                    aria-label={`Remove ${group?.name}`}
                  >
                    ×
                  </button>
                </span>
              )
            })}
          </div>
        )}
        <Field label="Notes" className="sm:col-span-2">
          <Textarea value={form.notes} onChange={(event) => set('notes', event.target.value)} placeholder="Anything worth remembering" />
        </Field>
      </form>
    </Modal>
  )
}
