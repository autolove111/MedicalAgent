# ==============================================
# 【模块全称】医疗知识库向量数据库构建与管理模块
# 【核心定位】RAG智能问答系统底层核心支撑模块，负责医疗文本知识库的向量化全流程处理
# 【完整端到端功能流程】
# 1. 路径标准化管理：自动解析/生成/清洗主库、科室文档、向量库存储路径，兼容配置文件+自定义路径
# 2. 文档加载：批量读取本地TXT医疗文档，支持主语料库、默认医疗库、各专科科室文档分级加载
# 3. 文本预处理：全自动清洗文档（去乱码、冗余空格、空行、格式化文本，提升向量质量）
# 4. 智能分块：基于递归字符分割算法切割长文档，保证语义完整性，支持自定义分块大小/重叠度
# 5. 向量生成：对接阿里通义千问嵌入模型，将文本转换为高维向量（AI检索专用格式）
# 6. 向量库构建：基于FAISS本地向量库，批量生成向量索引，分批次处理防止内存溢出
# 7. 持久化存储：将向量库保存到本地磁盘，主库/科室库独立分类存储，便于检索区分
# 8. 本地加载复用：快速读取已构建的向量库，避免重复计算，提升效率
# 9. 批量运维能力：自动遍历所有科室文件夹，批量构建/管理独立科室向量库
# 【支持业务场景】
# - 全局主语料库向量库构建、存储、加载
# - 多科室独立向量库批量构建、隔离存储、专属检索
# - 向量库路径智能检索、容错匹配
# 【核心技术栈】LangChain文档处理、阿里通义千问向量嵌入、FAISS向量数据库
# 【工程特性】配置化驱动、日志监控、异常容错、路径安全清洗、批量高效处理
# ==============================================

# 导入日志模块：用来打印程序运行的提示/警告/错误信息
import logging
# 导入文件/文件夹操作模块：处理路径、创建文件夹、判断文件是否存在
import os
# 导入正则模块：用来处理文本、替换非法字符
import re
# 导入类型提示：标注函数的输入/输出类型，让代码更清晰
from typing import List, Optional

# 导入阿里通义千问的向量嵌入模型（LangChain封装好的）
from langchain_community.embeddings import DashScopeEmbeddings
# 导入FAISS本地向量库（LangChain封装好的，用来存向量、做检索）
from langchain_community.vectorstores import FAISS
# 导入LangChain的文档对象：装「文本内容+文件信息」的盒子
from langchain_core.documents import Document

# 导入项目的配置文件：读取API密钥、向量库路径、分块大小等配置
from core.config import settings
# 导入文档分块工具：把长文档切成小段（方便检索）
from knowledge.chunk_strategies import split_documents
# 导入文档加载工具：你自己写的 加载txt、遍历科室文件的函数
from knowledge.document_loaders import (
    iter_department_sources,
    load_text_documents,
    resolve_main_corpus_dir,
    resolve_medical_docs_dir,
)
# 导入文本清洗工具：你自己写的 清理乱码、空格、空行的函数
from knowledge.text_cleaner import clean_documents

# 创建日志记录器：用当前文件的名字做标识，打印日志时能知道是哪个模块输出的
logger = logging.getLogger(__name__)


# --------------------------
# 工具函数1：清洗「范围标识」的字符
# 作用：把非法字符替换成下划线，防止创建文件夹/路径时报错
# --------------------------
def sanitize_scope_key(scope_key: str) -> str:
    # 正则替换：所有非 字母/数字/下划线/点/横杠 的字符，都换成 _
    return re.sub(r"[^A-Za-z0-9_.-]", "_", scope_key or "")


# --------------------------
# 工具函数2：创建向量嵌入模型
# 作用：把文本变成数字向量（AI能识别的格式）
# --------------------------
def create_embeddings(api_key: Optional[str] = None, model: str = "text-embedding-v3") -> DashScopeEmbeddings:
    # 确定API密钥：优先用传入的，没有就用配置文件里的通义千问密钥
    resolved_api_key = api_key or settings.DASHSCOPE_API_KEY
    # 创建并返回阿里通义千问的嵌入模型对象
    return DashScopeEmbeddings(
        model=model,  # 使用的嵌入模型名称
        dashscope_api_key=resolved_api_key,  # 身份认证密钥
    )


