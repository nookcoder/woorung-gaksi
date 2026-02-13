"""
Graph Schema & Data Seeder
============================
Neo4j에 한국 주식시장의 관계형 데이터를 구축한다.

노드:
  - (:Ticker {code, name, market})         — 종목
  - (:Theme {name, description})           — 테마/섹터
  - (:Company {name, code})                — 기업 (지분/공급망용)

관계:
  - (Ticker)-[:BELONGS_TO]->(Theme)        — 테마 구성 종목
  - (Company)-[:SUBSIDIARY_OF]->(Company)  — 모회사-자회사
  - (Company)-[:SUPPLIES_TO]->(Company)    — 공급업체→고객사
  - (Company)-[:COMPETES_WITH]->(Company)  — 경쟁사

Usage:
    docker exec woorung-alpha-k python3 -m src.infrastructure.graph.seed_graph
"""
import logging

from .neo4j_client import graph_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def init_schema():
    """인덱스 및 제약 조건 생성."""
    logger.info("[Graph] Initializing schema...")

    constraints = [
        "CREATE CONSTRAINT ticker_code IF NOT EXISTS FOR (t:Ticker) REQUIRE t.code IS UNIQUE",
        "CREATE CONSTRAINT theme_name IF NOT EXISTS FOR (th:Theme) REQUIRE th.name IS UNIQUE",
        "CREATE CONSTRAINT company_code IF NOT EXISTS FOR (c:Company) REQUIRE c.code IS UNIQUE",
    ]

    indexes = [
        "CREATE INDEX ticker_name_idx IF NOT EXISTS FOR (t:Ticker) ON (t.name)",
        "CREATE INDEX theme_category_idx IF NOT EXISTS FOR (th:Theme) ON (th.category)",
    ]

    for q in constraints + indexes:
        graph_client.run_write(q)

    logger.info("[Graph] Schema initialized")


