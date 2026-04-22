"""在 knowledge 目录下的向量库构建工具。

与原脚本功能等价：使用 `DASHSCOPE_API_KEY` 创建 DashScopeEmbeddings，
为主语料目录和 `dept_agent_docs` 下每个科室文本构建并保存 FAISS 向量库。

用法（在项目根或 langchain_service 目录运行）：
  python -m langchain_service.knowledge.build_vectorstore

注意：配置文件会从 `langchain_service/.env` 读取 `DASHSCOPE_API_KEY`。
"""

import os
import logging
from core.config import settings

logger = logging.getLogger("knowledge.build_vectorstore")
logging.basicConfig(level=logging.INFO)


def _build_vectorstore_for_source(embeddings, scope_key: str, source_path: str):
    import re
    from langchain_community.document_loaders import TextLoader, DirectoryLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import FAISS

    if not source_path or not os.path.exists(source_path):
        print(f"[WARN] 源不存在: {source_path}")
        return

    try:
        if os.path.isdir(source_path):
            loader = DirectoryLoader(
                source_path,
                glob="**/*.txt",
                loader_cls=TextLoader,
                loader_kwargs={"encoding": "utf-8"},
            )
            documents = loader.load()
        else:
            loader = TextLoader(source_path, encoding="utf-8")
            documents = loader.load()

        if not documents:
            print(f"[WARN] 未加载到文档: {source_path}")
            return

        chunk_size = getattr(settings, "CHUNK_SIZE", 500)
        chunk_overlap = getattr(settings, "CHUNK_OVERLAP", 50)
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = splitter.split_documents(documents)
        if not chunks:
            print(f"[WARN] 文档分片为空: {source_path}")
            return

        vectorstore = FAISS.from_documents(chunks[:100], embeddings)
        for i in range(100, len(chunks), 100):
            vectorstore.add_documents(chunks[i:i + 100])

        # sanitize scope_key into safe ASCII folder name to avoid filesystem/encoding issues
        safe_key = re.sub(r'[^A-Za-z0-9_.-]', '_', scope_key)
        vector_db_path = os.path.join(settings.VECTOR_DB_PATH, safe_key)
        os.makedirs(vector_db_path, exist_ok=True)
        vectorstore.save_local(vector_db_path)
        print(f"[OK] scope={scope_key} 向量库已保存: {vector_db_path}")
    except Exception as e:
        logger.exception(f"构建 scope={scope_key} 向量库失败: {e}")


def main():
    print("开始构建向量库 (knowledge.build_vectorstore)...")
    api_key = settings.DASHSCOPE_API_KEY
    if not api_key:
        print("警告: 未检测到 DASHSCOPE_API_KEY，请先在 langchain_service/.env 或环境变量中设置再运行。")
        return

    try:
        from langchain_community.embeddings import DashScopeEmbeddings

        embeddings = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=api_key,
        )

        # 主语料候选目录
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_candidates = [
            os.path.join(current_dir, "main_agent_docs"),
            os.path.join(current_dir, "medical_docs"),
        ]
        for d in main_candidates:
            if os.path.isdir(d):
                print("构建主语料向量库...")
                _build_vectorstore_for_source(embeddings, "main", d)
                break

        # 构建每个科室
        docs_dir = os.path.join(current_dir, 'dept_agent_docs')
        if os.path.isdir(docs_dir):
            for fname in os.listdir(docs_dir):
                if not fname.endswith('.txt'):
                    continue
                dept = os.path.splitext(fname)[0]
                source = os.path.join(docs_dir, fname)
                print(f"构建科室向量库: {dept} ...")
                _build_vectorstore_for_source(embeddings, f"department_{dept}", source)

        print("向量库构建流程完成。")
    except Exception as e:
        logger.exception(f"构建向量库失败: {e}")


if __name__ == '__main__':
    main()
