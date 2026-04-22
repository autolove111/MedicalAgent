"""Minimal medical_knowledge compatibility shim.

当前系统多处导入 `knowledge.medical_knowledge`，但仓库中缺失该模块导致导入失败。
此文件提供最小实现以避免服务启动/运行时崩溃，并可逐步替换为完整实现。

提供：
- create_knowledge_base(): 返回可被调用的知识库对象或 None
- PatientHistoryEnhancer: 包装类，提供 enhance_medical_summary(history, labs)

之后可由你替换为实际知识库构建逻辑（向量库、数据库接入等）。
"""

from typing import Any, Dict, Optional, List, Tuple
import os
import logging
import json

from core.config import settings
from knowledge.reference_ranges import get_reference_range

logger = logging.getLogger(__name__)


try:
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import DashScopeEmbeddings
    from langchain_community.document_loaders import TextLoader, DirectoryLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
except Exception:
    FAISS = None
    DashScopeEmbeddings = None
    TextLoader = None
    DirectoryLoader = None
    RecursiveCharacterTextSplitter = None
    Document = None


class KnowledgeBase:
    """医学知识库实现：加载文本语料，优先使用 DashScope+FAISS 向量检索，缺省时退回文本检索。"""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.docs: List[Dict[str, Any]] = []  # {source, path, text}
        self.vectorstore = None
        self.embeddings = None
        self._load_text_corpus()
        # 尝试构建向量索引（若 DashScope API key 可用）
        try:
            self._build_vectorstore()
        except Exception as e:
            logger.warning(f"知识库向量索引构建失败，回退为文本检索: {e}")

    def _load_text_corpus(self):
        # 加载科室文档和主语料目录
        candidates = [
            os.path.join(self.base_dir, "dept_agent_docs"),
            os.path.join(self.base_dir, "main_agent_docs"),
            os.path.join(self.base_dir, "medical_docs"),
        ]
        for d in candidates:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if not f.lower().endswith('.txt'):
                        continue
                    p = os.path.join(root, f)
                    try:
                        with open(p, 'r', encoding='utf-8') as fh:
                            text = fh.read()
                        self.docs.append({"source": os.path.relpath(p, self.base_dir), "path": p, "text": text})
                    except Exception as e:
                        logger.warning(f"读取语料失败: {p} | {e}")
        logger.info(f"KnowledgeBase: 加载文本语料 {len(self.docs)} 条")

    def _build_vectorstore(self):
        if not DashScopeEmbeddings or not FAISS:
            raise RuntimeError("缺少向量检索依赖（DashScope/FAISS）")
        api_key = getattr(settings, 'DASHSCOPE_API_KEY', None)
        if not api_key:
            raise RuntimeError("DashScope API Key 未配置")

        self.embeddings = DashScopeEmbeddings(model="text-embedding-v3", dashscope_api_key=api_key)

        # 使用 DirectoryLoader 读取文本并分块
        corpus_paths = []
        for doc in self.docs:
            corpus_paths.append(doc['path'])

        # 临时写入一个聚合目录 loader（避免复杂依赖）
        documents: List[Document] = []
        try:
            for p in corpus_paths:
                loader = TextLoader(p, encoding='utf-8')
                documents.extend(loader.load())
        except Exception as e:
            logger.warning(f"构建 vector 文档加载失败: {e}")

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(documents)
        if not chunks:
            raise RuntimeError("文档分割产生空块，无法构建向量库")

        # 分批构建 FAISS
        vectorstore = None
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            if vectorstore is None:
                vectorstore = FAISS.from_documents(batch, self.embeddings)
            else:
                vectorstore.add_documents(batch)

        self.vectorstore = vectorstore
        logger.info("KnowledgeBase: 向量索引构建完成")

    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, str]]:
        """检索知识库：返回 (source, snippet) 列表。"""
        if self.vectorstore:
            try:
                retriever = self.vectorstore.as_retriever(search_kwargs={"k": top_k})
                docs = retriever.get_relevant_documents(query)
                return [(getattr(d, 'metadata', {}).get('source', 'unknown'), d.page_content) for d in docs]
            except Exception as e:
                logger.warning(f"向量检索失败，回退到文本检索: {e}")

        # 退回：简单子串匹配，按出现次数排序
        hits: List[Tuple[str, int, str]] = []
        qlow = query.lower()
        for doc in self.docs:
            text = doc.get('text', '')
            cnt = text.lower().count(qlow)
            if cnt > 0:
                snippet = text[:1000]
                hits.append((doc.get('source', 'unknown'), cnt, snippet))
        hits.sort(key=lambda x: x[1], reverse=True)
        return [(h[0], h[2]) for h in hits[:top_k]]

    def check_abnormality(self, indicator: str, value: float, age_group: str = None, gender: str = None) -> Dict[str, Any]:
        """基于 reference_ranges 判定异常性并返回结构化信息。"""
        try:
            numeric = float(value)
        except Exception:
            return {"is_abnormal": False, "level": "unknown", "detail": "非数值"}

        ref = get_reference_range(indicator)
        if not ref:
            return {"is_abnormal": False, "level": "unknown", "detail": "无参考范围"}

        # 选择参考范围优先级：gender -> normal -> adult
        low = None
        high = None
        if gender and gender.lower().startswith('f') and isinstance(ref.get('female'), dict):
            low = ref.get('female', {}).get('min')
            high = ref.get('female', {}).get('max')
        elif gender and gender.lower().startswith('m') and isinstance(ref.get('male'), dict):
            low = ref.get('male', {}).get('min')
            high = ref.get('male', {}).get('max')
        elif isinstance(ref.get('normal'), dict):
            low = ref.get('normal', {}).get('min')
            high = ref.get('normal', {}).get('max')
        elif isinstance(ref.get('adult'), dict):
            low = ref.get('adult', {}).get('min')
            high = ref.get('adult', {}).get('max')

        is_abnormal = False
        level = 'normal'
        detail = ''

        if low is not None and numeric < low:
            is_abnormal = True
            level = 'low'
            detail = f"{indicator}={numeric} 低于参考下限 {low}"
        elif high is not None and numeric > high:
            is_abnormal = True
            # 判断危急程度
            crit_high = ref.get('critical_high')
            if crit_high is not None and numeric >= crit_high:
                level = 'critical'
            else:
                level = 'high'
            detail = f"{indicator}={numeric} 高于参考上限 {high}"

        return {"is_abnormal": is_abnormal, "level": level, "detail": detail, "value": numeric, "low": low, "high": high}

    def analyze_lab_results(self, lab_results: Dict[str, float], gender: str = None) -> Dict[str, Any]:
        """对一组检验值进行快速总结分析，返回异常包与建议要点。"""
        out = {"abnormalities": {}, "recommendations": []}
        for ind, val in (lab_results or {}).items():
            chk = self.check_abnormality(ind, val, gender=gender)
            out['abnormalities'][ind] = chk
            if chk.get('is_abnormal'):
                out['recommendations'].append(f"{ind} 异常: {chk.get('detail')}")
        return out


class PatientHistoryEnhancer:
    """基于知识库的病史增强器：用 RAG/KB 检索为病史补充相关知识片段。"""

    def __init__(self, kb: Optional[KnowledgeBase]):
        self.kb = kb

    def enhance_medical_summary(self, history_text: str, lab_results: Dict[str, float]) -> str:
        if not history_text:
            history_text = ""
        if not self.kb or not lab_results:
            return history_text

        # 取 top 3 指标作为检索触发词
        keys = list(lab_results.keys())[:3]
        query = history_text + "\n关键检验指标: " + ",".join(keys)
        hits = self.kb.search(query, top_k=3)
        if hits:
            snippets = []
            for src, snip in hits:
                snippets.append(f"【{src}】 {snip[:400]}")
            return history_text + "\n【知识库补充】\n" + "\n".join(snippets)
        return history_text


def create_knowledge_base() -> KnowledgeBase:
    """工厂函数：构建并返回 KnowledgeBase 实例。"""
    try:
        kb = KnowledgeBase()
        return kb
    except Exception as e:
        logger.warning(f"创建 KnowledgeBase 失败，返回占位 None: {e}")
        return None


__all__ = ["create_knowledge_base", "PatientHistoryEnhancer", "KnowledgeBase"]
