import logging
from typing import Optional

from core.config import settings
from knowledge.rag_query import QueryContext
from knowledge.vectorstore_builder import (
    build_main_vectorstore,
    get_vectorstore_candidate_paths,
    load_vectorstore_from_dir,
)

logger = logging.getLogger(__name__)


class ScopedRetrieverRegistry:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.vectorstores = {}
        self.retrievers = {}

    def _build_retriever(self, vectorstore):
        return vectorstore.as_retriever(
            search_kwargs={"k": getattr(settings, "RAG_TOP_K", 3)}
        )

    def get_vectorstore(self, context: QueryContext):
        cached = self.vectorstores.get(context.scope_key)
        if cached is not None:
            return cached

        vectorstore = self._load_or_build_vectorstore(context)
        if vectorstore is not None:
            self.vectorstores[context.scope_key] = vectorstore
        return vectorstore

    def get_retriever(self, context: QueryContext):
        cached = self.retrievers.get(context.scope_key)
        if cached is not None:
            return cached

        vectorstore = self.get_vectorstore(context)
        if vectorstore is None:
            return None

        retriever = self._build_retriever(vectorstore)
        self.retrievers[context.scope_key] = retriever
        return retriever

    def _load_or_build_vectorstore(self, context: QueryContext):
        for vector_db_path in get_vectorstore_candidate_paths(
            scope=context.normalized_scope,
            department=context.department,
        ):
            loaded = load_vectorstore_from_dir(vector_db_path, self.embeddings)
            if loaded is not None:
                logger.info("Loaded vectorstore from %s", vector_db_path)
                return loaded

        if context.normalized_scope != "main":
            logger.warning(
                "No vectorstore found for scope=%s department=%s",
                context.scope,
                context.department,
            )
            return None

        logger.info("Main vectorstore missing, building from source documents")
        return build_main_vectorstore(self.embeddings)
