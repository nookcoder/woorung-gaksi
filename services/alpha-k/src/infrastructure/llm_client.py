"""
Alpha-K LLM Client
===================
다양한 LLM Provider (OpenAI, DeepSeek, Anthropic)를 통합 관리하는 래퍼.
config/llm_config.yaml 설정을 로드하여 에이전트별 맞춤형 클라이언트를 제공한다.

지원:
- OpenAI / DeepSeek (OpenAI Compatible)
- Anthropic (Claude)
- 에이전트별 다른 모델/파라미터 설정 지원
"""
import os
import yaml
import logging
from typing import Optional, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

class LLMClient:
    _instance = None
    _llm_instances: Dict[str, BaseChatModel] = {}
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMClient, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """config/llm_config.yaml 로드"""
        try:
            # 다양한 경로 시도 (root, src/.., current dir)
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "llm_config.yaml"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "llm_config.yaml"),
                "config/llm_config.yaml",
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        self._config = yaml.safe_load(f)
                    logger.info(f"[LLMClient] Loaded config from {path}")
                    return

            logger.warning("[LLMClient] Config file not found. Using empty config.")
            self._config = {}
            
        except Exception as e:
            logger.error(f"[LLMClient] Config load failed: {e}")
            self._config = {}

    def get_agent_llm(self, agent_name: str) -> Optional[BaseChatModel]:
        """
        특정 에이전트용 LLM 인스턴스를 반환한다.
        이미 생성된 인스턴스가 있다면 재사용하고, 없다면 새로 생성한다.
        설정 우선순위: agents.{name} > defaults > hardcoded fallback
        """
        if agent_name in self._llm_instances:
            return self._llm_instances[agent_name]

        # 설정 병합 (Default + Agent Specific)
        defaults = self._config.get("defaults", {})
        agent_cfg = self._config.get("agents", {}).get(agent_name, {})
        
        # 병합된 최종 설정
        final_cfg = defaults.copy()
        final_cfg.update(agent_cfg)
        
        # LLM 사용 안 함 설정이면 None 반환
        if not final_cfg.get("use_llm", True):
             return None

        # 인스턴스 생성
        llm = self._create_llm_instance(final_cfg)
        if llm:
            self._llm_instances[agent_name] = llm
            logger.info(f"[LLMClient] Initialized LLM for agent '{agent_name}': {final_cfg.get('model_name')}")
        
        return llm

    def _create_llm_instance(self, cfg: Dict[str, Any]) -> Optional[BaseChatModel]:
        """설정 딕셔너리를 기반으로 LangChain 모델 인스턴스 생성"""
        provider = cfg.get("provider", "openai").lower()
        model_name = cfg.get("model_name", "gpt-4o")
        temp = cfg.get("temperature", 0.1)
        api_key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
        base_url = cfg.get("base_url")

        api_key = os.getenv(api_key_env)
        if not api_key:
            # 환경변수가 없을 경우 로그만 남기고 None 반환 (혹은 에러 발생)
            if provider != "ollama": # Ollama는 키 불필요
                logger.warning(f"[LLMClient] Missing API Key env var: {api_key_env}")
                return None

        try:
            if provider in ["deepseek", "openai"]:
                return ChatOpenAI(
                    model=model_name,
                    temperature=temp,
                    api_key=api_key,
                    base_url=base_url if provider == "deepseek" else None,
                )
            elif provider == "anthropic":
                return ChatAnthropic(
                    model=model_name,
                    temperature=temp,
                    api_key=api_key,
                )
            else:
                logger.error(f"[LLMClient] Unsupported provider: {provider}")
                return None
        except Exception as e:
            logger.error(f"[LLMClient] Failed to create LLM instance: {e}")
            return None

# Global Instance
llm_client = LLMClient()
