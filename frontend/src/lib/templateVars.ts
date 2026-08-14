// Template variable utilities (mirror backend template_service).

export const SUPPORTED_VARIABLES = [
  'first_name',
  'last_name',
  'phone',
  'email',
  'company',
  'notes',
] as const

export type TemplateVariable = (typeof SUPPORTED_VARIABLES)[number]

export const VARIABLE_LABELS: Record<TemplateVariable, string> = {
  first_name: 'First name',
  last_name: 'Last name',
  phone: 'Phone',
  email: 'Email',
  company: 'Company',
  notes: 'Notes',
}

const VARIABLE_RE = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g

export function extractVariables(message: string): {
  found: TemplateVariable[]
  unsupported: string[]
} {
  const found: TemplateVariable[] = []
  const unsupported: string[] = []
  for (const match of message.matchAll(VARIABLE_RE)) {
    const name = match[1].toLowerCase()
    if ((SUPPORTED_VARIABLES as readonly string[]).includes(name)) {
      if (!found.includes(name as TemplateVariable)) found.push(name as TemplateVariable)
    } else if (!unsupported.includes(match[1])) {
      unsupported.push(match[1])
    }
  }
  return { found, unsupported }
}

export interface PersonalizeValues {
  first_name?: string
  last_name?: string
  phone?: string
  email?: string
  company?: string
  notes?: string
}

export function personalize(
  message: string,
  values: PersonalizeValues,
): { text: string; missing: string[] } {
  const missing: string[] = []
  const text = message.replace(VARIABLE_RE, (raw, name: string) => {
    const key = name.toLowerCase() as keyof PersonalizeValues
    if (!(SUPPORTED_VARIABLES as readonly string[]).includes(key)) return raw
    const value = values[key] ?? ''
    if (!value) missing.push(key)
    return value
  })
  return { text, missing }
}

export function insertVariable(message: string, variable: string, cursor: number): string {
  const token = `{{${variable}}}`
  return message.slice(0, cursor) + token + message.slice(cursor)
}
