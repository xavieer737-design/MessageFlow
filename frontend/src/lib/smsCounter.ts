// Mirrors the backend SMS analysis so counters match exactly.

const GSM_BASIC =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?' +
  '¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà'

const GSM_EXTENDED = new Set('^{}\\[~]|€')
const GSM_ESCAPE = '\x1b'
export const MAX_GSM_SEGMENTS = 10

export interface SmsAnalysis {
  characters: number
  segments: number
  encoding: 'GSM-7' | 'UCS-2'
  perSegment: number
  truncated: boolean
  exceedLimit: boolean
}

function isGsm7bit(text: string): boolean {
  for (const ch of text) {
    if (ch === GSM_ESCAPE) continue
    if (GSM_EXTENDED.has(ch)) continue
    if (!GSM_BASIC.includes(ch)) return false
  }
  return true
}

function gsmLength(text: string): number {
  let length = 0
  for (const ch of text) {
    length += GSM_EXTENDED.has(ch) || ch === GSM_ESCAPE ? 2 : 1
  }
  return length
}

export function analyzeSms(text: string): SmsAnalysis {
  if (!text) text = ''
  const gsm = isGsm7bit(text)
  const encoding = gsm ? 'GSM-7' : 'UCS-2'
  const chars = gsm ? gsmLength(text) : text.length
  const perSegment = gsm ? 160 : 70
  const perSegmentConcat = gsm ? 153 : 67
  const segments = chars <= perSegment ? 1 : Math.ceil(chars / perSegmentConcat)
  return {
    characters: chars,
    segments,
    encoding,
    perSegment,
    truncated: chars > perSegment,
    exceedLimit: segments > MAX_GSM_SEGMENTS,
  }
}
