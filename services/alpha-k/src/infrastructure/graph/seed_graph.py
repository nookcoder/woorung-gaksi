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
    한국 주식시장 주요 테마 및 구성 종목 데이터.
    실제 2024-2025 시장에서 유효한 테마 분류.
    """
    logger.info("[Graph] Seeding themes...")

    themes = {
        "2차전지": {
            "description": "리튬이온 배터리, 양극재, 음극재, 전해질, 분리막 등 전기차 배터리 밸류체인",
            "category": "산업재",
            "tickers": [
                ("373220", "LG에너지솔루션"),
                ("006400", "삼성SDI"),
                ("051910", "LG화학"),
                ("247540", "에코프로비엠"),
                ("086520", "에코프로"),
                ("003670", "포스코퓨처엠"),
                ("012450", "한화에어로스페이스"),
                ("336260", "두산퓨얼셀"),
                ("298040", "효성중공업"),
                ("064350", "현대로템"),
            ],
        },
        "반도체": {
            "description": "메모리, 시스템 반도체, 파운드리, 반도체 장비, 소재",
            "category": "IT",
            "tickers": [
                ("005930", "삼성전자"),
                ("000660", "SK하이닉스"),
                ("402340", "SK스퀘어"),
                ("042700", "한미반도체"),
                ("240810", "원익IPS"),
                ("058470", "리노공업"),
                ("357780", "솔브레인"),
                ("166090", "하나머티리얼즈"),
                ("067310", "하나마이크론"),
                ("036930", "주성엔지니어링"),
            ],
        },
        "AI/인공지능": {
            "description": "AI 반도체, 서버, 데이터센터, AI 소프트웨어, 클라우드",
            "category": "IT",
            "tickers": [
                ("005930", "삼성전자"),
                ("000660", "SK하이닉스"),
                ("035420", "NAVER"),
                ("035720", "카카오"),
                ("036570", "엔씨소프트"),
                ("377300", "카카오페이"),
                ("259960", "크래프톤"),
                ("030200", "KT"),
                ("017670", "SK텔레콤"),
                ("032640", "LG유플러스"),
            ],
        },
        "바이오/헬스케어": {
            "description": "신약 개발, CDMO, 바이오시밀러, 의료기기, 디지털헬스",
            "category": "헬스케어",
            "tickers": [
                ("207940", "삼성바이오로직스"),
                ("068270", "셀트리온"),
                ("326030", "SK바이오팜"),
                ("302440", "SK바이오사이언스"),
                ("145020", "휴젤"),
                ("141080", "레고켐바이오"),
                ("950160", "코오롱티슈진"),
                ("328130", "루닛"),
                ("263750", "펄어비스"),
                ("041510", "에스엠"),
            ],
        },
        "자동차/전기차": {
            "description": "완성차, 자동차 부품, 전기차, 자율주행",
            "category": "자동차",
            "tickers": [
                ("005380", "현대차"),
                ("000270", "기아"),
                ("012330", "현대모비스"),
                ("018880", "한온시스템"),
                ("161390", "한국타이어앤테크놀로지"),
                ("298050", "효성첨단소재"),
                ("204320", "만도"),
                ("214370", "케어젠"),
                ("011210", "현대위아"),
                ("064350", "현대로템"),
            ],
        },
        "방산/우주항공": {
            "description": "국방, 방위산업, 우주항공, 드론",
            "category": "방산",
            "tickers": [
                ("012450", "한화에어로스페이스"),
                ("272210", "한화시스템"),
                ("047810", "한국항공우주"),
                ("064350", "현대로템"),
                ("298040", "효성중공업"),
                ("012750", "에스원"),
                ("003570", "SNT다이내믹스"),
                ("014970", "삼기이엔지"),
                ("033350", "루센트바이오"),
                ("079550", "LIG넥스원"),
            ],
        },
        "조선/해운": {
            "description": "조선, 해운, 해양플랜트, LNG 운반선",
            "category": "산업재",
            "tickers": [
                ("009540", "HD한국조선해양"),
                ("329180", "HD현대중공업"),
                ("042660", "한화오션"),
                ("010620", "HD현대미포"),
                ("028670", "팬오션"),
                ("011200", "HMM"),
                ("003490", "대한항공"),
                ("020560", "아시아나항공"),
                ("044450", "KSS해운"),
                ("082740", "HSD엔진"),
            ],
        },
        "금융": {
            "description": "은행, 증권, 보험, 핀테크",
            "category": "금융",
            "tickers": [
                ("105560", "KB금융"),
                ("055550", "신한지주"),
                ("086790", "하나금융지주"),
                ("316140", "우리금융지주"),
                ("024110", "기업은행"),
                ("003550", "LG"),
                ("005830", "DB손해보험"),
                ("000810", "삼성화재"),
                ("005940", "NH투자증권"),
                ("039490", "키움증권"),
            ],
        },
        "전력/에너지": {
            "description": "신재생에너지, 태양광, 풍력, 원전, ESS, 전력 인프라",
            "category": "에너지",
            "tickers": [
                ("015760", "한국전력"),
                ("034730", "SK"),
                ("267260", "HD현대일렉트릭"),
                ("298040", "효성중공업"),
                ("009830", "한화솔루션"),
                ("336260", "두산퓨얼셀"),
                ("322000", "현대에너지솔루션"),
                ("281820", "케이씨텍"),
                ("007460", "에이프로젠"),
                ("091990", "셀트리온헬스케어"),
            ],
        },
        "소비재/유통": {
            "description": "식품, 화장품, 유통, 의류, 엔터테인먼트",
            "category": "소비재",
            "tickers": [
                ("051900", "LG생활건강"),
                ("090430", "아모레퍼시픽"),
                ("004170", "신세계"),
                ("069960", "현대백화점"),
                ("023530", "롯데쇼핑"),
                ("097950", "CJ제일제당"),
                ("271560", "오리온"),
                ("005440", "현대그린푸드"),
                ("041510", "에스엠"),
                ("352820", "하이브"),
            ],
        },
    }

    for theme_name, info in themes.items():
        # 테마 노드 생성
        graph_client.run_write(
            """
            MERGE (th:Theme {name: $name})
            SET th.description = $description, th.category = $category
            """,
            {"name": theme_name, "description": info["description"], "category": info["category"]},
        )

        # 종목 노드 + 관계 생성
        for code, name in info["tickers"]:
            graph_client.run_write(
                """
                MERGE (t:Ticker {code: $code})
                SET t.name = $name
                WITH t
                MATCH (th:Theme {name: $theme})
                MERGE (t)-[:BELONGS_TO]->(th)
                """,
                {"code": code, "name": name, "theme": theme_name},
            )

    logger.info(f"[Graph] {len(themes)} themes seeded")


def seed_ownership():
    """
    주요 그룹사 지분 구조 (모회사-자회사).
    지배구조가 투자 판단에 영향을 미치는 관계망.
    """
    logger.info("[Graph] Seeding ownership...")

    ownership = [
        # 삼성그룹
        ("005930", "삼성전자", "207940", "삼성바이오로직스"),
        ("005930", "삼성전자", "006400", "삼성SDI"),
        ("005930", "삼성전자", "000810", "삼성화재"),
        # SK그룹
        ("034730", "SK", "000660", "SK하이닉스"),
        ("034730", "SK", "402340", "SK스퀘어"),
        ("034730", "SK", "326030", "SK바이오팜"),
        ("034730", "SK", "017670", "SK텔레콤"),
        ("051910", "LG화학", "373220", "LG에너지솔루션"),
        # 현대차그룹
        ("005380", "현대차", "012330", "현대모비스"),
        ("005380", "현대차", "000270", "기아"),
        ("005380", "현대차", "011210", "현대위아"),
        ("005380", "현대차", "064350", "현대로템"),
        # HD현대그룹
        ("009540", "HD한국조선해양", "329180", "HD현대중공업"),
        ("009540", "HD한국조선해양", "010620", "HD현대미포"),
        ("009540", "HD한국조선해양", "267260", "HD현대일렉트릭"),
        # LG그룹
        ("003550", "LG", "051910", "LG화학"),
        ("003550", "LG", "066570", "LG전자"),
        ("003550", "LG", "051900", "LG생활건강"),
        # 한화그룹
        ("012450", "한화에어로스페이스", "272210", "한화시스템"),
        ("009830", "한화솔루션", "322000", "현대에너지솔루션"),
        # 카카오그룹
        ("035720", "카카오", "377300", "카카오페이"),
    ]

    for parent_code, parent_name, child_code, child_name in ownership:
        graph_client.run_write(
            """
            MERGE (p:Company {code: $p_code}) SET p.name = $p_name
            MERGE (c:Company {code: $c_code}) SET c.name = $c_name
            MERGE (c)-[:SUBSIDIARY_OF]->(p)
            WITH p, c
            OPTIONAL MATCH (tp:Ticker {code: $p_code})
            OPTIONAL MATCH (tc:Ticker {code: $c_code})
            FOREACH (_ IN CASE WHEN tp IS NOT NULL THEN [1] ELSE [] END |
                MERGE (p)-[:IS_TICKER]->(tp))
            FOREACH (_ IN CASE WHEN tc IS NOT NULL THEN [1] ELSE [] END |
                MERGE (c)-[:IS_TICKER]->(tc))
            """,
            {"p_code": parent_code, "p_name": parent_name,
             "c_code": child_code, "c_name": child_name},
        )

    logger.info(f"[Graph] {len(ownership)} ownership relations seeded")


def seed_supply_chain():
    """
    주요 공급망 관계.
    A SUPPLIES_TO B = A가 B에 부품/서비스를 공급.
    """
    logger.info("[Graph] Seeding supply chain...")

    supply_chain = [
        # 반도체 장비 → 삼성/하이닉스
        ("240810", "원익IPS", "005930", "삼성전자"),
        ("036930", "주성엔지니어링", "005930", "삼성전자"),
        ("042700", "한미반도체", "000660", "SK하이닉스"),
        ("058470", "리노공업", "005930", "삼성전자"),
        ("166090", "하나머티리얼즈", "005930", "삼성전자"),
        ("166090", "하나머티리얼즈", "000660", "SK하이닉스"),
        # 반도체 소재
        ("357780", "솔브레인", "005930", "삼성전자"),
        ("357780", "솔브레인", "000660", "SK하이닉스"),
        # 2차전지 소재 → 배터리셀
        ("247540", "에코프로비엠", "373220", "LG에너지솔루션"),
        ("003670", "포스코퓨처엠", "373220", "LG에너지솔루션"),
        ("003670", "포스코퓨처엠", "006400", "삼성SDI"),
        # 자동차 부품 → 완성차
        ("012330", "현대모비스", "005380", "현대차"),
        ("012330", "현대모비스", "000270", "기아"),
        ("018880", "한온시스템", "005380", "현대차"),
        ("204320", "만도", "005380", "현대차"),
        ("204320", "만도", "000270", "기아"),
        # HBM 관련
        ("067310", "하나마이크론", "000660", "SK하이닉스"),
    ]

    for supplier_code, supplier_name, customer_code, customer_name in supply_chain:
        graph_client.run_write(
            """
            MERGE (s:Company {code: $s_code}) SET s.name = $s_name
            MERGE (c:Company {code: $c_code}) SET c.name = $c_name
            MERGE (s)-[:SUPPLIES_TO]->(c)
            """,
            {"s_code": supplier_code, "s_name": supplier_name,
             "c_code": customer_code, "c_name": customer_name},
        )

    logger.info(f"[Graph] {len(supply_chain)} supply chain relations seeded")


def seed_competitors():
    """경쟁사 관계."""
    logger.info("[Graph] Seeding competitors...")

    competitors = [
        # 배터리
        ("373220", "LG에너지솔루션", "006400", "삼성SDI"),
        # 반도체
        ("005930", "삼성전자", "000660", "SK하이닉스"),
        # 통신
        ("017670", "SK텔레콤", "030200", "KT"),
        ("017670", "SK텔레콤", "032640", "LG유플러스"),
        ("030200", "KT", "032640", "LG유플러스"),
        # 포털/IT
        ("035420", "NAVER", "035720", "카카오"),
        # 자동차
        ("005380", "현대차", "000270", "기아"),
        # 조선
        ("009540", "HD한국조선해양", "042660", "한화오션"),
        # 증권
        ("005940", "NH투자증권", "039490", "키움증권"),
        # 바이오
        ("207940", "삼성바이오로직스", "068270", "셀트리온"),
        # 화장품
        ("051900", "LG생활건강", "090430", "아모레퍼시픽"),
        # 엔터
        ("041510", "에스엠", "352820", "하이브"),
    ]

    for code1, name1, code2, name2 in competitors:
        graph_client.run_write(
            """
            MERGE (a:Company {code: $code1}) SET a.name = $name1
            MERGE (b:Company {code: $code2}) SET b.name = $name2
            MERGE (a)-[:COMPETES_WITH]->(b)
            MERGE (b)-[:COMPETES_WITH]->(a)
            """,
            {"code1": code1, "name1": name1, "code2": code2, "name2": name2},
        )

    logger.info(f"[Graph] {len(competitors)} competitor relations seeded")


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