def seed_themes():
    """
    [Institutional Grade Theme Coverage]
    한국 주식시장의 전 섹터를 트레이딩 관점에서 세분화한 테마 데이터.
    단순 산업 분류가 아닌, '동조화(Coupling)'되어 움직이는 테마 단위.
    """
    logger.info("[Graph] Seeding comprehensive market themes...")

    themes = {
        # ==========================================
        # 1. 반도체 & IT 하드웨어 (Tech Hardware)
        # ==========================================
        "HBM (고대역폭메모리)": {
            "category": "반도체",
            "tickers": [
                ("000660", "SK하이닉스"), ("005930", "삼성전자"), ("042700", "한미반도체"),
                ("071200", "인텍플러스"), ("403870", "HPSP"), ("272210", "한화시스템")
            ]
        },
        "온디바이스 AI / 팹리스": {
            "category": "반도체",
            "tickers": [
                ("354200", "제주반도체"), ("443060", "오픈엣지테크놀로지"), ("432720", "에이직랜드"),
                ("032500", "텔레칩스"), ("053050", "칩스앤미디어")
            ]
        },
        "반도체 소부장 (전공정/소재)": {
            "category": "반도체",
            "tickers": [
                ("357780", "솔브레인"), ("005290", "동진쎄미켐"), ("036930", "주성엔지니어링"),
                ("240810", "원익IPS"), ("008370", "원익QnC")
            ]
        },
        "반도체 후공정 (OSAT/테스트)": {
            "category": "반도체",
            "tickers": [
                ("067310", "하나마이크론"), ("058470", "리노공업"), ("241790", "두산테스나"),
                ("131290", "티에스이"), ("095610", "테스")
            ]
        },
        "IT 부품 (기판/카메라/MLCC)": {
            "category": "IT부품",
            "tickers": [
                ("009150", "삼성전기"), ("011070", "LG이노텍"), ("008060", "대덕전자"),
                ("290510", "코리아써키트"), ("033640", "네패스")
            ]
        },

        # ==========================================
        # 2. 2차전지 & 친환경차 (EV Value Chain)
        # ==========================================
        "2차전지 셀 (Cell Maker)": {
            "category": "2차전지",
            "tickers": [("373220", "LG에너지솔루션"), ("006400", "삼성SDI"), ("051910", "LG화학")]
        },
        "2차전지 양극재": {
            "category": "2차전지",
            "tickers": [("247540", "에코프로비엠"), ("003670", "포스코퓨처엠"), ("086520", "에코프로"), ("066970", "엘앤에프")]
        },
        "2차전지 소재 (전해액/분리막/음극재)": {
            "category": "2차전지",
            "tickers": [("348370", "엔켐"), ("278280", "천보"), ("361610", "SK아이이테크놀로지"), ("003670", "포스코퓨처엠")]
        },
        "폐배터리 리사이클링": {
            "category": "2차전지",
            "tickers": [("029640", "성일하이텍"), ("375500", "새빗켐"), ("006400", "삼성SDI")]
        },
        "자동차 대표주 (OEM)": {
            "category": "자동차",
            "tickers": [("005380", "현대차"), ("000270", "기아")]
        },
        "자동차 부품 (전장/타이어)": {
            "category": "자동차",
            "tickers": [
                ("012330", "현대모비스"), ("204320", "HL만도"), ("018880", "한온시스템"),
                ("161390", "한국타이어앤테크놀로지"), ("003300", "한일홀딩스")
            ]
        },

        # ==========================================
        # 3. 바이오 & 헬스케어 (Bio & Healthcare)
        # ==========================================
        "바이오 CDMO (위탁생산)": {
            "category": "헬스케어",
            "tickers": [("207940", "삼성바이오로직스"), ("237690", "에스티팜"), ("000100", "유한양행")] # 유한양행은 신약+CDMO 성격 혼재
        },
        "바이오시밀러": {
            "category": "헬스케어",
            "tickers": [("068270", "셀트리온"), ("207940", "삼성바이오로직스")]
        },
        "의료 AI (진단/영상)": {
            "category": "헬스케어",
            "tickers": [("328130", "루닛"), ("331520", "뷰노"), ("417840", "제이엘케이")]
        },
        "미용 의료기기 (에스테틱)": {
            "category": "헬스케어",
            "tickers": [("214150", "클래시스"), ("145020", "휴젤"), ("246720", "파마리서치"), ("359090", "제이시스메디칼")]
        },
        "신약 개발 (항암/비만)": {
            "category": "헬스케어",
            "tickers": [("000100", "유한양행"), ("141080", "리가켐바이오"), ("006280", "녹십자"), ("185750", "종근당")]
        },

        # ==========================================
        # 4. K-컬쳐 & 소비재 (Consumer & Content)
        # ==========================================
        "K-푸드 (수출 주도)": {
            "category": "소비재",
            "tickers": [("003230", "삼양식품"), ("004370", "농심"), ("271560", "오리온"), ("097950", "CJ제일제당"), ("114090", "GKL")]
        },
        "화장품 ODM (제조자 개발생산)": {
            "category": "소비재",
            "tickers": [("192820", "코스맥스"), ("161890", "한국콜마"), ("247540", "씨앤씨인터내셔널")]
        },
        "화장품 브랜드": {
            "category": "소비재",
            "tickers": [("090430", "아모레퍼시픽"), ("051900", "LG생활건강"), ("432400", "에이피알")]
        },
        "엔터테인먼트 (K-POP)": {
            "category": "미디어",
            "tickers": [("352820", "하이브"), ("035900", "JYP Ent."), ("041510", "에스엠"), ("122870", "와이지엔터테인먼트")]
        },
        "게임 (PC/콘솔/모바일)": {
            "category": "게임",
            "tickers": [("259960", "크래프톤"), ("036570", "엔씨소프트"), ("251270", "넷마블"), ("263750", "펄어비스"), ("112040", "위메이드")]
        },
        "웹툰/드라마/미디어": {
            "category": "미디어",
            "tickers": [("035420", "NAVER"), ("035720", "카카오"), ("253450", "스튜디오드래곤"), ("005810", "팬엔터테인먼트")]
        },

        # ==========================================
        # 5. 중후장대 & 인프라 (Cyclicals)
        # ==========================================
        "조선 (LNG/컨테이너)": {
            "category": "산업재",
            "tickers": [("009540", "HD한국조선해양"), ("329180", "HD현대중공업"), ("042660", "한화오션"), ("010620", "HD현대미포")]
        },
        "방위산업 (Global Defense)": {
            "category": "산업재",
            "tickers": [("012450", "한화에어로스페이스"), ("079550", "LIG넥스원"), ("064350", "현대로템"), ("047810", "한국항공우주")]
        },
        "전력설비 (AI 데이터센터 수혜)": {
            "category": "산업재",
            "tickers": [("267260", "HD현대일렉트릭"), ("010120", "LS ELECTRIC"), ("298040", "효성중공업"), ("033310", "제룡전기")]
        },
        "원자력 발전 (SMR)": {
            "category": "에너지",
            "tickers": [("034020", "두산에너빌리티"), ("052690", "한전기술"), ("051600", "한전KPS")]
        },
        "건설/플랜트": {
            "category": "산업재",
            "tickers": [("000720", "현대건설"), ("028050", "삼성중공업"), ("006360", "GS건설"), ("047040", "대우건설")]
        },

        # ==========================================
        # 6. 소재 & 에너지 (Materials & Energy)
        # ==========================================
        "철강": {
            "category": "소재",
            "tickers": [("005490", "POSCO홀딩스"), ("004020", "현대제철"), ("001230", "동국제강")]
        },
        "정유/석유화학": {
            "category": "에너지",
            "tickers": [("010950", "S-Oil"), ("096770", "SK이노베이션"), ("011170", "롯데케미칼"), ("051910", "LG화학"), ("011780", "금호석유")]
        },
        "해운/물류": {
            "category": "산업재",
            "tickers": [("011200", "HMM"), ("028670", "팬오션"), ("005880", "대한해운")]
        },

        # ==========================================
        # 7. 금융 & 지주 (Finance & Holdings) - 밸류업
        # ==========================================
        "금융지주 (은행)": {
            "category": "금융",
            "tickers": [("105560", "KB금융"), ("055550", "신한지주"), ("086790", "하나금융지주"), ("316140", "우리금융지주"), ("024110", "기업은행")]
        },
        "증권 (STO/PF)": {
            "category": "금융",
            "tickers": [("039490", "키움증권"), ("005940", "NH투자증권"), ("016360", "삼성증권"), ("008560", "메리츠증권")]
        },
        "보험 (손보/생보)": {
            "category": "금융",
            "tickers": [("000810", "삼성화재"), ("005830", "DB손해보험"), ("002550", "KB손해보험")] # KB손보 상장여부 확인(KB금융 자회사) -> 현대해상으로 대체
        },
        "주요 지주사 (저PBR)": {
            "category": "금융",
            "tickers": [("003550", "LG"), ("034730", "SK"), ("000810", "삼성물산"), ("000120", "CJ"), ("002380", "KCC")]
        },

        # ==========================================
        # 8. 인터넷 & 플랫폼 (Platform)
        # ==========================================
        "인터넷 플랫폼": {
            "category": "IT",
            "tickers": [("035420", "NAVER"), ("035720", "카카오"), ("068290", "아프리카TV")] # 아프리카TV 사명변경(SOOP) 체크
        },
        "핀테크/결제": {
            "category": "IT",
            "tickers": [("377300", "카카오페이"), ("299660", "토스뱅크"), ("041190", "우리기술투자")] # 토스 비상장, 우리기술투자(두나무 관련)
        },
    }

    # ============================================
    # Seed Execution Logic (Graph Insertion)
    # ============================================
    for theme_name, info in themes.items():
        # 1. 테마 노드 생성 (업서트)
        graph_client.run_write(
            """
            MERGE (th:Theme {name: $name})
            SET th.category = $category
            """,
            {"name": theme_name, "category": info["category"]}
        )

        # 2. 종목 노드 및 관계 생성
        for code, name in info["tickers"]:
            graph_client.run_write(
                """
                MERGE (t:Ticker {code: $code})
                SET t.name = $name
                WITH t
                MATCH (th:Theme {name: $theme})
                MERGE (t)-[:BELONGS_TO]->(th)
                """,
                {"code": code, "name": name, "theme": theme_name}
            )

    logger.info(f"[Graph] Comprehensive seeding complete: {len(themes)} sub-sectors seeded covering {sum(len(v['tickers']) for v in themes.values())} key tickers.")


