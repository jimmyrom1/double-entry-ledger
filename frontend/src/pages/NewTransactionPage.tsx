import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createTransaction, fetchAccounts } from '../api.ts'
import { BalanceChecker } from '../components/BalanceChecker.tsx'
import type { Account, PostingDirection } from '../types.ts'

interface FormPostingLine {
  id: string
  accountId: number | ''
  direction: PostingDirection
  amount: string
}

export const NewTransactionPage: React.FC = () => {
  const navigate = useNavigate()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [description, setDescription] = useState('')
  const [lines, setLines] = useState<FormPostingLine[]>([
    { id: '1', accountId: '', direction: 'DEBIT', amount: '' },
    { id: '2', accountId: '', direction: 'CREDIT', amount: '' },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAccounts().then(setAccounts).catch((e) => setError(e.message))
  }, [])

  const addLine = (dir: PostingDirection = 'DEBIT') => {
    setLines((prev) => [
      ...prev,
      { id: Math.random().toString(), accountId: '', direction: dir, amount: '' },
    ])
  }

  const removeLine = (id: string) => {
    if (lines.length <= 2) return
    setLines((prev) => prev.filter((l) => l.id !== id))
  }

  const updateLine = (id: string, field: keyof FormPostingLine, value: unknown) => {
    setLines((prev) =>
      prev.map((l) => (l.id === id ? { ...l, [field]: value } : l))
    )
  }

  const totalDebit = lines
    .filter((l) => l.direction === 'DEBIT')
    .reduce((acc, l) => acc + (Number.parseFloat(l.amount) || 0), 0)

  const totalCredit = lines
    .filter((l) => l.direction === 'CREDIT')
    .reduce((acc, l) => acc + (Number.parseFloat(l.amount) || 0), 0)

  const diff = totalDebit - totalCredit
  const isBalanced = Math.abs(diff) < 0.0001 && totalDebit > 0 && lines.length >= 2

  const autoBalance = () => {
    if (Math.abs(diff) < 0.0001) return
    if (diff > 0) {
      // Falta en el Haber
      setLines((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          accountId: '',
          direction: 'CREDIT',
          amount: diff.toFixed(2),
        },
      ])
    } else {
      // Falta en el Debe
      setLines((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          accountId: '',
          direction: 'DEBIT',
          amount: Math.abs(diff).toFixed(2),
        },
      ])
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validar líneas
    for (const l of lines) {
      if (!l.accountId) {
        setError('Por favor, selecciona una cuenta para todas las líneas contables.')
        return
      }
      const val = Number.parseFloat(l.amount)
      if (Number.isNaN(val) || val <= 0) {
        setError('Todos los importes deben ser números estrictamente positivos.')
        return
      }
    }

    if (!isBalanced) {
      setError('El asiento está descuadrado: la suma del Debe debe ser igual a la suma del Haber.')
      return
    }

    setLoading(true)
    try {
      const idempotency_key = `web-tx-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`
      await createTransaction({
        idempotency_key,
        description,
        postings: lines.map((l) => ({
          account_id: Number(l.accountId),
          direction: l.direction,
          amount: Number.parseFloat(l.amount),
        })),
      })
      navigate('/transactions')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al registrar la transacción')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Registrar Nuevo Asiento Contable</h2>
          <p className="page-subtitle">Transacción inmutable por partida doble con validación atómica</p>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)', background: 'var(--danger-bg)' }}>
          ⚠️ {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="card">
          <div className="form-group">
            <label>Concepto / Descripción del Asiento</label>
            <input
              type="text"
              required
              placeholder="Ej: Pago de nóminas de septiembre, Factura proveedor 102..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <h3 style={{ fontSize: '1rem', marginTop: '1.5rem', marginBottom: '0.75rem' }}>
            Líneas del Asiento (Apuntes Contables)
          </h3>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '45%' }}>Cuenta Contable</th>
                  <th style={{ width: '20%' }}>Columna</th>
                  <th style={{ width: '25%' }}>Importe (€)</th>
                  <th style={{ width: '10%' }} className="text-center">Quitar</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.id}>
                    <td>
                      <select
                        required
                        value={line.accountId}
                        onChange={(e) => updateLine(line.id, 'accountId', Number(e.target.value))}
                      >
                        <option value="">-- Selecciona cuenta --</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            [{a.code}] {a.name} ({a.type})
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={line.direction}
                        onChange={(e) => updateLine(line.id, 'direction', e.target.value as PostingDirection)}
                      >
                        <option value="DEBIT">DEBE (Débito)</option>
                        <option value="CREDIT">HABER (Crédito)</option>
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        required
                        placeholder="0.00"
                        value={line.amount}
                        onChange={(e) => updateLine(line.id, 'amount', e.target.value)}
                      />
                    </td>
                    <td className="text-center">
                      <button
                        type="button"
                        className="btn btn-danger"
                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                        disabled={lines.length <= 2}
                        onClick={() => removeLine(line.id)}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button type="button" className="btn btn-secondary" onClick={() => addLine('DEBIT')}>
              ➕ Añadir Línea al Debe
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => addLine('CREDIT')}>
              ➕ Añadir Línea al Haber
            </button>
            {Math.abs(diff) > 0.0001 && totalDebit > 0 && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}
                onClick={autoBalance}
              >
                🪄 Cuadrar Automáticamente ({diff > 0 ? `Haber: ${diff.toFixed(2)} €` : `Debe: ${Math.abs(diff).toFixed(2)} €`})
              </button>
            )}
          </div>

          <BalanceChecker totalDebit={totalDebit} totalCredit={totalCredit} />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
            <button type="button" className="btn btn-secondary" onClick={() => navigate('/transactions')}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={!isBalanced || loading}>
              {loading ? 'Validando y Registrando...' : '💾 Registrar Asiento Contable'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
