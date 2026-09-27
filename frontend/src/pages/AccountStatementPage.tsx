import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchAccountStatement, fetchAccounts } from '../api.ts'
import { formatMoney } from '../money.ts'
import type { Account, AccountStatementResponse } from '../types.ts'

export const AccountStatementPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams()
  const accountParam = searchParams.get('account')

  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | ''>(
    accountParam ? Number(accountParam) : ''
  )
  const [statement, setStatement] = useState<AccountStatementResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAccounts().then((data) => {
      setAccounts(data)
      if (!selectedAccountId && data.length > 0) {
        setSelectedAccountId(data[0].id)
      }
    })
  }, [])

  useEffect(() => {
    if (selectedAccountId) {
      setSearchParams({ account: selectedAccountId.toString() })
      setLoading(true)
      fetchAccountStatement(Number(selectedAccountId))
        .then((data) => {
          setStatement(data)
          setError(null)
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [selectedAccountId])

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Libro Mayor / Extracto de Cuenta</h2>
          <p className="page-subtitle">Movimientos históricos y cálculo del saldo acumulado cronológico</p>
        </div>
      </div>

      <div className="card">
        <div className="form-group" style={{ maxWidth: '400px', marginBottom: 0 }}>
          <label>Selecciona una cuenta contable</label>
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(Number(e.target.value))}
          >
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                [{a.code}] {a.name} ({a.type})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div>}

      {statement && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Cuenta</div>
              <div className="stat-value" style={{ fontSize: '1.1rem' }}>
                [{statement.account.code}] {statement.account.name}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Naturaleza</div>
              <div className="stat-value" style={{ fontSize: '1.1rem' }}>
                <span className={`badge badge-${statement.account.type.toLowerCase()}`}>
                  {statement.account.type}
                </span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Saldo Acumulado Final</div>
              <div className="stat-value" style={{ color: 'var(--primary)' }}>
                {formatMoney(statement.account.balance)}
              </div>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Asiento</th>
                  <th>Concepto</th>
                  <th className="text-right">Debe (€)</th>
                  <th className="text-right">Haber (€)</th>
                  <th className="text-right">Saldo Acumulado (€)</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} className="text-center" style={{ padding: '2rem' }}>
                      Cargando extracto...
                    </td>
                  </tr>
                ) : statement.items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center" style={{ padding: '2rem' }}>
                      Esta cuenta no tiene movimientos registrados.
                    </td>
                  </tr>
                ) : (
                  statement.items.map((it) => (
                    <tr key={it.posting_id}>
                      <td>{new Date(it.posted_at).toLocaleDateString('es-ES')}</td>
                      <td><strong>#{it.transaction_id}</strong></td>
                      <td>{it.description}</td>
                      <td className="text-right" style={{ color: it.direction === 'DEBIT' ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {it.direction === 'DEBIT' ? formatMoney(it.amount) : '—'}
                      </td>
                      <td className="text-right" style={{ color: it.direction === 'CREDIT' ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {it.direction === 'CREDIT' ? formatMoney(it.amount) : '—'}
                      </td>
                      <td className="text-right" style={{ fontWeight: 700 }}>
                        {formatMoney(it.running_balance)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
