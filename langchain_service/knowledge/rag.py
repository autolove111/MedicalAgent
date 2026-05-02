import logging
from typing import Optional, Tuple

from core.config import settings
from knowledge.rag_cache import RAGCache
from knowledge.rag_formatter import format_documents_as_answer
from knowledge.rag_graph import GraphContextRetriever
from knowledge.rag_query import build_query_context
from knowledge.rag_retriever import ScopedRetrieverRegistry
from knowledge.embedding_FAISS import create_embeddings

logger = logging.getLogger(__name__)


class RAGSystem:
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self.rag_chain = None
        self.redis_client = None
        self.graph_loader = None
        self.cache = None
        self.graph_retriever = None
        self.retriever_registry = None
        self._initialize()

    def _initialize(self):
        try:
            logger.info("=" * 40)
            logger.info("开始初始化 RAG 系统")

            api_key = settings.DASHSCOPE_API_KEY
            if not api_key or api_key == "your-dashscope-api-key":
                logger.error("DashScope API Key 未配置，RAG 将不可用")
                return

            self.embeddings = create_embeddings(api_key=api_key)
            self.cache = RAGCache()
            self.redis_client = self.cache.client
            self.graph_retriever = GraphContextRetriever()
            self.graph_loader = self.graph_retriever.graph_loader
            self.retriever_registry = ScopedRetrieverRegistry(self.embeddings)
            logger.info("RAG 组件初始化完成，主检索器将按需加载")
            logger.info("=" * 40)
        except Exception as exc:
            logger.error("RAG 系统初始化异常: %s", exc, exc_info=True)

    def retrieve(
        self,
        query: str,
        scope: str = "main",
        department: Optional[str] = None,
    ) -> Tuple[str, list]:
        context = build_query_context(query, scope=scope, department=department)
        if not context.normalized_query:
            return "", []

        if self.retriever_registry is None or self.cache is None or self.graph_retriever is None:
            logger.error("RAG 系统未就绪，跳过检索")
            return "", []

        retriever = self.retriever_registry.get_retriever(context)
        if retriever is None:
            logger.error("未找到可用 retriever | scope=%s department=%s", scope, department)
            return "", []

        if context.scope_key == "main":
            self.rag_chain = retriever
            self.vectorstore = self.retriever_registry.vectorstores.get("main")

        try:
            cached = self.cache.get(context.cache_key)
            if cached is not None:
                return cached

            docs = list(retriever.invoke(context.normalized_query))
            graph_docs = self.graph_retriever.retrieve(context.normalized_query)
            combined_docs = graph_docs + docs
            answer = format_documents_as_answer(combined_docs)
            self.cache.set(context.cache_key, answer, combined_docs)
            return answer, combined_docs
        except Exception as exc:
            logger.error("检索异常: %s", exc, exc_info=True)
            return "", []


rag_system = RAGSystem()


def retrieve_medical_knowledge(
    query: str,
    scope: str = "main",
    department: Optional[str] = None,
) -> Tuple[str, list]:
    return rag_system.retrieve(query, scope=scope, department=department)
