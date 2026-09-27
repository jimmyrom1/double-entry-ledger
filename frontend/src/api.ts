import type {
  Account,
  AccountStatementResponse,
  AccountType,
  PostingDirection,
  Transaction,
  TrialBalanceReport,
} from './types.ts'

export interface CreateAccountInput {
  code: string
  name: string
  type: AccountType
  currency?: string
  allow_negative?: boolean
}

export interface CreatePostingInput {
  account_id: number
  direction: PostingDirection
  amount: number
}

export interface CreateTransactionInput {
  idempotency_key: string
  description: string
  postings: CreatePostingInput[]
}

const BASE_URL = '/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = 'Error en la petición'
    try {
      const data = await res.json()
      if (data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      errorDetail = `${res.status} ${res.statusText}`
    }
    throw new Error(errorDetail)
  }
  return res.json()
}

export async function fetchAccounts(): Promise<Account[]> {
  const res = await fetch(`${BASE_URL}/accounts`)
  return handleResponse<Account[]>(res)
}

export async function createAccount(data: CreateAccountInput): Promise<Account> {
  const res = await fetch(`${BASE_URL}/accounts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return handleResponse<Account>(res)
}

export async function fetchTransactions(): Promise<Transaction[]> {
  const res = await fetch(`${BASE_URL}/transactions`)
  return handleResponse<Transaction[]>(res)
}

export async function createTransaction(data: CreateTransactionInput): Promise<Transaction> {
  const res = await fetch(`${BASE_URL}/transactions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': data.idempotency_key,
    },
    body: JSON.stringify(data),
  })
  return handleResponse<Transaction>(res)
}

export async function reverseTransaction(id: number, reason?: string): Promise<Transaction> {
  const idempotency_key = `rev-${id}-${Date.now()}`
  const res = await fetch(`${BASE_URL}/transactions/${id}/reversal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key, reason }),
  })
  return handleResponse<Transaction>(res)
}

export async function fetchTrialBalance(): Promise<TrialBalanceReport> {
  const res = await fetch(`${BASE_URL}/reports/trial-balance`)
  return handleResponse<TrialBalanceReport>(res)
}

export async function fetchAccountStatement(accountId: number): Promise<AccountStatementResponse> {
  const res = await fetch(`${BASE_URL}/accounts/${accountId}/statement`)
  return handleResponse<AccountStatementResponse>(res)
}
