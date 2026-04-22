import logging
import os
import json
import hashlib
import re
from typing import Dict, List, Tuple, Optional, Set
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import redis
from sqlalchemy import create_engine

# 使用绝对路径导入
from core.config import settings
from knowledge.reference_ranges import REFERENCE_RANGES

try:
    from graph.graph_utils import GraphLoader
except Exception:
    GraphLoader = None

logger = logging.getLogger(__name__)

_INDICATOR_ALIAS = {
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

_KNOWN_INDICATORS: Set[str] = set(REFERENCE_RANGES.keys()) | {
    "HbA1c", "RDW", "CK-MB", "Troponin", "BNP", "TBIL", "DBIL", "ALP", "GGT"
}

class RAGSystem:
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self.rag_chain = None  # 实际上这里作为 retriever 使用
        self.redis_client: Optional[redis.Redis] = None
        self.graph_loader = None
        self._init_redis()
        self._init_graph_loader()
        self._initialize()
    
    def _init_redis(self):
        """初始化 Redis 连接（缓存层）"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info(f"✅ Redis 连接成功 ({settings.REDIS_HOST}:{settings.REDIS_PORT})")
        except Exception as e:
            logger.warning(f"⚠️ Redis 连接失败 ({e})，将以无缓存模式运行")
            self.redis_client = None
    
    def _initialize(self):
        try:
            logger.info("=" * 40)
            logger.info("开始初始化 RAG 系统")
            
            # 1. 初始化 Embeddings
            api_key = settings.DASHSCOPE_API_KEY
            if not api_key or api_key == "your-dashscope-api-key":
                logger.error("❌ DashScope API Key 未配置，RAG 将不可用")
                return
                
            self.embeddings = DashScopeEmbeddings(
                model="text-embedding-v3",
                dashscope_api_key=api_key
            )
            
            # 2. 初始化向量库
            self.vectorstore = self._get_or_create_vectorstore()
            
            # 3. 创建检索句柄 (Retriever)
            if self.vectorstore:
                self.rag_chain = self.vectorstore.as_retriever(
                    search_kwargs={"k": getattr(settings, "RAG_TOP_K", 3)}
                )
                logger.info("✅ RAG 系统初始化完成")
            else:
                logger.error("❌ 向量库加载失败，RAG 功能受限")
            
            logger.info("=" * 40)
        except Exception as e:
            logger.error(f"❌ RAG 系统初始化异常: {e}", exc_info=True)

    def _init_graph_loader(self):
        """初始化指标图查询组件（可选，不可用时自动降级）。"""
        if not getattr(settings, "GRAPH_RETRIEVAL_ENABLED", True):
            logger.info("Indicator graph retrieval disabled by config")
            return

        if GraphLoader is None:
            logger.warning("GraphLoader import failed, indicator graph retrieval disabled")
            return

        try:
            engine = create_engine(settings.SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
            self.graph_loader = GraphLoader(engine)
            logger.info("✅ Indicator graph retrieval initialized")
        except Exception as e:
            logger.warning(f"⚠️ Indicator graph retrieval init failed: {e}")
            self.graph_loader = None

    def _extract_indicators_from_query(self, query: str) -> List[str]:
        indicators: Set[str] = set()

        for zh_name, code in _INDICATOR_ALIAS.items():
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
            if normalized in _KNOWN_INDICATORS:
                indicators.add(normalized)

        return sorted(indicators)

    def _retrieve_indicator_graph_context(self, query: str) -> List[Document]:
        if self.graph_loader is None:
            return []

        indicators = self._extract_indicators_from_query(query)
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

                candidates.sort(key=lambda x: x[0], reverse=True)
                edge_lines.extend(line for _, line in candidates[:3])

            if not edge_lines:
                return []

            edge_lines = edge_lines[:top_edges]

            dept_mapping = self.graph_loader.load_indicator_dept_mapping()
            dept_scores: Dict[str, float] = {}
            for indicator in indicators:
                for dept, score in dept_mapping.get(indicator, []):
                    dept_scores[dept] = max(dept_scores.get(dept, 0.0), float(score))

            top_depts = sorted(dept_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            dept_text = "、".join([f"{dept}({score:.2f})" for dept, score in top_depts]) if top_depts else "无"

            graph_text = (
                "【指标图谱联查】\n"
                f"触发指标: {', '.join(indicators)}\n"
                "指标关联:\n"
                + "\n".join(f"- {line}" for line in edge_lines)
                + f"\n建议关联科室: {dept_text}"
            )

            return [
                Document(
                    page_content=graph_text,
                    metadata={
                        "source": "indicator_graph",
                        "retrieval_type": "graph",
                        "indicators": indicators,
                        "departments": [dept for dept, _ in top_depts],
                    },
                )
            ]
        except Exception as e:
            logger.warning(f"indicator_graph 联查失败，自动降级: {e}")
            return []

    def _load_medical_documents(self) -> List:
        """加载医学文本文档"""
        documents = []
        # 使用相对于 /app 的绝对路径，确保在 Docker 容器内路径一致
        doc_path = "/app/medical_docs"
        
        if not os.path.exists(doc_path):
            logger.warning(f"目录 {doc_path} 不存在，尝试寻找备用路径...")
            # 备用：尝试相对于当前文件的路径
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            doc_path = os.path.join(current_dir, "medical_docs")

        try:
            if os.path.exists(doc_path):
                files = [f for f in os.listdir(doc_path) if f.endswith('.txt')]
                logger.info(f"在 {doc_path} 发现 {len(files)} 个文本文件")
                
                loader = DirectoryLoader(
                    doc_path,
                    glob="**/*.txt",
                    loader_cls=TextLoader,
                    loader_kwargs={'encoding': 'utf-8'}
                )
                documents = loader.load()
                logger.info(f"成功加载 {len(documents)} 个文档对象")
            else:
                logger.error(f"找不到医学文档目录: {doc_path}")
        except Exception as e:
            logger.error(f"加载文档失败: {e}")
        
        return documents

    def _get_or_create_vectorstore(self):
        """加载或创建 FAISS 向量库"""
        try:
            vector_db_path = settings.VECTOR_DB_PATH
            
            # 1. 尝试加载现有索引
            if os.path.exists(os.path.join(vector_db_path, "index.faiss")):
                logger.info(f"正在从 {vector_db_path} 加载现有向量库...")
                # 【核心修复】必须添加 allow_dangerous_deserialization=True
                return FAISS.load_local(
                    vector_db_path, 
                    self.embeddings, 
                    allow_dangerous_deserialization=True
                )
            
            # 2. 创建新索引
            logger.info("未发现现有向量库，开始构建...")
            documents = self._load_medical_documents()
            if not documents:
                return None
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50
            )
            chunks = text_splitter.split_documents(documents)
            
            # 【分批处理】避免 DashScope 并发或长度限制
            vectorstore = None
            batch_size = 10 
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(batch, self.embeddings)
                else:
                    vectorstore.add_documents(batch)
            
            # 3. 保存到本地
            os.makedirs(vector_db_path, exist_ok=True)
            vectorstore.save_local(vector_db_path)
            logger.info(f"✅ 向量库已保存至: {vector_db_path}")
            return vectorstore

        except Exception as e:
            logger.error(f"向量库操作失败: {e}", exc_info=True)
            return None

    def retrieve(self, query: str) -> Tuple[str, list]:
        """执行 RAG 检索"""
        if not self.vectorstore or not self.rag_chain:
            logger.error("RAG 系统未就绪，跳过检索")
            return "", []
        
        try:
            # 1. 检查 Redis 缓存
            cache_key = f"rag_cache:{hashlib.md5(query.encode()).hexdigest()}"
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    cached_sources = data.get("sources", [])
                    cached_docs = [
                        Document(
                            page_content=item.get("page_content", ""),
                            metadata=item.get("metadata", {}),
                        )
                        for item in cached_sources
                        if isinstance(item, dict)
                    ]
                    return data.get("answer", ""), cached_docs

            # 2. 执行向量检索
            docs = self.rag_chain.invoke(query)
            graph_docs = self._retrieve_indicator_graph_context(query)
            combined_docs = graph_docs + list(docs)
            
            # 3. 格式化结果
            context_list = []
            serialized_sources = []
            for doc in combined_docs:
                source_name = doc.metadata.get('source', '未知来源')
                context_list.append(f"【来源:{source_name}】\n{doc.page_content}")
                serialized_sources.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata
                })
            
            answer = "\n\n".join(context_list)
            
            # 4. 写入缓存
            if self.redis_client:
                self.redis_client.setex(
                    cache_key, 
                    3600, 
                    json.dumps({"answer": answer, "sources": serialized_sources}, ensure_ascii=False)
                )
                
            return answer, combined_docs
        except Exception as e:
            logger.error(f"检索异常: {e}")
            return "", []

# 单例实例化
rag_system = RAGSystem()

def retrieve_medical_knowledge(query: str) -> Tuple[str, list]:
    """导出给 Agent 使用的接口"""
    return rag_system.retrieve(query)