# --------------------------
# 工具函数3：拼接向量库的存储路径
# 作用：生成「向量库要存在哪个文件夹」的完整路径
# --------------------------
def resolve_vectorstore_dir(scope_key: str, base_path: Optional[str] = None) -> str:
    # 确定根路径：优先用传入的，没有就用配置文件里的向量库根目录
    root = base_path or settings.VECTOR_DB_PATH
    # 拼接路径：根目录 + 清洗后的范围标识（比如 main / department_呼吸科）
    return os.path.join(root, sanitize_scope_key(scope_key))


# --------------------------
# 工具函数4：获取向量库的「候选查找路径」
# 作用：告诉程序 去哪些文件夹找已经建好的向量库
# --------------------------
def get_vectorstore_candidate_paths(
    scope: str = "main",
    department: Optional[str] = None,
    base_path: Optional[str] = None,
) -> List[str]:
    # 向量库根目录：优先传入，否则用配置文件的
    root = base_path or settings.VECTOR_DB_PATH
    # 标准化范围：转小写、去空格，统一格式
    normalized_scope = (scope or "main").strip().lower()
    # 存储候选路径的空列表
    candidates: List[str] = []

    # 如果是「科室检索」范围
    if normalized_scope == "department":
        # 去掉科室名的空格
        dept = (department or "").strip()
        # 没有科室名，直接返回空列表
        if not dept:
            return []
        # 生成2个候选路径：标准路径 + 简化路径，防止找不到
        candidates.append(resolve_vectorstore_dir(f"department_{dept}", root))
        candidates.append(os.path.join(root, f"department_{dept}"))
    # 如果是「主语料库」范围
    else:
        # 生成2个候选路径：main文件夹 + 根目录
        candidates.append(os.path.join(root, "main"))
        candidates.append(root)

    # 路径去重：避免重复的路径
    deduped: List[str] = []
    seen = set()
    # 遍历所有候选路径
    for path in candidates:
        # 标准化路径格式
        normalized = os.path.normpath(path)
        # 已经记录过的路径跳过
        if normalized in seen:
            continue
        # 没记录过的，加入集合和结果列表
        seen.add(normalized)
        deduped.append(normalized)
    # 返回去重后的候选路径列表
    return deduped


# --------------------------
# 工具函数5：从本地文件夹加载向量库
# 作用：读取已经建好的FAISS向量库，不用重复构建
# --------------------------
def load_vectorstore_from_dir(vector_db_path: str, embeddings) -> Optional[FAISS]:
    # 拼接向量库核心文件路径：index.faiss是FAISS的索引文件
    index_path = os.path.join(vector_db_path, "index.faiss")
    # 如果索引文件不存在，返回空（代表没找到向量库）
    if not os.path.exists(index_path):
        return None

    # 加载本地向量库，返回FAISS对象
    return FAISS.load_local(
        vector_db_path,  # 向量库文件夹路径
        embeddings,      # 向量嵌入模型
        allow_dangerous_deserialization=True,  # 允许加载本地文件（LangChain要求）
    )


# --------------------------
# 工具函数6：加载并清洗 指定路径的文档
# 作用：把txt文件 → 加载 → 清洗 → 返回干净的LangChain文档
# --------------------------
def load_documents_for_source(source_path: str) -> List[Document]:
    # 调用你写的函数：加载路径下的所有txt原始文档
    raw_documents = load_text_documents(source_path)
    # 调用你写的函数：清洗所有文档（去乱码、去空格、规范格式）
    return clean_documents(raw_documents)


# --------------------------
# 工具函数7：加载默认的医疗文档
# 作用：加载系统预设的医疗知识库文档
# --------------------------
def load_default_medical_documents() -> List[Document]:
    # 获取默认医疗文档的文件夹路径
    medical_dir = resolve_medical_docs_dir()
    # 如果路径不存在，返回空列表
    if not medical_dir:
        return []
    # 调用上面的函数：加载并清洗医疗文档
    return load_documents_for_source(medical_dir)


