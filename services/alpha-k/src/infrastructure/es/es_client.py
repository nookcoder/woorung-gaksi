"""
Elasticsearch Client for Alpha-K
================================
Manages connection to Elasticsearch cluster and defines the 'news' index schema.
"""
import os
import logging
from typing import Dict, Any, Optional
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

class ESClient:
    _instance = None
    client: Optional[Elasticsearch] = None
    
    INDEX_NEWS = "news-v1"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ESClient, cls).__new__(cls)
            cls._instance._connect()
        return cls._instance

    def _connect(self):
        """Connect to Elasticsearch."""
        try:
            # Default to docker service name 'elasticsearch'
            es_host = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
            
            self.client = Elasticsearch(
                es_host,
                verify_certs=False,
                request_timeout=30
            )

            if self.client.ping():
                logger.info(f"[ESClient] Connected to {es_host}")
                self._ensure_indices()
            else:
                logger.error(f"[ESClient] Connection failed to {es_host}")
                
        except Exception as e:
            logger.error(f"[ESClient] Integration error: {e}")
            self.client = None

    def _ensure_indices(self):
        """Create indices with Nori analyzer if they don't exist."""
        if not self.client:
            return

        # News Index Schema
        settings = {
            "analysis": {
                "tokenizer": {
                    "nori_user_dict": {
                        "type": "nori_tokenizer",
                        "decompound_mode": "mixed",
                        # "user_dictionary": "userdict_ko.txt" 
                    }
                },
                "analyzer": {
                    "korean": {
                        "type": "custom",
                        "tokenizer": "nori_user_dict",
                        "filter": [
                            "nori_part_of_speech",
                            "lowercase", 
                            "stop",
                            "nori_readingform"
                        ]
                    }
                }
            }
        }

        mappings = {
            "properties": {
                "ticker_code": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "korean"},
                "content": {"type": "text", "analyzer": "korean"},
                "url": {"type": "keyword"},
                "published_at": {"type": "date"},
                "source": {"type": "keyword"},
                "sentiment_score": {"type": "float"}, # -1.0 to 1.0 (LLM Analysis)
                "sentiment_reason": {"type": "text", "analyzer": "korean"},
                "impact_duration": {"type": "keyword"} # Short, Mid, Long
            }
        }

        try:
            if not self.client.indices.exists(index=self.INDEX_NEWS):
                self.client.indices.create(
                    index=self.INDEX_NEWS,
                    settings=settings,
                    mappings=mappings
                )
                logger.info(f"[ESClient] Index '{self.INDEX_NEWS}' created.")
            else:
                logger.info(f"[ESClient] Index '{self.INDEX_NEWS}' exists.")
        except Exception as e:
            logger.error(f"[ESClient] Index creation failed: {e}")

    def index_document(self, index: str, doc_id: str, body: Dict[str, Any]):
        """Index a single document."""
        if not self.client:
            return
        
        try:
            resp = self.client.index(index=index, id=doc_id, document=body)
            # logger.debug(f"[ESClient] Indexed {doc_id}: {resp['result']}")
            return resp
        except Exception as e:
            logger.error(f"[ESClient] Indexing failed for {doc_id}: {e}")

    def search(self, index: str, query: Dict[str, Any], size: int = 10):
        """Search documents."""
        if not self.client:
            return []
        
        try:
            resp = self.client.search(index=index, body=query, size=size)
            return resp['hits']['hits']
        except Exception as e:
            logger.error(f"[ESClient] Search failed: {e}")
            return []

# Global Instance
es_client = ESClient()
