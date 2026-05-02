import hashlib
from dataclasses import dataclass
from typing import Optional

from knowledge.vectorstore_builder import sanitize_scope_key


def normalize_query_text(query: str) -> str:
    return (query or "").strip()


def normalize_scope(scope: str) -> str:
    normalized = (scope or "main").strip().lower()
    return normalized or "main"


def resolve_scope_key(scope: str = "main", department: Optional[str] = None) -> str:
    normalized_scope = normalize_scope(scope)
    if normalized_scope == "department":
        dept = (department or "").strip()
        if not dept:
            return "department"
        return sanitize_scope_key(f"department_{dept}")
    return "main"


def build_cache_key(query: str, scope: str = "main", department: Optional[str] = None) -> str:
    identity = f"{normalize_scope(scope)}:{(department or '').strip()}:{normalize_query_text(query)}"
    return f"rag_cache:{hashlib.md5(identity.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class QueryContext:
    query: str
    scope: str = "main"
    department: Optional[str] = None

    @property
    def normalized_query(self) -> str:
        return normalize_query_text(self.query)

    @property
    def normalized_scope(self) -> str:
        return normalize_scope(self.scope)

    @property
    def scope_key(self) -> str:
        return resolve_scope_key(self.scope, self.department)

    @property
    def cache_key(self) -> str:
        return build_cache_key(self.query, self.scope, self.department)


def build_query_context(query: str, scope: str = "main", department: Optional[str] = None) -> QueryContext:
    return QueryContext(query=normalize_query_text(query), scope=scope, department=department)
