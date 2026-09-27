import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createAccount, fetchAccounts } from '../api.ts'
import { formatMoney } from '../money.ts'
import type { Account, AccountType } from '../types.ts'

export const AccountsPage: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)

  // Form states
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [type, setType] = useState<AccountType>('ASSET')
  const [allowNegative, setAllowNegative] = useState(true)
  const [formSubmitting, setFormSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      const data = await fetchAccounts()
      setAccounts(data)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al cargar cuentas')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setFormSubmitting(true)
    try {
      await createAccount({
        code,
        name,
        type,
        currency: 'EUR',
        allow_negative: allowNegative,
      })
      setShowModal(false)
      setCode('')
      setName('')
      setAllowNegative(true)
      await loadData()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error al crear cuenta')
    } finally {
      setFormSubmitting(false)
    }
  }

  // Resumen contable
  const totalAssets = accounts
    .filter((a) => a.type === 'ASSET')
    .reduce((acc, a) => acc + Number.parseFloat(a.balance), 0)

  const totalLiabilities = accounts
    .filter((a) => a.type === 'LIABILITY')
    .reduce((acc, a) => acc + Number.parseFloat(a.balance), 0)

  const totalEquity = accounts
    .filter((a) => a.type === 'EQUITY')
    .reduce((acc, a) => acc + Number.parseFloat(a.balance), 0)

  const totalRevenues = accounts
    .filter((a) => a.type === 'REVENUE')
    .reduce((acc, a) => acc + Number.parseFloat(a.balance), 0)

  const totalExpenses = accounts
    .filter((a) => a.type === 'EXPENSE')
    .reduce((acc, a) => acc + Number.parseFloat(a.balance), 0)

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Plan de Cuentas Contable</h2>
          <p className="page-subtitle">Cuentas del libro mayor, tipología y saldos calculados en tiempo real</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          ➕ Nueva Cuenta
        </button>
      </div>

      {error && <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>{error}</div>}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Activo</div>
          <div className="stat-value">{formatMoney(totalAssets)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Pasivo</div>
          <div className="stat-value">{formatMoney(totalLiabilities)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Patrimonio Neto</div>
          <div className="stat-value">{formatMoney(totalEquity)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Ingresos / Ventas</div>
          <div className="stat-value" style={{ color: 'var(--success)' }}>{formatMoney(totalRevenues)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Gastos / Compras</div>
          <div className="stat-value" style={{ color: 'var(--danger)' }}>{formatMoney(totalExpenses)}</div>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre de la Cuenta</th>
              <th>Naturaleza</th>
              <th className="text-center">Permite Descubierto</th>
              <th className="text-right">Total Debe</th>
              <th className="text-right">Total Haber</th>
              <th className="text-right">Saldo Actual</th>
              <th className="text-center">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="text-center" style={{ padding: '2rem' }}>
                  Cargando plan contable...
                </td>
              </tr>
            ) : accounts.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center" style={{ padding: '2rem' }}>
                  No hay cuentas registradas. Crea una nueva cuenta para comenzar.
                </td>
              </tr>
            ) : (
              accounts.map((acc) => (
                <tr key={acc.id}>
                  <td><strong>{acc.code}</strong></td>
                  <td>{acc.name}</td>
                  <td>
                    <span className={`badge badge-${acc.type.toLowerCase()}`}>
                      {acc.type}
                    </span>
                  </td>
                  <td className="text-center">
                    {acc.allow_negative ? (
                      <span style={{ color: 'var(--text-muted)' }}>Sí</span>
                    ) : (
                      <span style={{ color: 'var(--warning)', fontWeight: 600 }}>No (Anti-sobregiro)</span>
                    )}
                  </td>
                  <td className="text-right">{formatMoney(acc.total_debit)}</td>
                  <td className="text-right">{formatMoney(acc.total_credit)}</td>
                  <td className="text-right" style={{ fontWeight: 700 }}>
                    {formatMoney(acc.balance)}
                  </td>
                  <td className="text-center">
                    <Link
                      to={`/statements?account=${acc.id}`}
                      className="btn btn-secondary"
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                    >
                      Ver Mayor
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '1rem' }}>Crear Nueva Cuenta</h3>
            {formError && (
              <div style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {formError}
              </div>
            )}
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Código de Cuenta</label>
                <input
                  type="text"
                  required
                  placeholder="Ej: 1000, 4300, 7000..."
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Nombre de la Cuenta</label>
                <input
                  type="text"
                  required
                  placeholder="Ej: Banco Santander, Caja, Ventas..."
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Naturaleza Contable</label>
                <select value={type} onChange={(e) => setType(e.target.value as AccountType)}>
                  <option value="ASSET">ACTIVO (Caja, Bancos, Clientes, Inmovilizado)</option>
                  <option value="LIABILITY">PASIVO (Proveedores, Préstamos, Deudas)</option>
                  <option value="EQUITY">PATRIMONIO NETO (Capital Social, Reservas)</option>
                  <option value="REVENUE">INGRESOS (Ventas, Prestación de Servicios)</option>
                  <option value="EXPENSE">GASTOS (Compras, Suministros, Nóminas)</option>
                </select>
              </div>
              <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1rem' }}>
                <input
                  type="checkbox"
                  id="allowNegative"
                  style={{ width: 'auto' }}
                  checked={allowNegative}
                  onChange={(e) => setAllowNegative(e.target.checked)}
                />
                <label htmlFor="allowNegative" style={{ marginBottom: 0, cursor: 'pointer' }}>
                  Permitir saldo negativo (desmarca para cuentas de caja o con protección estricta anti-descubierto)
                </label>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={formSubmitting}>
                  {formSubmitting ? 'Guardando...' : 'Crear Cuenta'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
