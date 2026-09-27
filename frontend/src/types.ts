export type AccountType = 'ASSET' | 'LIABILITY' | 'EQUITY' | 'REVENUE' | 'EXPENSE'

export type PostingDirection = 'DEBIT' | 'CREDIT'

export type TransactionStatus = 'POSTED' | 'REVERSED'

export interface Account {
  id: number
  code: string
  name: string
  type: AccountType
  currency: string
  allow_negative: boolean
  created_at: string
  balance: string
  total_debit: string
  total_credit: string
}

export interface Posting {
  id: number
  transaction_id: number
  account_id: number
  account_code?: string
  account_name?: string
  direction: PostingDirection
  amount: string
  created_at: string
}

export interface Transaction {
  id: number
  idempotency_key: string
  description: string
  posted_at: string
  status: TransactionStatus
  reversal_of_id?: number | null
  created_at: string
  postings: Posting[]
}

export interface TrialBalanceLine {
  account_id: number
  code: string
  name: string
  type: AccountType
  total_debit: string
  total_credit: string
  debit_balance: string
  credit_balance: string
}

export interface TrialBalanceReport {
  as_of: string
  lines: TrialBalanceLine[]
  total_debits: string
  total_credits: string
  total_debit_balance: string
  total_credit_balance: string
  is_balanced: boolean
}

export interface AccountStatementItem {
  posting_id: number
  transaction_id: number
  posted_at: string
  description: string
  direction: PostingDirection
  amount: string
  running_balance: string
}

export interface AccountStatementResponse {
  account: Account
  items: AccountStatementItem[]
}
