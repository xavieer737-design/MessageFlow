import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Pencil, Plus, Trash2, Upload, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ContactFormModal } from '../components/contacts/ContactFormModal'
import { ImportWizard } from '../components/contacts/ImportWizard'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/Modal'
import { Modal } from '../components/ui/Modal'
import { Dropdown, DropdownItem } from '../components/ui/Dropdown'
import { EmptyState, LoadingRows } from '../components/ui/EmptyState'
import { Field, Input, Select } from '../components/ui/Form'
import { PageHeader, SearchInput, useDebouncedValue } from '../components/ui/Misc'
import { Pagination, Table, Td, Th, THead, TRow } from '../components/ui/Table'
import { useToast } from '../components/ui/Toast'
import { getErrorMessage } from '../lib/api'
import { formatDate, fullName } from '../lib/format'
import { contactsApi, groupsApi } from '../services/api'
import type { Contact } from '../types'

const PAGE_SIZE = 25

export function ContactsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { success, error } = useToast()

  const [search, setSearch] = useState(searchParams.get('q') ?? '')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [groupFilter, setGroupFilter] = useState<number | ''>('')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)

  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Contact | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Contact | null>(null)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [groupModalOpen, setGroupModalOpen] = useState(false)
  const [groupName, setGroupName] = useState('')
  const [deleting, setDeleting] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['contacts', { search: debouncedSearch, groupFilter, sortBy, sortDir, page }],
    queryFn: () =>
      contactsApi.list({
        search: debouncedSearch,
        group_id: groupFilter === '' ? undefined : Number(groupFilter),
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        page_size: PAGE_SIZE,
      }),
  })

  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: groupsApi.list })

  const allSelected = useMemo(
    () => !!data?.items.length && data.items.every((contact) => selected.has(contact.id)),
    [data, selected],
  )

  const toggleAll = () => {
    if (!data) return
    setSelected(allSelected ? new Set() : new Set(data.items.map((contact) => contact.id)))
  }

  const toggleOne = (id: number) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['contacts'] })
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const handleSort = (key: string) => {
    if (sortBy === key) setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
    else {
      setSortBy(key)
      setSortDir('asc')
    }
  }

  const deleteContact = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await contactsApi.remove(deleteTarget.id)
      success('Contact deleted')
      refresh()
      setDeleteTarget(null)
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete contact'))
    } finally {
      setDeleting(false)
    }
  }

  const bulkDelete = async () => {
    setDeleting(true)
    try {
      await contactsApi.bulkDelete([...selected])
      success(`${selected.size} contact${selected.size === 1 ? '' : 's'} deleted`)
      setSelected(new Set())
      refresh()
      setBulkDeleteOpen(false)
    } catch (err) {
      error(getErrorMessage(err, 'Could not delete contacts'))
    } finally {
      setDeleting(false)
    }
  }

  const createGroupFromSelection = async () => {
    if (!groupName.trim()) return
    try {
      const group = await groupsApi.create({ name: groupName.trim() })
      await groupsApi.addContacts(group.id, [...selected])
      success(`Group "${group.name}" created with ${selected.size} contact${selected.size === 1 ? '' : 's'}`)
      setGroupModalOpen(false)
      setGroupName('')
      setSelected(new Set())
      queryClient.invalidateQueries({ queryKey: ['groups'] })
    } catch (err) {
      error(getErrorMessage(err, 'Could not create group'))
    }
  }

  const updateUrlQuery = (value: string) => {
    setSearch(value)
    if (value) setSearchParams({ q: value }, { replace: true })
    else setSearchParams({}, { replace: true })
    setPage(1)
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Contacts"
        description="Your address book. Phone numbers are stored in international format."
        actions={
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="h-4 w-4" /> Import CSV / Excel
            </Button>
            <Button onClick={() => { setEditing(null); setFormOpen(true) }}>
              <Plus className="h-4 w-4" /> Add contact
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={updateUrlQuery}
            placeholder="Search name, phone, email, company…"
            className="w-full sm:w-72"
          />
          <Select value={groupFilter} onChange={(event) => { setGroupFilter(event.target.value === '' ? '' : Number(event.target.value)); setPage(1) }} className="h-9 w-full sm:w-44">
            <option value="">All groups</option>
            {groups?.map((group) => (
              <option key={group.id} value={group.id}>{group.name}</option>
            ))}
          </Select>
        </div>

        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <Badge tone="violet">{selected.size} selected</Badge>
            <Button variant="outline" size="sm" onClick={() => setGroupModalOpen(true)}>
              <Users className="h-3.5 w-3.5" /> Create group
            </Button>
            <Button variant="danger" size="sm" onClick={() => setBulkDeleteOpen(true)}>
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
          </div>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900">
        {isLoading ? (
          <LoadingRows cols={7} />
        ) : isError ? (
          <EmptyState title="Could not load contacts" description="Check that the backend is running and try again." />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Users}
            title={debouncedSearch || groupFilter ? 'No contacts match your filters' : 'No contacts yet'}
            description={
              debouncedSearch || groupFilter
                ? 'Try a different search term or group filter.'
                : 'Add contacts one by one or import them from a CSV or Excel file.'
            }
            action={
              debouncedSearch || groupFilter ? undefined : (
                <>
                  <Button variant="outline" onClick={() => setImportOpen(true)}>
                    <Upload className="h-4 w-4" /> Import CSV / Excel
                  </Button>
                  <Button className="ml-2" onClick={() => { setEditing(null); setFormOpen(true) }}>
                    <Plus className="h-4 w-4" /> Add contact
                  </Button>
                </>
              )
            }
          />
        ) : (
          <>
            <Table>
              <THead>
                <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-800/40">
                  <Th className="w-10">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      className="h-4 w-4 rounded border-zinc-300 accent-brand-600"
                      aria-label="Select all"
                    />
                  </Th>
                  <Th onClick={() => handleSort('name')} active={sortBy === 'name'} direction={sortDir}>Name</Th>
                  <Th onClick={() => handleSort('phone')} active={sortBy === 'phone'} direction={sortDir}>Phone</Th>
                  <Th onClick={() => handleSort('email')} active={sortBy === 'email'} direction={sortDir}>Email</Th>
                  <Th onClick={() => handleSort('company')} active={sortBy === 'company'} direction={sortDir}>Company</Th>
                  <Th>Groups</Th>
                  <Th>Status</Th>
                  <Th onClick={() => handleSort('created_at')} active={sortBy === 'created_at'} direction={sortDir}>Created</Th>
                  <Th className="w-14" />
                </tr>
              </THead>
              <tbody>
                {data.items.map((contact) => (
                  <TRow key={contact.id}>
                    <Td>
                      <input
                        type="checkbox"
                        checked={selected.has(contact.id)}
                        onChange={() => toggleOne(contact.id)}
                        className="h-4 w-4 rounded border-zinc-300 accent-brand-600"
                        aria-label={`Select ${fullName(contact)}`}
                      />
                    </Td>
                    <Td>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">{fullName(contact)}</p>
                    </Td>
                    <Td className="font-mono text-xs">{contact.phone}</Td>
                    <Td className="max-w-44 truncate">{contact.email || <span className="text-zinc-300 dark:text-zinc-600">—</span>}</Td>
                    <Td className="max-w-36 truncate">{contact.company || <span className="text-zinc-300 dark:text-zinc-600">—</span>}</Td>
                    <Td>
                      <div className="flex max-w-40 flex-wrap gap-1">
                        {contact.groups.length === 0 ? (
                          <span className="text-zinc-300 dark:text-zinc-600">—</span>
                        ) : (
                          contact.groups.map((group) => (
                            <span key={group.id} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                              {group.name}
                            </span>
                          ))
                        )}
                      </div>
                    </Td>
                    <Td>
                      {contact.opted_out ? (
                        <Badge tone="red">Opted out</Badge>
                      ) : (
                        <Badge tone="green">Active</Badge>
                      )}
                    </Td>
                    <Td className="text-xs whitespace-nowrap">{formatDate(contact.created_at)}</Td>
                    <Td>
                      <Dropdown>
                        {(close) => (
                          <>
                            <DropdownItem icon={<Pencil className="h-4 w-4" />} onClick={() => { setEditing(contact); setFormOpen(true); close() }}>
                              Edit
                            </DropdownItem>
                            <DropdownItem danger icon={<Trash2 className="h-4 w-4" />} onClick={() => { setDeleteTarget(contact); close() }}>
                              Delete
                            </DropdownItem>
                          </>
                        )}
                      </Dropdown>
                    </Td>
                  </TRow>
                ))}
              </tbody>
            </Table>
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </div>

      <div className="mt-4 flex justify-end">
        <a
          href={contactsApi.exportUrl('csv')}
          className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3.5 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          <Download className="h-4 w-4" /> Export CSV
        </a>
        <a
          href={contactsApi.exportUrl('xlsx')}
          className="ml-2 inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3.5 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          <Download className="h-4 w-4" /> Export XLSX
        </a>
      </div>

      <ContactFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        contact={editing}
        onSaved={refresh}
      />
      <ImportWizard open={importOpen} onClose={() => setImportOpen(false)} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={deleteContact}
        loading={deleting}
        title="Delete contact"
        message={<>Are you sure you want to delete <strong>{deleteTarget ? fullName(deleteTarget) : ''}</strong>? This cannot be undone.</>}
      />

      <ConfirmDialog
        open={bulkDeleteOpen}
        onClose={() => setBulkDeleteOpen(false)}
        onConfirm={bulkDelete}
        loading={deleting}
        title="Delete selected contacts"
        message={<>Delete {selected.size} contact{selected.size === 1 ? '' : 's'}? This cannot be undone.</>}
      />

      <Modal
        open={groupModalOpen}
        onClose={() => setGroupModalOpen(false)}
        title="Create group from selection"
        description={`${selected.size} contact${selected.size === 1 ? '' : 's'} will be added to the new group.`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setGroupModalOpen(false)}>Cancel</Button>
            <Button onClick={createGroupFromSelection} disabled={!groupName.trim()}>Create group</Button>
          </>
        }
      >
        <Field label="Group name" required>
          <Input value={groupName} onChange={(event) => setGroupName(event.target.value)} placeholder="e.g. VIP customers" />
        </Field>
      </Modal>
    </div>
  )
}
