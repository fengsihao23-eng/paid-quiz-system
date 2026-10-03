import { describe, expect, it } from 'vitest'
import { formatAccessCode, normalizeAccessCode, formatPrice } from './helpers'

describe('customer credential and price display', () => {
  it('keeps every character when a formatted code is formatted again', () => {
    const code = 'ABCD-EFGH-JKLM-NPQR'
    expect(formatAccessCode(code)).toBe(code)
    expect(formatAccessCode('abcdefghijklmnop')).toBe('ABCD-EFGH-IJKL-MNOP')
    expect(normalizeAccessCode(' abcd efgh-jklm npqr ')).toBe('ABCDEFGHJKLMNPQR')
  })
  it('shows 990 cents as 9.90 yuan for both products', () => {
    expect(formatPrice(990)).toMatch(/9\.90$/)
    expect(formatPrice(990)).not.toContain('990.00')
  })
})
