import React from 'react'
import { NavLink } from 'react-router-dom'

export const Navbar: React.FC = () => {
  return (
    <header>
      <div className="logo-area">
        <span className="logo-icon" role="img" aria-label="balanza">⚖️</span>
        <div className="logo-text">
          <h1>Double-Entry Ledger</h1>
          <p>Motor contable inmutable con garantías en PostgreSQL</p>
        </div>
      </div>
      <nav>
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          📊 Plan Contable
        </NavLink>
        <NavLink to="/transactions/new" className={({ isActive }) => (isActive ? 'active' : '')}>
          ✍️ Nuevo Asiento
        </NavLink>
        <NavLink to="/transactions" end className={({ isActive }) => (isActive ? 'active' : '')}>
          📜 Libro Diario
        </NavLink>
        <NavLink to="/statements" className={({ isActive }) => (isActive ? 'active' : '')}>
          📑 Libro Mayor
        </NavLink>
        <NavLink to="/trial-balance" className={({ isActive }) => (isActive ? 'active' : '')}>
          ⚖️ Sumas y Saldos
        </NavLink>
      </nav>
    </header>
  )
}
