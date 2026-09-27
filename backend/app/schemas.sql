-- Schema definition for double-entry ledger

CREATE TABLE IF NOT EXISTS accounts (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(32) NOT NULL CHECK (type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    allow_negative BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(32) NOT NULL DEFAULT 'POSTED' CHECK (status IN ('POSTED', 'REVERSED')),
    reversal_of_id BIGINT REFERENCES transactions(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS postings (
    id BIGSERIAL PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    direction VARCHAR(6) NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    amount NUMERIC(18, 4) NOT NULL CHECK (amount > 0 AND round(amount, 4) = amount),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices de consulta frecuente
CREATE INDEX IF NOT EXISTS idx_postings_transaction_id ON postings(transaction_id);
CREATE INDEX IF NOT EXISTS idx_postings_account_id ON postings(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_posted_at ON transactions(posted_at);
CREATE INDEX IF NOT EXISTS idx_transactions_idempotency ON transactions(idempotency_key);

-- Vista de saldos acumulados por cuenta
DROP VIEW IF EXISTS account_balances CASCADE;
CREATE OR REPLACE VIEW account_balances AS
SELECT
    a.id AS account_id,
    a.code,
    a.name,
    a.type,
    a.currency,
    a.allow_negative,
    a.created_at,
    COALESCE(SUM(CASE WHEN p.direction = 'DEBIT' THEN p.amount ELSE 0 END), 0) AS total_debit,
    COALESCE(SUM(CASE WHEN p.direction = 'CREDIT' THEN p.amount ELSE 0 END), 0) AS total_credit,
    CASE
        WHEN a.type IN ('ASSET', 'EXPENSE') THEN
            COALESCE(SUM(CASE WHEN p.direction = 'DEBIT' THEN p.amount ELSE -p.amount END), 0)
        ELSE
            COALESCE(SUM(CASE WHEN p.direction = 'CREDIT' THEN p.amount ELSE -p.amount END), 0)
    END AS balance
FROM accounts a
LEFT JOIN postings p ON a.id = p.account_id
GROUP BY a.id, a.code, a.name, a.type, a.currency, a.allow_negative, a.created_at;

-- 1. Regla de negocio en BD: Invariante de suma cero por transacción
-- Se valida al hacer COMMIT gracias a DEFERRABLE INITIALLY DEFERRED
CREATE OR REPLACE FUNCTION check_transaction_balanced()
RETURNS TRIGGER AS $$
DECLARE
    v_balance NUMERIC(18, 4);
    v_count INTEGER;
BEGIN
    SELECT
        COALESCE(SUM(CASE WHEN direction = 'DEBIT' THEN amount ELSE -amount END), 0),
        COUNT(*)
    INTO v_balance, v_count
    FROM postings
    WHERE transaction_id = NEW.transaction_id;

    IF v_count < 2 THEN
        RAISE EXCEPTION 'Transaction % must contain at least 2 postings (found %)', NEW.transaction_id, v_count
            USING ERRCODE = 'check_violation';
    END IF;

    IF v_balance <> 0 THEN
        RAISE EXCEPTION 'Transaction % is unbalanced: debits minus credits is %', NEW.transaction_id, v_balance
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_transaction_balanced ON postings;
CREATE CONSTRAINT TRIGGER trg_check_transaction_balanced
AFTER INSERT OR UPDATE ON postings
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION check_transaction_balanced();

-- 2. Regla de negocio en BD: Inmutabilidad estricta de postings
CREATE OR REPLACE FUNCTION prevent_posting_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Ledger postings are strictly immutable: updates and deletions are forbidden'
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_posting_update_delete ON postings;
CREATE TRIGGER trg_prevent_posting_update_delete
BEFORE UPDATE OR DELETE ON postings
FOR EACH ROW
EXECUTE FUNCTION prevent_posting_mutation();

-- 3. Regla de negocio en BD: Inmutabilidad de transacciones (solo se permite marcar REVERSED)
CREATE OR REPLACE FUNCTION prevent_transaction_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Ledger transactions are strictly immutable: deletions are forbidden'
            USING ERRCODE = 'integrity_constraint_violation';
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status = 'REVERSED' THEN
            RAISE EXCEPTION 'Cannot modify an already reversed transaction'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.id <> OLD.id 
           OR NEW.idempotency_key <> OLD.idempotency_key 
           OR NEW.posted_at <> OLD.posted_at 
           OR NEW.description <> OLD.description 
           OR NEW.reversal_of_id IS DISTINCT FROM OLD.reversal_of_id THEN
            RAISE EXCEPTION 'Ledger transaction fields are immutable except status'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.status NOT IN ('POSTED', 'REVERSED') THEN
            RAISE EXCEPTION 'Invalid transaction status: %', NEW.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_transaction_update_delete ON transactions;
CREATE TRIGGER trg_prevent_transaction_update_delete
BEFORE UPDATE OR DELETE ON transactions
FOR EACH ROW
EXECUTE FUNCTION prevent_transaction_mutation();
