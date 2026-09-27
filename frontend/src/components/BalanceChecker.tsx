import React from 'react'
import { formatMoney } from '../money.ts'

interface BalanceCheckerProps {
  totalDebit: number
  totalCredit: number
}

export const BalanceChecker: React.FC<BalanceCheckerProps> = ({ totalDebit, totalCredit }) => {
  const diff = Math.abs(totalDebit - totalCredit)
  const isBalanced = diff < 0.0001 && totalDebit > 0

  return (
    <div
      className={`balance-checker ${isBalanced ? 'balanced' : 'unbalanced'}`}
      data-testid="balance-checker"
    >
      <div>
        <span>Debe: <strong>{formatMoney(totalDebit)}</strong></span>
        <span style={{ marginLeft: '1.5rem' }}>Haber: <strong>{formatMoney(totalCredit)}</strong></span>
      </div>
      <div>
        {isBalanced ? (
          <span>✅ Asiento cuadrado (Diferencia: 0,00 €)</span>
        ) : (
          <span>
            {totalDebit === 0 && totalCredit === 0
              ? 'Introduce al menos dos líneas contables'
              : `⚠️ Descuadre de ${formatMoney(diff)}`}
          </span>
        )}
      </div>
    </div>
  )
}