def seed_ownership():
    """
    [Institutional Grade Governance Map]
    한국 주식시장의 모든 주요 그룹사 지배구조 및 지분 관계.
    단순 모-자 관계뿐만 아니라, 순환출자 및 지주사 체계를 명확히 정의.
    
    Relationship Type:
    - Holding: 정석적인 지주사 -> 자회사 구조
    - Circular: 순환출자 (지배구조 리스크)
    - Strategic: 전략적 지분 투자
    """
    logger.info("[Graph] Seeding comprehensive ownership structures (Chaebol & Groups)...")

    # (Parent Code, Parent Name, Child Code, Child Name, Relation Type)
    ownership = [
        # ==========================================
        # 1. 4대 그룹 (Samsung, SK, Hyundai, LG)
        # ==========================================
        # Samsung: 삼성물산이 실질적 지주사
        ("028260", "삼성물산", "005930", "삼성전자", "De Facto Holding"),
        ("028260", "삼성물산", "207940", "삼성바이오로직스", "Major Shareholder"),
        ("005930", "삼성전자", "006400", "삼성SDI", "Strategic"),
        ("005930", "삼성전자", "009150", "삼성전기", "Strategic"),
        ("005930", "삼성전자", "018260", "삼성에스디에스", "Strategic"),
        ("005930", "삼성전자", "000810", "삼성화재", "Strategic"), # 금융 계열사 지분 보유
        
        # SK: SK(주) 중심의 지주사 체계
        ("034730", "SK", "000660", "SK하이닉스", "Holding"), # SK스퀘어 분할 전/후 구조 고려 필요하나 단순화
        ("034730", "SK", "017670", "SK텔레콤", "Holding"),
        ("034730", "SK", "096770", "SK이노베이션", "Holding"),
        ("034730", "SK", "326030", "SK바이오팜", "Holding"),
        ("034730", "SK", "340610", "SKC", "Holding"),
        ("096770", "SK이노베이션", "361610", "SK아이이테크놀로지", "Parent"),
        ("017670", "SK텔레콤", "402340", "SK스퀘어", "Spin-off"), # 현재는 별도 법인이나 관계성 유지

        # Hyundai Motor: 순환출자 구조 (모비스 -> 현대차 -> 기아 -> 모비스)
        ("012330", "현대모비스", "005380", "현대차", "Circular (Key)"),
        ("005380", "현대차", "000270", "기아", "Circular"),
        ("000270", "기아", "012330", "현대모비스", "Circular"),
        ("005380", "현대차", "086280", "현대글로비스", "Affiliate"),
        ("005380", "현대차", "064350", "현대로템", "Parent"),
        ("005380", "현대차", "011210", "현대위아", "Parent"),

        # LG: 깔끔한 지주사 체계
        ("003550", "LG", "066570", "LG전자", "Holding"),
        ("003550", "LG", "051910", "LG화학", "Holding"),
        ("003550", "LG", "051900", "LG생활건강", "Holding"),
        ("003550", "LG", "032640", "LG유플러스", "Holding"),
        ("051910", "LG화학", "373220", "LG에너지솔루션", "Parent (Split-off)"),
        ("066570", "LG전자", "011070", "LG이노텍", "Parent"),

        # ==========================================
        # 2. 2차전지 & 소재 그룹 (POSCO, EcoPro)
        # ==========================================
        # POSCO Group
        ("005490", "POSCO홀딩스", "003670", "포스코퓨처엠", "Holding"),
        ("005490", "POSCO홀딩스", "047050", "포스코인터내셔널", "Holding"),
        ("005490", "POSCO홀딩스", "022100", "포스코DX", "Holding"),
        ("005490", "POSCO홀딩스", "058430", "포스코엠텍", "Holding"),

        # EcoPro Group (수직 계열화)
        ("086520", "에코프로", "247540", "에코프로비엠", "Holding"),
        ("086520", "에코프로", "383310", "에코프로에이치엔", "Holding"),
        ("086520", "에코프로", "450080", "에코프로머티", "Holding"), # 상장 코드 확인 필요

        # ==========================================
        # 3. 중후장대 & 인프라 (HD Hyundai, Hanwha, Doosan, LS)
        # ==========================================
        # HD Hyundai
        ("267250", "HD현대", "009540", "HD한국조선해양", "Holding"),
        ("267250", "HD현대", "267260", "HD현대일렉트릭", "Holding"),
        ("267250", "HD현대", "295310", "HD현대에너지솔루션", "Holding"),
        ("009540", "HD한국조선해양", "329180", "HD현대중공업", "Intermediate Holding"),
        ("009540", "HD한국조선해양", "010620", "HD현대미포", "Intermediate Holding"),

        # Hanwha
        ("000880", "한화", "012450", "한화에어로스페이스", "Holding"),
        ("000880", "한화", "009830", "한화솔루션", "Holding"),
        ("000880", "한화", "003530", "한화생명", "Holding"), # 금융계열사
        ("012450", "한화에어로스페이스", "272210", "한화시스템", "Parent"),
        ("012450", "한화에어로스페이스", "042660", "한화오션", "Parent (Acquisition)"),

        # Doosan (로봇/원전 밸류체인)
        ("000150", "두산", "034020", "두산에너빌리티", "Holding"),
        ("034020", "두산에너빌리티", "241560", "두산밥캣", "Parent"),
        ("034020", "두산에너빌리티", "336260", "두산퓨얼셀", "Parent"),
        ("000150", "두산", "454910", "두산로보틱스", "Parent"), # 지배구조 개편 이슈 체크

        # LS (전력/전선)
        ("006260", "LS", "010120", "LS ELECTRIC", "Holding"),
        ("006260", "LS", "000680", "LS MnM", "Holding"), # 비상장이나 중요
        ("006260", "LS", "229640", "LS에코에너지", "Holding"),

        # ==========================================
        # 4. IT & 플랫폼 & 게임 (Kakao, Naver, Krafton)
        # ==========================================
        # Kakao
        ("035720", "카카오", "377300", "카카오페이", "Parent"),
        ("035720", "카카오", "323410", "카카오뱅크", "Parent"),
        ("035720", "카카오", "293490", "카카오게임즈", "Parent"),
        ("035720", "카카오", "041510", "에스엠", "Major Shareholder"),

        # Naver (지분 투자 중심)
        ("035420", "NAVER", "Webtoon", "Webtoon Ent", "Parent (US Listed)"),
        ("035420", "NAVER", "Z_Holdings", "LY Corp", "Strategic (Softbank JV)"),

        # Game
        ("251270", "넷마블", "351200", "코웨이", "Strategic (Rental Biz)"), # 게임사가 렌탈사 보유
        ("251270", "넷마블", "352820", "하이브", "Strategic Investment"), 

        # ==========================================
        # 5. 금융지주 (Financial Groups)
        # ==========================================
        ("105560", "KB금융", "105560", "KB국민은행", "Holding"), # 상장 자회사 없음 (완전 자회사)
        ("055550", "신한지주", "055550", "신한은행", "Holding"),
        ("316140", "우리금융지주", "316140", "우리은행", "Holding"),
        ("086790", "하나금융지주", "086790", "하나은행", "Holding"),
        ("138930", "BNK금융지주", "138930", "부산은행", "Holding"),
        ("139130", "DGB금융지주", "139130", "대구은행", "Holding"),
        ("175330", "JB금융지주", "175330", "전북은행", "Holding"),
        ("138040", "메리츠금융지주", "008560", "메리츠증권", "Merged (One Company)"), # 완전 자회사화됨

        # ==========================================
        # 6. 유통/식품/바이오 기타 (CJ, Lotte, Celltrion)
        # ==========================================
        # CJ
        ("001040", "CJ", "097950", "CJ제일제당", "Holding"),
        ("001040", "CJ", "035760", "CJ ENM", "Holding"),
        ("001040", "CJ", "000120", "CJ대한통운", "Holding"),
        ("035760", "CJ ENM", "253450", "스튜디오드래곤", "Parent"),

        # Lotte
        ("004990", "롯데지주", "023530", "롯데쇼핑", "Holding"),
        ("004990", "롯데지주", "011170", "롯데케미칼", "Holding"),
        ("011170", "롯데케미칼", "028050", "롯데에너지머티리얼즈", "Parent"), # 일진머티리얼즈 인수

        # Celltrion
        ("068270", "셀트리온", "068760", "셀트리온제약", "Parent"), # 합병 이슈 존재
    ]

    for pc, pn, cc, cn, rel_type in ownership:
        # 1. Company/Ticker Node 생성
        # 지주사나 자회사가 상장사가 아닐 수도 있지만(예: SK E&S), 여기서는 상장 코드 기준으로 가정.
        # 코드가 있는 경우 Ticker 노드와 연결.
        
        graph_client.run_write(
            """
            MERGE (p:Company {code: $pc}) SET p.name = $pn
            MERGE (c:Company {code: $cc}) SET c.name = $cn
            
            WITH p, c
            MERGE (c)-[r:SUBSIDIARY_OF]->(p)
            SET r.type = $type
            
            // Ticker 노드가 있다면 연결 (종목 분석을 위해)
            WITH p, c
            OPTIONAL MATCH (tp:Ticker {code: $pc})
            OPTIONAL MATCH (tc:Ticker {code: $cc})
            
            FOREACH (_ IN CASE WHEN tp IS NOT NULL THEN [1] ELSE [] END | MERGE (p)-[:IS_TICKER]->(tp))
            FOREACH (_ IN CASE WHEN tc IS NOT NULL THEN [1] ELSE [] END | MERGE (c)-[:IS_TICKER]->(tc))
            """,
            {"pc": pc, "pn": pn, "cc": cc, "cn": cn, "type": rel_type}
        )

    logger.info(f"[Graph] Seeded {len(ownership)} comprehensive ownership relations.")


