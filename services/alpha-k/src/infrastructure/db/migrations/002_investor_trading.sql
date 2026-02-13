-- 002_investor_trading.sql
-- 투자자별 매매동향 테이블 (종목별)

-- 1. 종목별 투자자 매매동향 (Hypertable)
CREATE TABLE IF NOT EXISTS investor_trading (
    time TIMESTAMPTZ NOT NULL,
    ticker_code VARCHAR(10) NOT NULL,
    foreigner_net_qty BIGINT DEFAULT 0,     -- 외국인 순매수 수량
    institution_net_qty BIGINT DEFAULT 0,   -- 기관 순매수 수량
    individual_net_qty BIGINT DEFAULT 0,    -- 개인 순매수 수량
    foreigner_net_amt BIGINT DEFAULT 0,     -- 외국인 순매수 금액 (원)
    institution_net_amt BIGINT DEFAULT 0,   -- 기관 순매수 금액 (원)
    individual_net_amt BIGINT DEFAULT 0,    -- 개인 순매수 금액 (원)

    PRIMARY KEY (time, ticker_code)
);

SELECT create_hypertable('investor_trading', 'time', if_not_exists => TRUE);

-- 인덱스: 종목별 최근 조회 가속
CREATE INDEX IF NOT EXISTS idx_investor_ticker_time
    ON investor_trading (ticker_code, time DESC);

-- 압축 정책
ALTER TABLE investor_trading SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_code'
);
SELECT add_compression_policy('investor_trading', INTERVAL '30 days');
