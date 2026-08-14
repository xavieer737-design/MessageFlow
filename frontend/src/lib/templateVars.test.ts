import { describe, expect, it } from 'vitest'
import { extractVariables, insertVariable, personalize } from './templateVars'

describe('template variables', () => {
  it('extracts supported and unsupported variables', () => {
    const result = extractVariables('Hi {{first_name}} {{company}} {{order_id}}')
    expect(result.found).toEqual(['first_name', 'company'])
    expect(result.unsupported).toEqual(['order_id'])
  })

  it('personalizes with contact values', () => {
    const { text, missing } = personalize('Hi {{first_name}}, your order from {{company}} is ready.', {
      first_name: 'Rahul',
      company: 'ABC Ltd',
    })
    expect(text).toBe('Hi Rahul, your order from ABC Ltd is ready.')
    expect(missing).toEqual([])
  })

  it('reports missing fields', () => {
    const { text, missing } = personalize('Hi {{first_name}} from {{company}}', { first_name: 'Rahul' })
    expect(text).toBe('Hi Rahul from ')
    expect(missing).toEqual(['company'])
  })

  it('leaves unsupported variables untouched', () => {
    const { text } = personalize('Hi {{first_name}} {{custom}}', { first_name: 'Rahul' })
    expect(text).toContain('{{custom}}')
  })

  it('inserts a variable at a cursor position', () => {
    expect(insertVariable('Hi ', 'first_name', 3)).toBe('Hi {{first_name}}')
  })

  it('handles whitespace inside braces', () => {
    const { text } = personalize('Hi {{ first_name }}!', { first_name: 'Rahul' })
    expect(text).toBe('Hi Rahul!')
  })
})