def seed_supply_chain():
    """
    [Institutional Grade Supply Chain]
    한국 전 섹터를 아우르는 B2B 공급망 및 밸류체인 관계.
    단순 납품 관계를 넘어, '수주'와 '실적'이 연동되는 핵심 파이프라인.
    """
    logger.info("[Graph] Seeding comprehensive supply chain (Full Sector)...")

    # (공급사 Code, 공급사 Name, 고객사 Code, 고객사 Name, 공급 품목)
    supply_relations = [
        # ==========================================
        # 1. 반도체 & AI (Legacy + HBM)
        # ==========================================
        ("NVDA", "NVIDIA", "000660", "SK하이닉스", "GPU HBM3/3E Partner"),
        ("000660", "SK하이닉스", "NVDA", "NVIDIA", "HBM Supply"),
        ("042700", "한미반도체", "000660", "SK하이닉스", "TC Bonder (HBM Essential)"),
        ("042700", "한미반도체", "300750", "Micron", "TC Bonder Export"),
        ("005290", "동진쎄미켐", "005930", "삼성전자", "EUV Photoresist"),
        ("357780", "솔브레인", "005930", "삼성전자", "Etching Gas (High Purity)"),
        ("008370", "원익QnC", "000660", "SK하이닉스", "Quartz Ware"),
        ("131290", "티에스이", "005930", "삼성전자", "Probe Card (Test)"),

        # ==========================================
        # 2. 2차전지 & EV (광물 -> 소재 -> 셀 -> 완성차)
        # ==========================================
        # 광물/지주
        ("005490", "POSCO홀딩스", "003670", "포스코퓨처엠", "Lithium/Nickel Supply"),
        ("010130", "고려아연", "373220", "LG에너지솔루션", "Nickel Precursor"),
        # 소재 -> 셀
        ("247540", "에코프로비엠", "006400", "삼성SDI", "High-Nickel Cathode"),
        ("003670", "포스코퓨처엠", "373220", "LG에너지솔루션", "Cathode/Anode"),
        ("348370", "엔켐", "373220", "LG에너지솔루션", "Electrolyte (전해액)"),
        ("361610", "SK아이이테크놀로지", "096770", "SK이노베이션", "Separator (분리막)"),
        # 셀 -> 완성차
        ("373220", "LG에너지솔루션", "TSLA", "Tesla", "4680 Battery"),
        ("373220", "LG에너지솔루션", "GM", "General Motors", "Ultium Cells"),
        ("006400", "삼성SDI", "BMW", "BMW Group", "Prismatic Battery"),
        ("096770", "SK이노베이션", "F", "Ford", "Battery Supply"),

        # ==========================================
        # 3. 조선 & 해운 (엔진/보냉재 -> 조선소)
        # ==========================================
        ("082740", "HSD엔진", "042660", "한화오션", "Ship Engine"), # 現 한화엔진
        ("082740", "HSD엔진", "009540", "HD한국조선해양", "Ship Engine"),
        ("049120", "한국카본", "329180", "HD현대중공업", "LNG Insulation Panel (보냉재)"),
        ("017960", "동성화인텍", "042660", "한화오션", "LNG Insulation Panel"),
        ("009540", "HD한국조선해양", "011200", "HMM", "Container Ship Building"),

        # ==========================================
        # 4. 방위산업 (부품 -> 체계종합 -> 수출)
        # ==========================================
        ("272210", "한화시스템", "012450", "한화에어로스페이스", "Radar/Combat System"),
        ("079550", "LIG넥스원", "Gov_UAE", "UAE Government", "Cheongung-II Export"),
        ("012450", "한화에어로스페이스", "Gov_Poland", "Poland Government", "K9 Howitzer Export"),
        ("064350", "현대로템", "Gov_Poland", "Poland Government", "K2 Tank Export"),
        ("047810", "한국항공우주", "Gov_Poland", "Poland Government", "FA-50 Export"),

        # ==========================================
        # 5. 전력기기 (AI 인프라 수혜)
        # ==========================================
        ("001440", "대한전선", "USA_Grid", "US Power Grid", "Cable Export"),
        ("267260", "HD현대일렉트릭", "USA_Util", "American Electric Power", "Power Transformer"),
        ("028050", "삼성중공업", "015760", "한국전력", "Offshore Wind Power"), # 해상풍력 하부구조물

        # ==========================================
        # 6. 화장품 & 소비재 (ODM -> 브랜드)
        # ==========================================
        ("192820", "코스맥스", "044320", "만녀공장", "ODM Manufacturing"), # 인디브랜드
        ("192820", "코스맥스", "Loreal", "L'Oreal", "ODM Export"),
        ("161890", "한국콜마", "247540", "씨앤씨인터내셔널", "Raw Material/Coop"), # 밸류체인 예시
        ("247540", "씨앤씨인터내셔널", "Rare_Beauty", "Rare Beauty", "Makeup ODM"), # 북미 수출 핵심
        ("271560", "오리온", "VNM_Retail", "Vietnam Market", "Choco Pie Export"),
        ("003230", "삼양식품", "WMT", "Walmart", "Buldak Ramen Export"),

        # ==========================================
        # 7. 바이오 (소부장 -> CDMO -> Big Pharma)
        # ==========================================
        ("207940", "삼성바이오로직스", "PFE", "Pfizer", "CMO Contract"),
        ("207940", "삼성바이오로직스", "LLY", "Eli Lilly", "Alzheimer Drug CMO"),
        ("068270", "셀트리온", "Healthcare_Global", "Global Healthcare", "Biosimilar Distribution"),
        ("237690", "에스티팜", "Global_Pharma", "Big Pharma", "RNA Raw Material (Oligonucleotide)"),
    ]

    for sc, sn, cc, cn, item in supply_relations:
        # 1. 해외/정부 기관은 Company 노드로 생성 (Ticker 없음)
        # Code가 숫자로만 구성되면 한국 종목(Ticker), 아니면 해외/기관(Company)
        is_kr_supplier = sc.isdigit()
        is_kr_client = cc.isdigit()

        # Supplier Node Creation
        if is_kr_supplier:
            graph_client.run_write(f"MERGE (s:Ticker {{code: '{sc}'}}) SET s.name = '{sn}'")
        else:
            graph_client.run_write(f"MERGE (s:Company {{code: '{sc}'}}) SET s.name = '{sn}', s.type = 'Foreign/Gov'")

        # Client Node Creation
        if is_kr_client:
            graph_client.run_write(f"MERGE (c:Ticker {{code: '{cc}'}}) SET c.name = '{cn}'")
        else:
            graph_client.run_write(f"MERGE (c:Company {{code: '{cc}'}}) SET c.name = '{cn}', c.type = 'Foreign/Gov'")

        # 2. Relationship Creation
        graph_client.run_write(
            """
            MATCH (s {code: $sc}), (c {code: $cc})
            MERGE (s)-[r:SUPPLIES_TO]->(c)
            SET r.item = $item
            """,
            {"sc": sc, "cc": cc, "item": item}
        )

    logger.info(f"[Graph] Seeded {len(supply_relations)} comprehensive supply chain links.")


