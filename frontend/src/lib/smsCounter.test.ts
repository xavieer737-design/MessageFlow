import { describe, expect, it } from 'vitest'
import { analyzeSms } from './smsCounter'

describe('analyzeSms', () => {
  it('counts a plain ASCII message as one GSM-7 segment', () => {
    const result = analyzeSms('Hello world!')
    expect(result.encoding).toBe('GSM-7')
    expect(result.characters).toBe(12)
    expect(result.segments).toBe(1)
  })

  it('keeps 160 characters in a single segment', () => {
    expect(analyzeSms('a'.repeat(160)).segments).toBe(1)
    expect(analyzeSms('a'.repeat(161)).segments).toBe(2)
  })

  it('detects UCS-2 for non-GSM characters', () => {
    const result = analyzeSms('Привет мир')
    expect(result.encoding).toBe('UCS-2')
  })

  it('uses 70-char limit for UCS-2', () => {
    expect(analyzeSms('Ж'.repeat(70)).segments).toBe(1)
    expect(analyzeSms('Ж'.repeat(71)).segments).toBe(2)
  })

  it('counts GSM extension characters as two', () => {
    const result = analyzeSms('Cost: €50')
    expect(result.encoding).toBe('GSM-7')
    expect(result.characters).toBe(10)
  })

  it('flags messages over the practical segment limit', () => {
    expect(analyzeSms('a'.repeat(1700)).exceedLimit).toBe(true)
    expect(analyzeSms('a'.repeat(160)).exceedLimit).toBe(false)
  })

  it('handles empty strings', () => {
    expect(analyzeSms('').segments).toBe(1)
    expect(analyzeSms('').characters).toBe(0)
  })
})
