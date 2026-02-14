-- 003_financials.sql

-- 1. 재무제표 (Quarterly/Annual)
-- KIS API output structure matching + FundamentalAgent requirements
CREATE TABLE IF NOT EXISTS financial_statements (
    ticker_code VARCHAR(10) NOT NULL,
    period_code VARCHAR(10) NOT NULL, -- e.g., '2023.12', '2024.03'
    report_type VARCHAR(10) DEFAULT 'Quarterly', -- 'Quarterly', 'Annual'
    
    -- 기본 재무제표
    total_assets BIGINT,
    total_liabilities BIGINT,
    total_equity BIGINT,
    current_assets BIGINT,
    current_liabilities BIGINT,
    
    revenue BIGINT,
    operating_income BIGINT,
    net_income BIGINT,
    gross_profit BIGINT,
    
    operating_cash_flow BIGINT,
    
    -- 주식수
    total_shares BIGINT,
    
    -- 비율 (직접 계산하여 저장하거나 API 값 사용)
    eps NUMERIC(12, 2),
    bps NUMERIC(12, 2),
    
    gross_margin NUMERIC(10, 4),     -- 0.1534
    operating_margin NUMERIC(10, 4),
    net_margin NUMERIC(10, 4),
    
    roa NUMERIC(10, 4),
    roe NUMERIC(10, 4),
    current_ratio NUMERIC(10, 4),    -- 1.5 = 150%
    debt_ratio NUMERIC(10, 4),       -- 0.5 = 50%
    asset_turnover NUMERIC(10, 4),

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (ticker_code, period_code, report_type)
);

CREATE INDEX IF NOT EXISTS idx_financials_ticker ON financial_statements(ticker_code);
