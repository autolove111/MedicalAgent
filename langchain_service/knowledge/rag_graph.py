import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from langchain_core.documents import Document
from sqlalchemy import create_engine

from core.config import settings
from knowledge.reference_ranges import REFERENCE_RANGES

try:
    from graph.graph_utils import GraphLoader
except Exception:
    GraphLoader = None

logger = logging.getLogger(__name__)


INDICATOR_ALIAS = {
    "肌酐": "Cr",
    "尿素氮": "BUN",
    "尿酸": "UA",
    "估算肾小球滤过率": "eGFR",
    "白细胞": "WBC",
    "红细胞": "RBC",
    "血红蛋白": "HB",
    "血小板": "PLT",
    "丙氨酸氨基转移酶": "ALT",
    "天门冬氨酸氨基转移酶": "AST",
    "总胆红素": "TBIL",
    "直接胆红素": "DBIL",
    "血糖": "GLU",
    "糖化血红蛋白": "HbA1c",
    "钠": "Na",
    "钾": "K",
    "氯": "Cl",
    "钙": "Ca",
    "磷": "P",
}

KNOWN_INDICATORS: Set[str] = set(REFERENCE_RANGES.keys()) | {
    "HbA1c",
    "RDW",
    "CK-MB",
    "Troponin",
    "BNP",
    "TBIL",
    "DBIL",
    "ALP",
    "GGT",
}


class GraphContextRetriever:
    def __init__(self):
        self.graph_loader = self._init_graph_loader()

    def _init_graph_loader(self):
        if not getattr(settings, "GRAPH_RETRIEVAL_ENABLED", True):
            logger.info("Indicator graph retrieval disabled by config")
            return None

        if GraphLoader is None:
            logger.warning("GraphLoader import failed, indicator graph retrieval disabled")
            return None

        try:
            engine = create_engine(settings.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
            loader = GraphLoader(engine)
            logger.info("Indicator graph retrieval initialized")
            return loader
        except Exception as exc:
            logger.warning("Indicator graph retrieval init failed: %s", exc)
            return None

    def extract_indicators(self, query: str) -> List[str]:
        indicators: Set[str] = set()

        for zh_name, code in INDICATOR_ALIAS.items():
            if zh_name in query:
                indicators.add(code)

        for token in re.findall(r"\b[A-Za-z][A-Za-z0-9\-]{1,11}\b", query):
            normalized = token.strip().upper()
            if normalized == "HBA1C":
                indicators.add("HbA1c")
                continue
            if normalized in {"CKMB", "CK-MB"}:
                indicators.add("CK-MB")
                continue
            if normalized == "TROPONIN":
                indicators.add("Troponin")
                continue
            if normalized in KNOWN_INDICATORS:
                indicators.add(normalized)

        return sorted(indicators)

    def retrieve(self, query: str) -> List[Document]:
        if self.graph_loader is None:
            return []

        indicators = self.extract_indicators(query)
        if not indicators:
            return []

        try:
            graph = self.graph_loader.load_indicator_graph()
            if graph is None or graph.number_of_edges() == 0:
                return []

            edge_lines: List[str] = []
            top_edges = max(1, int(getattr(settings, "GRAPH_RETRIEVAL_TOP_EDGES", 8)))

            for indicator in indicators:
                if indicator not in graph:
                    continue

                candidates: List[Tuple[float, str]] = []

                for neighbor in graph.successors(indicator):
                    edge_data = graph.get_edge_data(indicator, neighbor) or {}
                    weight = float(edge_data.get("weight", 0.0) or 0.0)
                    rel_type = edge_data.get("relation_type", "UNKNOWN")
                    description = edge_data.get("description", "") or "无描述"
                    candidates.append(
                        (weight, f"{indicator} -> {neighbor} [{rel_type}] (权重:{weight:.2f}) {description}")
                    )

                for predecessor in graph.predecessors(indicator):
                    edge_data = graph.get_edge_data(predecessor, indicator) or {}
                    weight = float(edge_data.get("weight", 0.0) or 0.0)
                    rel_type = edge_data.get("relation_type", "UNKNOWN")
                    description = edge_data.get("description", "") or "无描述"
                    candidates.append(
                        (weight, f"{predecessor} -> {indicator} [{rel_type}] (权重:{weight:.2f}) {description}")
                    )

                candidates.sort(key=lambda item: item[0], reverse=True)
                edge_lines.extend(line for _, line in candidates[:3])

            if not edge_lines:
                return []

            edge_lines = edge_lines[:top_edges]
            dept_mapping = self.graph_loader.load_indicator_dept_mapping()
            dept_scores: Dict[str, float] = {}
            for indicator in indicators:
                for department, score in dept_mapping.get(indicator, []):
                    dept_scores[department] = max(dept_scores.get(department, 0.0), float(score))

            top_departments = sorted(dept_scores.items(), key=lambda item: item[1], reverse=True)[:3]
            department_text = "、".join([f"{dept}({score:.2f})" for dept, score in top_departments]) if top_departments else "无"

            graph_text = (
                "【指标图谱关联】\n"
                f"触发指标: {', '.join(indicators)}\n"
                "指标关联:\n"
                + "\n".join(f"- {line}" for line in edge_lines)
                + f"\n建议关联科室: {department_text}"
            )

            return [
                Document(
                    page_content=graph_text,
                    metadata={
                        "source": "indicator_graph",
                        "retrieval_type": "graph",
                        "indicators": indicators,
                        "departments": [dept for dept, _ in top_departments],
                    },
                )
            ]
        except Exception as exc:
            logger.warning("Indicator graph retrieval failed, fallback to vector-only: %s", exc)
            return []
