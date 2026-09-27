import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchTransactions, reverseTransaction } from '../api.ts'
import { formatMoney } from '../money.ts'
import type { Transaction } from '../types.ts'

export const TransactionsPage: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reversingId, setReversingId] = useState<number | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      const data = await fetchTransactions()
      setTransactions(data)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar transacciones')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleReverse = async (tx: Transaction) => {
    const reason = window.prompt(
      `Introduce el motivo para revertir el asiento #${tx.id} ("${tx.description}"):`,
      'Reversión por corrección contable'
    )
    if (!reason) return

    try {
      setReversingId(tx.id)
      await reverseTransaction(tx.id, reason)
      await loadData()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Error al revertir')
    } finally {
      setReversingId(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Libro Diario Contable</h2>
          <p className="page-subtitle">Registro cronológico e inmutable de todos los asientos y compensaciones</p>
        </div>
        <Link to="/transactions/new" className="btn btn-primary">
          ✍️ Registrar Asiento
        </Link>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="card text-center" style={{ padding: '3rem' }}>
          Cargando libro diario...
        </div>
      ) : transactions.length === 0 ? (
        <div className="card text-center" style={{ padding: '3rem' }}>
          No hay asientos contables registrados todavía.
        </div>
      ) : (
        transactions.map((tx) => {
          const totalAmount = tx.postings
            .filter((p) => p.direction === 'DEBIT')
            .reduce((acc, p) => acc + Number.parseFloat(p.amount), 0)

          return (
            <div key={tx.id} className="card" style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div>
                  <span style={{ fontWeight: 700, fontSize: '1.1rem', marginRight: '0.75rem' }}>
                    Asiento #{tx.id}
                  </span>
                  <span className={`badge badge-${tx.status.toLowerCase()}`}>
                    {tx.status === 'POSTED' ? 'ASENTADO' : 'REVERTIDO'}
                  </span>
                  {tx.reversal_of_id && (
                    <span className="badge badge-warning" style={{ marginLeft: '0.5rem', background: '#fef3c7', color: '#b45309' }}>
                      Compensa asiento #{tx.reversal_of_id}
                    </span>
                  )}
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    Fecha: {new Date(tx.posted_at).toLocaleString('es-ES')} · Idempotencia: <code style={{ fontSize: '0.75rem' }}>{tx.idempotency_key}</code>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>TOTAL ASIENTO</div>
                    <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{formatMoney(totalAmount)}</div>
                  </div>
                  {tx.status === 'POSTED' && (
                    <button
                      className="btn btn-danger"
                      style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                      disabled={reversingId === tx.id}
                      onClick={() => handleReverse(tx)}
                    >
                      {reversingId === tx.id ? 'Revirtiendo...' : '↩️ Revertir'}
                    </button>
                  )}
                </div>
              </div>

              <p style={{ marginBottom: '1rem', fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                "{tx.description}"
              </p>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Código Cuenta</th>
                      <th>Nombre de la Cuenta</th>
                      <th className="text-right">Debe (€)</th>
                      <th className="text-right">Haber (€)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tx.postings.map((p) => (
                      <tr key={p.id}>
                        <td><strong>{p.account_code ?? `ID ${p.account_id}`}</strong></td>
                        <td>{p.account_name ?? '—'}</td>
                        <td className="text-right" style={{ color: p.direction === 'DEBIT' ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                          {p.direction === 'DEBIT' ? formatMoney(p.amount) : '—'}
                        </td>
                        <td className="text-right" style={{ color: p.direction === 'CREDIT' ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                          {p.direction === 'CREDIT' ? formatMoney(p.amount) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}
