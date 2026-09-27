import { describe, expect, it } from 'vitest'
import { formatMoney, formatPrecisionMoney, roundMoney } from './money.ts'

describe('money utilities', () => {
  it('formats euro currency correctly', () => {
    const formatted = formatMoney('1250.50')
    expect(formatted).toMatch(/1\.?250,50/)
    expect(formatted).toContain('€')
  })

  it('handles invalid numbers gracefully', () => {
    expect(formatMoney('invalid')).toBe('0,00 €')
  })

  it('formats 4 decimal places with formatPrecisionMoney', () => {
    const formatted = formatPrecisionMoney('123.4567')
    expect(formatted).toMatch(/123,4567/)
  })

  it('rounds money accurately', () => {
    expect(roundMoney(10.005)).toBe(10.01)
    expect(roundMoney(10.004)).toBe(10.00)
  })
})
