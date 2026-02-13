-- 001_init.sql
-- TimescaleDB Extension이 이미 설치되어 있다고 가정 (이미지 포함)
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. 종목 마스터 테이블 (Tickers)
CREATE TABLE IF NOT EXISTS tickers (
    ticker_code VARCHAR(10) PRIMARY KEY,
    ticker_name VARCHAR(100) NOT NULL,
    market_type VARCHAR(10), -- KOSPI, KOSDAQ
    sector_code VARCHAR(10),
    industry VARCHAR(100),
    listing_date DATE,
    delisting_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스: 종목명 검색, 섹터별 조회
CREATE INDEX IF NOT EXISTS idx_tickers_name ON tickers(ticker_name);
CREATE INDEX IF NOT EXISTS idx_tickers_sector ON tickers(sector_code);

-- 2. 일봉 데이터 (Hypertable)
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    time TIMESTAMPTZ NOT NULL,
    ticker_code VARCHAR(10) NOT NULL,
    open NUMERIC(12, 2),
    high NUMERIC(12, 2),
    low NUMERIC(12, 2),
    close NUMERIC(12, 2),
    volume BIGINT,
    trading_value BIGINT, -- 거래대금
    change_rate NUMERIC(6, 4), -- 등락률
    ma5 NUMERIC(12, 2),
    ma20 NUMERIC(12, 2),
    ma60 NUMERIC(12, 2),
    rsi_14 NUMERIC(6, 2),
    
    PRIMARY KEY (time, ticker_code)
);

-- TimescaleDB Hypertable 변환 (시간축 파티셔닝)
SELECT create_hypertable('ohlcv_daily', 'time', if_not_exists => TRUE);

-- 압축 설정 (오래된 데이터 디스크 절약)
ALTER TABLE ohlcv_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_code'
);
SELECT add_compression_policy('ohlcv_daily', INTERVAL '30 days');

-- 3. 분봉 데이터 (Hypertable)
CREATE TABLE IF NOT EXISTS ohlcv_minute (
    time TIMESTAMPTZ NOT NULL,
    ticker_code VARCHAR(10) NOT NULL,
    open NUMERIC(12, 2),
    high NUMERIC(12, 2),
    low NUMERIC(12, 2),
    close NUMERIC(12, 2),
    volume BIGINT,
    
    PRIMARY KEY (time, ticker_code)
);

SELECT create_hypertable('ohlcv_minute', 'time', if_not_exists => TRUE);

ALTER TABLE ohlcv_minute SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker_code'
);
-- 분봉은 데이터가 많으므로 7일 지나면 압축
SELECT add_compression_policy('ohlcv_minute', INTERVAL '7 days');


-- 4. 섹터 지수 (Sector Index)
CREATE TABLE IF NOT EXISTS sector_indices (
    time TIMESTAMPTZ NOT NULL,
    sector_code VARCHAR(10) NOT NULL,
    sector_name VARCHAR(50),
    close NUMERIC(12, 2),
    change_rate NUMERIC(6, 4),
    
    PRIMARY KEY (time, sector_code)
);

SELECT create_hypertable('sector_indices', 'time', if_not_exists => TRUE);
