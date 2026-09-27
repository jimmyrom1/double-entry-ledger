import React from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Navbar } from './components/Navbar.tsx'
import { AccountsPage } from './pages/AccountsPage.tsx'
import { AccountStatementPage } from './pages/AccountStatementPage.tsx'
import { NewTransactionPage } from './pages/NewTransactionPage.tsx'
import { TransactionsPage } from './pages/TransactionsPage.tsx'
import { TrialBalancePage } from './pages/TrialBalancePage.tsx'

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<AccountsPage />} />
            <Route path="/transactions/new" element={<NewTransactionPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/statements" element={<AccountStatementPage />} />
            <Route path="/trial-balance" element={<TrialBalancePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
