import os
from typing import List, Tuple
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document

# --------------------------
# 【核心】直接写死路径，和你的项目结构一一对应，清晰明了
# --------------------------
# 当前文件所在目录（也就是 knowledge 目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 固定的文档目录，和你项目里的文件夹完全对应
MAIN_DOCS_DIR = os.path.join(BASE_DIR, "main_agent_docs")  # 主语料库
DEPT_DOCS_DIR = os.path.join(BASE_DIR, "dept_agent_docs")    # 科室文档目录

# 只读取 .txt 文件，简化 glob 规则
TEXT_GLOB = "*.txt"


# --------------------------
# 核心工具：读取单个文件 / 文件夹（保留这个实用功能）
# --------------------------
def load_text_documents(source_path: str, encoding: str = "utf-8") -> List[Document]:
    """读取单个 txt 文件或文件夹下所有 txt 文件，返回 LangChain Document 列表"""
    if not source_path or not os.path.exists(source_path):
        return []

    if os.path.isdir(source_path):
        # 读取文件夹下所有 txt
        loader = DirectoryLoader(
            source_path,
            glob=TEXT_GLOB,
            loader_cls=TextLoader,
            loader_kwargs={"encoding": encoding},
            show_progress=False  # 可选：关闭加载进度条，更干净
        )
        return loader.load()
    else:
    # 读取单个 txt 文件
        loader = TextLoader(source_path, encoding=encoding)
        return loader.load()


# --------------------------
# 科室文档读取：直接用固定路径，去掉所有兼容逻辑
# --------------------------
def iter_department_sources() -> List[Tuple[str, str]]:
    """遍历 dept_agent_docs 下所有科室 txt 文件，返回 [(科室名, 文件路径), ...]"""
    out = []
    if not os.path.isdir(DEPT_DOCS_DIR):
        return out

    # 直接遍历，不需要多余的兼容判断
    for fname in sorted(os.listdir(DEPT_DOCS_DIR)):
        if not fname.lower().endswith(".txt"):
            continue
        dept_name = os.path.splitext(fname)[0]
        file_path = os.path.join(DEPT_DOCS_DIR, fname)
        out.append((dept_name, file_path))
    return out


# --------------------------
# 新增快捷函数，直接用，不用每次拼路径
# --------------------------
def load_main_corpus() -> List[Document]:
    """直接加载主语料库所有文档"""
    return load_text_documents(MAIN_DOCS_DIR)


def load_all_dept_docs() -> List[Document]:
    """直接加载所有科室文档"""
    all_docs = []
    for _, file_path in iter_department_sources():
        all_docs.extend(load_text_documents(file_path))
    return all_docs
