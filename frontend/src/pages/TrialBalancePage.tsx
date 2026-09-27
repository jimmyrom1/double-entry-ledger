import React, { useEffect, useState } from 'react'
import { fetchTrialBalance } from '../api.ts'
import { formatMoney } from '../money.ts'
import type { TrialBalanceReport } from '../types.ts'

export const TrialBalancePage: React.FC = () => {
  const [report, setReport] = useState<TrialBalanceReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      const data = await fetchTrialBalance()
      setReport(data)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar balance de comprobación')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Balance de Sumas y Saldos (Trial Balance)</h2>
          <p className="page-subtitle">Auditoría contable y comprobación del cuadre estricto Debe == Haber</p>
        </div>
        <button className="btn btn-secondary" onClick={loadData}>
          🔄 Actualizar
        </button>
      </div>

      {error && <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div>}

      {report && (
        <>
          <div
            className={`balance-checker ${report.is_balanced ? 'balanced' : 'unbalanced'}`}
            style={{ marginBottom: '1.5rem', padding: '1.25rem' }}
          >
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                {report.is_balanced
                  ? '✅ Invariante Contable Garantizado: El libro mayor está 100% cuadrado'
                  : '⚠️ Alerta de Descuadre en el Libro Mayor'}
              </div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                Fecha de auditoría: {new Date(report.as_of).toLocaleString('es-ES')}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div>Suma Global Débitos: <strong>{formatMoney(report.total_debits)}</strong></div>
              <div>Suma Global Créditos: <strong>{formatMoney(report.total_credits)}</strong></div>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th rowSpan={2} style={{ verticalAlign: 'bottom' }}>Código</th>
                  <th rowSpan={2} style={{ verticalAlign: 'bottom' }}>Cuenta</th>
                  <th rowSpan={2} style={{ verticalAlign: 'bottom' }}>Naturaleza</th>
                  <th colSpan={2} className="text-center" style={{ borderBottom: '1px solid var(--border-color)', background: '#f1f5f9' }}>
                    SUMAS (€)
                  </th>
                  <th colSpan={2} className="text-center" style={{ borderBottom: '1px solid var(--border-color)', background: '#e2e8f0' }}>
                    SALDOS (€)
                  </th>
                </tr>
                <tr>
                  <th className="text-right">Suma Debe</th>
                  <th className="text-right">Suma Haber</th>
                  <th className="text-right">Saldo Deudor</th>
                  <th className="text-right">Saldo Acreedor</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-center" style={{ padding: '2rem' }}>
                      Cargando balance...
                    </td>
                  </tr>
                ) : (
                  <>
                    {report.lines.map((l) => (
                      <tr key={l.account_id}>
                        <td><strong>{l.code}</strong></td>
                        <td>{l.name}</td>
                        <td>
                          <span className={`badge badge-${l.type.toLowerCase()}`}>
                            {l.type}
                          </span>
                        </td>
                        <td className="text-right">{formatMoney(l.total_debit)}</td>
                        <td className="text-right">{formatMoney(l.total_credit)}</td>
                        <td className="text-right" style={{ color: Number(l.debit_balance) > 0 ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                          {Number(l.debit_balance) > 0 ? formatMoney(l.debit_balance) : '—'}
                        </td>
                        <td className="text-right" style={{ color: Number(l.credit_balance) > 0 ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                          {Number(l.credit_balance) > 0 ? formatMoney(l.credit_balance) : '—'}
                        </td>
                      </tr>
                    ))}
                    <tr style={{ background: '#f8fafc', fontWeight: 700, borderTop: '2px solid var(--border-color)' }}>
                      <td colSpan={3}>TOTALES GLOBALES</td>
                      <td className="text-right">{formatMoney(report.total_debits)}</td>
                      <td className="text-right">{formatMoney(report.total_credits)}</td>
                      <td className="text-right">{formatMoney(report.total_debit_balance)}</td>
                      <td className="text-right">{formatMoney(report.total_credit_balance)}</td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
