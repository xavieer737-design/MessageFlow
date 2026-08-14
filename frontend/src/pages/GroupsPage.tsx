import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Trash2, Users, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { EmptyState } from '../components/ui/EmptyState'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { Field, Input, Textarea } from '../components/ui/Form'
import { PageHeader, Alert } from '../components/ui/Misc'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatNumber } from '../lib/format'
import { contactsApi, groupsApi } from '../services/api'
import type { ContactGroup } from '../types'

export function GroupsPage() {
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<ContactGroup | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ContactGroup | null>(null)
  const [deleting, setDeleting] = useState(false)

  const [detail, setDetail] = useState<ContactGroup | null>(null)
  const [removeTarget, setRemoveTarget] = useState<{ group: ContactGroup; contactId: number } | null>(null)

  const { data: groups, isLoading, isError } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })
  const { data: contacts } = useQuery({
    queryKey: ['contacts-all'],
    queryFn: () => contactsApi.list({ page_size: 200 }),
    enabled: !!detail,
  })
  const { data: detailContacts } = useQuery({
    queryKey: ['group-detail', detail?.id],
    queryFn: () => groupsApi.get(detail!.id),
    enabled: !!detail,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['groups'] })
    queryClient.invalidateQueries({ queryKey: ['contacts'] })
  }

  const openCreate = () => {
    setEditing(null)
    setName('')
    setDescription('')
    setModalOpen(true)
  }

  const openEdit = (group: ContactGroup) => {
    setEditing(group)
    setName(group.name)
    setDescription(group.description ?? '')
    setModalOpen(true)
  }

  const save = async () => {
    if (!name.trim()) return
    try {
      if (editing) {
        await groupsApi.update(editing.id, { name: name.trim(), description: description.trim() || undefined })
        success('Group updated')
      } else {
        await groupsApi.create({ name: name.trim(), description: description.trim() || undefined })
        success('Group created')
      }
      setModalOpen(false)
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not save group'))
    }
  }

  const removeGroup = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await groupsApi.remove(deleteTarget.id)
      success('Group deleted')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete group'))
    } finally {
      setDeleting(false)
    }
  }

  const removeContact = async () => {
    if (!removeTarget) return
    try {
      await groupsApi.removeContacts(removeTarget.group.id, [removeTarget.contactId])
      success('Contact removed from group')
      queryClient.invalidateQueries({ queryKey: ['group-detail'] })
      refresh()
      setRemoveTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not remove contact'))
    }
  }

  const addContactToGroup = async (groupId: number, contactId: number) => {
    try {
      await groupsApi.addContacts(groupId, [contactId])
      success('Contact added to group')
      queryClient.invalidateQueries({ queryKey: ['group-detail'] })
      refresh()
    } catch (err) {
      error(getErrorMessage(err, 'Could not add contact'))
    }
  }

  const memberIds = new Set(detailContacts?.contact_ids ?? [])
  const availableContacts = (contacts?.items ?? []).filter((contact) => !memberIds.has(contact.id))

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Contact Groups"
        description="Organize contacts into groups like Customers, Leads or VIP to target campaigns."
        actions={
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" /> New group
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-36 animate-pulse rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState title="Could not load groups" description="Check that the backend is running and try again." />
      ) : !groups || groups.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
          <EmptyState
            icon={UsersRound}
            title="No groups yet"
            description="Create groups to organize your contacts and target campaigns precisely."
            action={<Button onClick={openCreate}><Plus className="h-4 w-4" /> New group</Button>}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map((group) => (
            <div key={group.id} className="rounded-xl border border-zinc-200 bg-white p-5 shadow-card transition-shadow hover:shadow-pop dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-400">
                    <UsersRound className="h-4.5 w-4.5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{group.name}</h3>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {formatNumber(group.contact_count)} contact{group.contact_count === 1 ? '' : 's'}
                    </p>
                  </div>
                </div>
                <Dropdown>
                  {(close) => (
                    <>
                      <DropdownItem icon={<Users className="h-4 w-4" />} onClick={() => { setDetail(group); close() }}>
                        View contacts
                      </DropdownItem>
                      <DropdownItem icon={<Pencil className="h-4 w-4" />} onClick={() => { openEdit(group); close() }}>
                        Rename
                      </DropdownItem>
                      <DropdownItem danger icon={<Trash2 className="h-4 w-4" />} onClick={() => { setDeleteTarget(group); close() }}>
                        Delete
                      </DropdownItem>
                    </>
                  )}
                </Dropdown>
              </div>
              {group.description && (
                <p className="mt-3 line-clamp-2 text-sm text-zinc-500 dark:text-zinc-400">{group.description}</p>
              )}
              <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3 dark:border-zinc-800">
                <Badge tone="gray">{group.name}</Badge>
                <button
                  onClick={() => setDetail(group)}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400"
                >
                  Manage contacts →
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / edit modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Rename group' : 'New group'}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={!name.trim()}>{editing ? 'Save changes' : 'Create group'}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name" required>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. VIP customers" />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Who belongs here?" />
          </Field>
        </div>
      </Modal>

      {/* Group detail modal */}
      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail?.name ?? ''}
        description={`${detail?.contact_count ?? 0} contact${detail?.contact_count === 1 ? '' : 's'} in this group`}
        size="lg"
      >
        {detail && (
          <div className="space-y-4">
            {memberIds.size > 0 && (
              <div>
                <p className="mb-1.5 text-xs font-semibold tracking-wide text-zinc-400 uppercase">Members</p>
                <div className="space-y-1">
                  {(contacts?.items ?? [])
                    .filter((contact) => memberIds.has(contact.id))
                    .map((contact) => (
                      <div key={contact.id} className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2 dark:border-zinc-800">
                        <div>
                          <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                            {[contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Unknown'}
                          </p>
                          <p className="font-mono text-xs text-zinc-500">{contact.phone}</p>
                        </div>
                        <button
                          onClick={() => setRemoveTarget({ group: detail, contactId: contact.id })}
                          className="rounded-lg p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10"
                          aria-label={`Remove ${contact.first_name ?? contact.phone}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            )}
            <div>
              <p className="mb-1.5 text-xs font-semibold tracking-wide text-zinc-400 uppercase">Add contacts</p>
              {availableContacts.length === 0 ? (
                <Alert tone="info">All your contacts are already in this group (or you have no contacts yet).</Alert>
              ) : (
                <select
                  value=""
                  onChange={(event) => {
                    const id = Number(event.target.value)
                    if (id) addContactToGroup(detail.id, id)
                  }}
                  className="h-9 w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm focus:border-brand-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
                >
                  <option value="">Select a contact to add…</option>
                  {availableContacts.map((contact) => (
                    <option key={contact.id} value={contact.id}>
                      {[contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.phone} — {contact.phone}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeGroup}
        loading={deleting}
        title="Delete group"
        message={<>Delete group <strong>{deleteTarget?.name}</strong>? Contacts stay in your address book; only the group is removed.</>}
      />

      <ConfirmDialog
        open={!!removeTarget}
        onClose={() => setRemoveTarget(null)}
        onConfirm={removeContact}
        title="Remove from group"
        message="Remove this contact from the group? The contact itself is not deleted."
      />
    </div>
  )
}