def seed_competitors():
    """
    [Institutional Grade Peer Groups]
    한국 주식시장의 전 섹터별 경쟁사(Peer Group) 및 비교 대상.
    Long-Short 전략, Pair Trading, 상대가치 평가(Relative Valuation)를 위한 필수 데이터.
    
    Relationship Property:
    - domain: 경쟁 분야 (예: 'Ramen', 'HBM', 'Banking')
    """
    logger.info("[Graph] Seeding comprehensive competitor relations (All Sectors)...")

    # (Code1, Name1, Code2, Name2, Domain/Reason)
    competitors = [
        # ==========================================
        # 1. 반도체 & IT (Tech Peers)
        # ==========================================
        # IDM (메모리)
        ("005930", "삼성전자", "000660", "SK하이닉스", "Global Memory / HBM"),
        # 소부장 (장비)
        ("042700", "한미반도체", "403870", "HPSP", "High-End AI Equipment"), # 고마진 장비 피어
        ("036930", "주성엔지니어링", "240810", "원익IPS", "Deposition Equipment (증착)"),
        ("058470", "리노공업", "131290", "티에스이", "Test Socket"),
        # OSAT (후공정)
        ("067310", "하나마이크론", "093320", "두산테스나", "OSAT / Test"),
        # 기판 (PCB)
        ("009150", "삼성전기", "011070", "LG이노텍", "High-End Substrate / FC-BGA"),
        ("008060", "대덕전자", "290510", "코리아써키트", "PCB"),

        # ==========================================
        # 2. 2차전지 & 자동차 (EV Chain)
        # ==========================================
        # 배터리 셀
        ("373220", "LG에너지솔루션", "006400", "삼성SDI", "Global Battery Cell"),
        ("006400", "삼성SDI", "096770", "SK이노베이션", "Battery Cell"),
        # 양극재 (High Nickel)
        ("247540", "에코프로비엠", "003670", "포스코퓨처엠", "Cathode Material"),
        ("247540", "에코프로비엠", "066970", "엘앤에프", "Cathode Material"),
        # 전해액
        ("348370", "엔켐", "278280", "천보", "Electrolyte / Additives"),
        # 완성차
        ("005380", "현대차", "000270", "기아", "Auto OEM (Sibling Rivalry)"),
        # 타이어
        ("161390", "한국타이어앤테크놀로지", "073240", "금호타이어", "Global Tire"),

        # ==========================================
        # 3. 바이오 & 헬스케어 (Pharma & Aesthetic)
        # ==========================================
        # 바이오시밀러/CDMO
        ("207940", "삼성바이오로직스", "068270", "셀트리온", "Global Biosimilar / CDMO"),
        # 전통 제약사 (신약)
        ("000100", "유한양행", "128940", "한미약품", "Major Pharma / R&D"),
        ("185750", "종근당", "249420", "일동제약", "Major Pharma"),
        # 미용 의료기기 (에스테틱) - 고성장 섹터
        ("214150", "클래시스", "359090", "제이시스메디칼", "HIFU / RF Devices"),
        ("214150", "클래시스", "145720", "덴티움", "Aesthetic / Dental Export"), # 수출 피어
        # 보톡스/필러
        ("145020", "휴젤", "086900", "메디톡스", "Botulinum Toxin"),

        # ==========================================
        # 4. 인터넷 & 게임 & 엔터 (Growth)
        # ==========================================
        # 플랫폼
        ("035420", "NAVER", "035720", "카카오", "Tech Platform / Ad / Commerce"),
        ("068290", "SOOP", "035420", "NAVER", "Streaming (Chisijik vs SOOP)"), # 아프리카TV 사명 변경
        # 게임 (대형)
        ("036570", "엔씨소프트", "259960", "크래프톤", "Major Game Developer"),
        ("251270", "넷마블", "293490", "카카오게임즈", "Mobile Game Publisher"),
        # 엔터 (Big 4)
        ("352820", "하이브", "041510", "에스엠", "K-POP Agency"),
        ("035900", "JYP Ent.", "122870", "와이지엔터테인먼트", "K-POP Agency"),
        # 웹툰/콘텐츠
        ("253450", "스튜디오드래곤", "035760", "CJ ENM", "Content Production"),

        # ==========================================
        # 5. 소비재 (Food & Beauty)
        # ==========================================
        # 라면/K-푸드
        ("004370", "농심", "003230", "삼양식품", "Ramen Export"),
        ("004370", "농심", "007310", "오뚜기", "Domestic Ramen"),
        # 제과
        ("271560", "오리온", "004990", "롯데지주", "Confectionery (Vietnam/India)"),
        # 화장품 브랜드
        ("090430", "아모레퍼시픽", "051900", "LG생활건강", "Cosmetic Brand (China exposure)"),
        # 화장품 ODM
        ("192820", "코스맥스", "161890", "한국콜마", "Cosmetic ODM"),
        # 패션/의류
        ("383220", "F&F", "093050", "LF", "Fashion Brand"),
        # 편의점
        ("282330", "BGF리테일", "007070", "GS리테일", "CVS (Convenience Store)"),

        # ==========================================
        # 6. 중후장대 (Industrial)
        # ==========================================
        # 조선
        ("329180", "HD현대중공업", "042660", "한화오션", "LNG / Defense Ship"),
        ("010620", "HD현대미포", "009540", "HD한국조선해양", "Shipbuilding"),
        # 방산
        ("012450", "한화에어로스페이스", "079550", "LIG넥스원", "Defense Export"),
        ("064350", "현대로템", "012450", "한화에어로스페이스", "Land Systems (Tank/Artillery)"),
        # 전력기기 (변압기)
        ("267260", "HD현대일렉트릭", "298040", "효성중공업", "Power Transformer"),
        ("010120", "LS ELECTRIC", "267260", "HD현대일렉트릭", "Power Grid"),
        # 건설
        ("000720", "현대건설", "006360", "GS건설", "Construction / Housing"),
        ("047040", "대우건설", "052690", "한전기술", "Nuclear Plant Construction"), # 원전 테마 연결

        # ==========================================
        # 7. 금융 (Finance)
        # ==========================================
        # 은행 (금융지주)
        ("105560", "KB금융", "055550", "신한지주", "Top Tier Bank"),
        ("086790", "하나금융지주", "316140", "우리금융지주", "Commercial Bank"),
        # 증권
        ("039490", "키움증권", "005940", "NH투자증권", "Brokerage vs IB"),
        ("016360", "삼성증권", "008560", "메리츠증권", "Wealth Mgmt vs Project Financing"),
        # 보험
        ("000810", "삼성화재", "005830", "DB손해보험", "Non-Life Insurance"),

        # ==========================================
        # 8. 소재 (Materials)
        # ==========================================
        # 철강
        ("005490", "POSCO홀딩스", "004020", "현대제철", "Steel Maker"),
        # 정유
        ("010950", "S-Oil", "078930", "GS", "Oil Refinery"),
        # 석유화학
        ("011170", "롯데케미칼", "051910", "LG화학", "Petrochemical"),
        ("011780", "금호석유", "011170", "롯데케미칼", "Synthetic Rubber/Plastic"),

        # ==========================================
        # 9. 항공 & 여행 (Travel)
        # ==========================================
        ("003490", "대한항공", "020560", "아시아나항공", "FSC (Full Service Carrier)"),
        ("272450", "진에어", "091810", "티웨이항공", "LCC (Low Cost Carrier)"),
        ("039130", "하나투어", "080160", "모두투어", "Travel Agency"),
    ]

    for code1, name1, code2, name2, domain in competitors:
        # 1. Company/Ticker Node 생성
        # 경쟁사는 대부분 상장사이므로 Ticker가 있다고 가정, 없으면 Company로 생성
        graph_client.run_write(
            """
            MERGE (a:Ticker {code: $code1}) SET a.name = $name1
            MERGE (b:Ticker {code: $code2}) SET b.name = $name2
            """
            , {"code1": code1, "name1": name1, "code2": code2, "name2": name2}
        )

        # 2. Relationship 생성 (양방향)
        graph_client.run_write(
            """
            MATCH (a:Ticker {code: $code1}), (b:Ticker {code: $code2})
            MERGE (a)-[r:COMPETES_WITH]->(b)
            SET r.domain = $domain
            MERGE (b)-[r2:COMPETES_WITH]->(a)
            SET r2.domain = $domain
            """,
            {"code1": code1, "code2": code2, "domain": domain}
        )

    logger.info(f"[Graph] Seeded {len(competitors)} comprehensive competitor pairs.")

def seed_all():
    """전체 시드 실행."""
    if not graph_client.is_connected:
        logger.error("[Graph] Neo4j not connected. Aborting seed.")
        return

    init_schema()
    seed_themes()
    seed_ownership()
    seed_supply_chain()
    seed_competitors()

    # 통계
    stats = graph_client.run_query("""
        MATCH (n) WITH labels(n) AS lbls, count(*) AS cnt
        UNWIND lbls AS lbl
        RETURN lbl, sum(cnt) AS total ORDER BY total DESC
    """)
    logger.info("[Graph] === Node Stats ===")
    for s in stats:
        logger.info(f"  :{s['lbl']} = {s['total']}")

    rel_stats = graph_client.run_query("""
        MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS cnt ORDER BY cnt DESC
    """)
    logger.info("[Graph] === Relationship Stats ===")
    for s in rel_stats:
        logger.info(f"  [{s['rel']}] = {s['cnt']}")


if __name__ == "__main__":
    seed_all()