# --------------------------
# 核心函数1：从「文档列表」构建向量库
# 作用：文档 → 分块 → 批量生成向量 → 存入FAISS
# --------------------------
def build_vectorstore_from_documents(
    embeddings,
    documents: List[Document],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    batch_size: int = 100,
) -> Optional[FAISS]:
    # 如果没有文档，直接返回空
    if not documents:
        return None

    # 调用分块函数：把长文档切成小段
    chunks = split_documents(
        documents,
        strategy="recursive",  # 分块策略：递归分块
        # 分块大小：优先传入，否则用配置文件的默认值500
        chunk_size=chunk_size or getattr(settings, "CHUNK_SIZE", 500),
        # 分块重叠：优先传入，否则用配置文件的默认值50
        chunk_overlap=chunk_overlap or getattr(settings, "CHUNK_OVERLAP", 50),
    )
    # 如果分块后没有内容，返回空
    if not chunks:
        return None

    # 批量构建向量库：先加载前100块
    vectorstore = FAISS.from_documents(chunks[:batch_size], embeddings)
    # 遍历剩下的文档块，批量添加到向量库（防止内存溢出）
    for idx in range(batch_size, len(chunks), batch_size):
        vectorstore.add_documents(chunks[idx:idx + batch_size])
    # 返回构建好的向量库对象
    return vectorstore


# --------------------------
# 核心函数2：从「源文件路径」完整构建向量库
# 作用：加载文档 → 清洗 → 分块 → 建库 → 保存到本地
# --------------------------
def build_vectorstore_for_source(
    embeddings,
    scope_key: str,
    source_path: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    batch_size: int = 100,
) -> Optional[FAISS]:
    # 如果路径不存在，打印警告，返回空
    if not source_path or not os.path.exists(source_path):
        logger.warning("Source path does not exist: %s", source_path)
        return None

    # 加载并清洗路径下的所有文档
    documents = load_documents_for_source(source_path)
    # 调用核心函数1：从文档构建向量库
    vectorstore = build_vectorstore_from_documents(
        embeddings,
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
    )
    # 如果构建失败，打印警告，返回空
    if vectorstore is None:
        logger.warning("No chunks generated for source: %s", source_path)
        return None

    # 生成向量库的存储路径
    vector_db_path = resolve_vectorstore_dir(scope_key)
    # 创建文件夹（如果已存在，不报错）
    os.makedirs(vector_db_path, exist_ok=True)
    # 把向量库保存到本地
    vectorstore.save_local(vector_db_path)
    # 打印日志：保存成功
    logger.info("Saved vectorstore | scope=%s path=%s", scope_key, vector_db_path)
    # 返回构建好的向量库
    return vectorstore


# --------------------------
# 业务函数1：构建「主语料库」向量库
# 作用：专门给 main_agent_docs 构建向量库
# --------------------------
def build_main_vectorstore(embeddings) -> Optional[FAISS]:
    # 获取主语料库的文件夹路径
    main_dir = resolve_main_corpus_dir()
    # 如果路径不存在，打印警告，返回空
    if not main_dir:
        logger.warning("Main corpus directory not found")
        return None
    # 调用核心函数2：为主库构建向量库
    return build_vectorstore_for_source(embeddings, "main", main_dir)


# --------------------------
# 业务函数2：批量构建「所有科室」向量库
# 作用：遍历 dept_agent_docs 下所有科室文件，逐个建库
# --------------------------
def build_department_vectorstores(embeddings) -> List[str]:
    # 存储构建成功的科室名称
    built: List[str] = []
    # 遍历你写的函数：获取所有(科室名, 文件路径)
    for department, source_path in iter_department_sources():
        # 为当前科室构建向量库，命名规则：department_科室名
        vectorstore = build_vectorstore_for_source(
            embeddings,
            f"department_{department}",
            source_path,
        )
        # 如果构建成功，把科室名加入结果列表
        if vectorstore is not None:
            built.append(department)
    # 返回所有构建成功的科室名称
    return built