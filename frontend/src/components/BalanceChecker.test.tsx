import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BalanceChecker } from './BalanceChecker.tsx'

describe('BalanceChecker component', () => {
  it('renders balanced status when debits equal credits', () => {
    render(<BalanceChecker totalDebit={150.0} totalCredit={150.0} />)
    const element = screen.getByTestId('balance-checker')
    expect(element).toHaveClass('balanced')
    expect(screen.getByText(/Asiento cuadrado/i)).toBeInTheDocument()
  })

  it('renders unbalanced status when debits and credits differ', () => {
    render(<BalanceChecker totalDebit={100.0} totalCredit={80.0} />)
    const element = screen.getByTestId('balance-checker')
    expect(element).toHaveClass('unbalanced')
    expect(screen.getByText(/Descuadre de/i)).toBeInTheDocument()
  })
})
