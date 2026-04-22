"""仅为 `dept_agent_docs` 中的科室文本构建向量库的辅助脚本。

用法：
  python -m langchain_service.knowledge.run_build_depts
"""
import os
import logging
from core.config import settings

logger = logging.getLogger("knowledge.run_build_depts")
logging.basicConfig(level=logging.INFO)


def main():
    api_key = settings.DASHSCOPE_API_KEY
    if not api_key:
        print("DASHSCOPE_API_KEY 未配置，请在 langchain_service/.env 中设置后重试。")
        return

    try:
        from langchain_community.embeddings import DashScopeEmbeddings
    except Exception as e:
        print(f"无法导入 DashScopeEmbeddings: {e}")
        return

    embeddings = DashScopeEmbeddings(model="text-embedding-v3", dashscope_api_key=api_key)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(current_dir, 'dept_agent_docs')
    if not os.path.isdir(docs_dir):
        print(f"找不到科室语料目录: {docs_dir}")
        return

    from build_vectorstore import _build_vectorstore_for_source

    for fname in os.listdir(docs_dir):
        if not fname.endswith('.txt'):
            continue
        dept = os.path.splitext(fname)[0]
        source = os.path.join(docs_dir, fname)
        print(f"构建科室向量库: {dept} ...")
        _build_vectorstore_for_source(embeddings, f"department_{dept}", source)

    print("科室向量库构建完成（dept_agent_docs）。")


if __name__ == '__main__':
    main()
