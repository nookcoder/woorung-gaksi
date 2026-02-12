"""
KIS (Korea Investment & Securities) Open API Client
====================================================
REST API 직접 호출 방식. kis_auth SDK 없이 독립 동작.

인증: OAuth 2.0 → access_token 발급 후 재사용.
Base URL:
  - 실전투자: https://openapi.koreainvestment.com:9443
  - 모의투자: https://openapivts.koreainvestment.com:29443
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import requests
import pandas as pd

logger = logging.getLogger(__name__)


class KISClient:
    """한국투자증권 Open API REST 클라이언트."""

    # ── 실전/모의 Base URL ──
    REAL_URL = "https://openapi.koreainvestment.com:9443"
    DEMO_URL = "https://openapivts.koreainvestment.com:29443"

    def __init__(
        self,
        app_key: str = None,
        app_secret: str = None,
        account_no: str = None,
        is_demo: bool = False,
    ):
        self.app_key = app_key or os.getenv("KIS_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("KIS_APP_SECRET", "")
        self.account_no = account_no or os.getenv("KIS_ACCOUNT_NO", "")
        self.is_demo = is_demo
        self.base_url = self.DEMO_URL if is_demo else self.REAL_URL

        self._access_token: Optional[str] = None
        self._token_expired_at: float = 0

    # ═══════════════════════════════════════════════════════════
    # Authentication
    # ═══════════════════════════════════════════════════════════

    def _ensure_token(self) -> str:
        """토큰이 없거나 만료됐으면 재발급."""
        if self._access_token and time.time() < self._token_expired_at:
            return self._access_token

        url = f"{self.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        # 토큰 유효시간: 약 24h → 23h 후 갱신
        self._token_expired_at = time.time() + 23 * 3600
        logger.info("[KIS] Access token issued")
        return self._access_token

    def _headers(self, tr_id: str) -> Dict[str, str]:
        """공통 요청 헤더."""
        token = self._ensure_token()
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _get(self, path: str, tr_id: str, params: Dict[str, str]) -> Dict[str, Any]:
        """GET 요청 공통."""
        url = f"{self.base_url}{path}"
        headers = self._headers(tr_id)
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            logger.warning(f"[KIS] API error: {data.get('msg1', 'unknown')}")
        return data

    # ═══════════════════════════════════════════════════════════
    # 국내주식 시세
    # ═══════════════════════════════════════════════════════════

    def get_current_price(self, ticker: str) -> Dict[str, Any]:
        """
        주식현재가 시세 [FHKST01010100]
        GET /uapi/domestic-stock/v1/quotations/inquire-price
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            params,
        )
        return data.get("output", {})

    def get_daily_price(
        self, ticker: str, start_date: str, end_date: str, period: str = "D"
    ) -> pd.DataFrame:
        """
        국내주식기간별시세 (일/주/월/년) [FHKST03010100]
        GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemprice
        """
        all_rows = []
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_DATE_1": start_date.replace("-", ""),
            "FID_INPUT_DATE_2": end_date.replace("-", ""),
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",  # 수정주가
        }

        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemprice",
            "FHKST03010100",
            params,
        )
        rows = data.get("output2", [])
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "Date": pd.to_datetime(r.get("stck_bsop_date", "")),
                    "Open": int(r.get("stck_oprc", 0)),
                    "High": int(r.get("stck_hgpr", 0)),
                    "Low": int(r.get("stck_lwpr", 0)),
                    "Close": int(r.get("stck_clpr", 0)),
                    "Volume": int(r.get("acml_vol", 0)),
                    "Change": float(r.get("prdy_ctrt", 0)),
                })
            except (ValueError, TypeError):
                continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.set_index("Date").sort_index()
        return df

    # ═══════════════════════════════════════════════════════════
    # 투자자별 매매동향 (종목별)
    # ═══════════════════════════════════════════════════════════

    def get_investor_trading(self, ticker: str) -> pd.DataFrame:
        """
        주식현재가 투자자 [FHKST01010900]
        GET /uapi/domestic-stock/v1/quotations/inquire-investor

        최근 30 거래일의 외국인/기관/개인 순매수 데이터.
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            "FHKST01010900",
            params,
        )
        rows = data.get("output", [])
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "Date": pd.to_datetime(r.get("stck_bsop_date", "")),
                    "foreigner_net_qty": int(r.get("frgn_ntby_qty", 0)),
                    "institution_net_qty": int(r.get("orgn_ntby_qty", 0)),
                    "individual_net_qty": int(r.get("prsn_ntby_qty", 0)),
                    "foreigner_net_amt": int(r.get("frgn_ntby_tr_pbmn", 0)),
                    "institution_net_amt": int(r.get("orgn_ntby_tr_pbmn", 0)),
                    "individual_net_amt": int(r.get("prsn_ntby_tr_pbmn", 0)),
                })
            except (ValueError, TypeError):
                continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.set_index("Date").sort_index()
        return df

    # ═══════════════════════════════════════════════════════════
    # 업종 시세
    # ═══════════════════════════════════════════════════════════

    def get_sector_index(self, sector_code: str) -> Dict[str, Any]:
        """
        국내주식 업종현재지수 [FHPUP02100000]
        GET /uapi/domestic-stock/v1/quotations/inquire-index-price
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": sector_code,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            "FHPUP02100000",
            params,
        )
        return data.get("output", {})

    def get_sector_daily(
        self, sector_code: str, start_date: str, end_date: str, period: str = "D"
    ) -> pd.DataFrame:
        """
        국내주식 업종기간별시세 [FHKUP03500100]
        GET /uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": sector_code,
            "FID_INPUT_DATE_1": start_date.replace("-", ""),
            "FID_INPUT_DATE_2": end_date.replace("-", ""),
            "FID_PERIOD_DIV_CODE": period,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice",
            "FHKUP03500100",
            params,
        )
        rows = data.get("output2", [])
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "Date": pd.to_datetime(r.get("stck_bsop_date", "")),
                    "Close": float(r.get("bstp_nmix_prpr", 0)),
                    "Open": float(r.get("bstp_nmix_oprc", 0)),
                    "High": float(r.get("bstp_nmix_hgpr", 0)),
                    "Low": float(r.get("bstp_nmix_lwpr", 0)),
                    "Volume": int(r.get("acml_vol", 0)),
                })
            except (ValueError, TypeError):
                continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.set_index("Date").sort_index()
        return df

    # ═══════════════════════════════════════════════════════════
    # 시장별 투자자 매매동향 (시장 전체)
    # ═══════════════════════════════════════════════════════════

    def get_market_investor_daily(
        self, market: str = "KOSPI", start_date: str = None, end_date: str = None
    ) -> pd.DataFrame:
        """
        시장별 투자자매매동향 (일별) [FHPTJ04010200]
        GET /uapi/domestic-stock/v1/quotations/inquire-investor-daily

        시장 전체의 외국인/기관/개인 일별 매매동향.
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        market_code = "0001" if market == "KOSPI" else "1001"  # KOSPI / KOSDAQ
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": market_code,
            "FID_INPUT_DATE_1": start_date.replace("-", ""),
            "FID_INPUT_DATE_2": end_date.replace("-", ""),
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor-daily",
            "FHPTJ04010200",
            params,
        )
        rows = data.get("output", [])
        if not rows:
            return pd.DataFrame()

        records = []
        for r in rows:
            try:
                records.append({
                    "Date": pd.to_datetime(r.get("stck_bsop_date", "")),
                    "foreigner_net_amt": int(r.get("frgn_ntby_tr_pbmn", 0)),
                    "institution_net_amt": int(r.get("orgn_ntby_tr_pbmn", 0)),
                    "individual_net_amt": int(r.get("prsn_ntby_tr_pbmn", 0)),
                })
            except (ValueError, TypeError):
                continue

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.set_index("Date").sort_index()
        return df

    # ═══════════════════════════════════════════════════════════
    # 종목 기본 정보 (PER, PBR, 시총 등)
    # ═══════════════════════════════════════════════════════════

    def get_stock_info(self, ticker: str) -> Dict[str, Any]:
        """
        주식현재가 시세 + 추가 지표 [FHKST01010100]
        PER, PBR, EPS, BPS, 시가총액(HTS_AVLS) 등.
        """
        output = self.get_current_price(ticker)
        return {
            "per": float(output.get("per", 0) or 0),
            "pbr": float(output.get("pbr", 0) or 0),
            "eps": float(output.get("eps", 0) or 0),
            "bps": float(output.get("bps", 0) or 0),
            "market_cap": int(output.get("hts_avls", 0) or 0),  # 억원 단위
            "trading_value": int(output.get("acml_tr_pbmn", 0) or 0),  # 거래대금
            "volume": int(output.get("acml_vol", 0) or 0),
            "current_price": int(output.get("stck_prpr", 0) or 0),
            "change_rate": float(output.get("prdy_ctrt", 0) or 0),
            "w52_high": int(output.get("stck_dryy_hgpr", 0) or 0),
            "w52_low": int(output.get("stck_dryy_lwpr", 0) or 0),
        }

    # ═══════════════════════════════════════════════════════════
    # 프로그램 매매동향 (종목별)
    # ═══════════════════════════════════════════════════════════

    def get_program_trading(self, ticker: str) -> Dict[str, Any]:
        """
        주식현재가 프로그램매매 [FHKST01010200]
        GET /uapi/domestic-stock/v1/quotations/inquire-member
        (비차익/차익 매매 데이터)
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-member",
            "FHKST01010200",
            params,
        )
        return data.get("output", {})

    # ═══════════════════════════════════════════════════════════
    # 국내 주가지수 (KOSPI, KOSDAQ 등)
    # ═══════════════════════════════════════════════════════════

    def get_index_price(self, index_code: str = "0001") -> Dict[str, Any]:
        """
        업종 현재 지수.
        0001: KOSPI, 1001: KOSDAQ, 2001: KOSPI200
        """
        return self.get_sector_index(index_code)

    # ═══════════════════════════════════════════════════════════
    # 업종별 종목 리스트
    # ═══════════════════════════════════════════════════════════

    def get_sector_tickers(self, sector_code: str) -> List[str]:
        """
        업종별 종목 리스트 조회 [FHKST03010500]
        GET /uapi/domestic-stock/v1/quotations/inquire-index-category-item-list
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": sector_code,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-index-category-item-list",
            "FHKST03010500",
            params,
        )
        rows = data.get("output", [])
        return [r.get("stck_shrn_iscd", "") for r in rows if r.get("stck_shrn_iscd")]

    # ═══════════════════════════════════════════════════════════
    # 재무 정보 (F-Score용)
    # ═══════════════════════════════════════════════════════════

    def get_financial_statements(self, ticker: str) -> Dict[str, Any]:
        """
        주식현재가 재무표 [FHKST03020800]
        최근 연간/분기 재무제표 요약.
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
        }
        data = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-financial-statement",
            "FHKST03020800",
            params,
        )
        # KIS API는 output이 여러 개일 수 있음. 보통 output은 요약 데이터.
        return data.get("output", {})

    # ═══════════════════════════════════════════════════════════
    # Helper: API key 유효성 검사
    # ═══════════════════════════════════════════════════════════

    @property
    def is_configured(self) -> bool:
        """API key가 설정되어 있는지 확인."""
        return bool(self.app_key and self.app_secret)
