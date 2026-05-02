"""
1、知识模块的离线向量库构建入口
2、提供了一个向量库构建的主函数，负责调用相关的构建函数来生成主语料和科室的向量库。
3、包含一个向量库构建的辅助函数，保持与现有脚本和导入的兼容性。
"""




import logging

from core.config import settings
from knowledge.embedding_FAISS import (
    build_department_vectorstores,
    build_main_vectorstore,
    build_vectorstore_for_source,
    create_embeddings,
)


logger = logging.getLogger("knowledge.build_vectorstore")
logging.basicConfig(level=logging.INFO)

def main():
    print("开始构建向量库 :")
    api_key = settings.DASHSCOPE_API_KEY
    if not api_key:
        print("警告: 未检测到 DASHSCOPE_API_KEY，请先在 langchain_service/.env 或环境变量中设置后再运行。")
        return

    try:
        embeddings = create_embeddings(api_key=api_key)

        print("构建主语料向量库...")
        build_main_vectorstore(embeddings)

        print("构建科室向量库...")
        built_departments = build_department_vectorstores(embeddings)
        print(f"已完成科室向量库构建: {', '.join(built_departments) if built_departments else '无'}")
        print("向量库构建流程完成。")
    except Exception as exc:
        logger.exception("构建向量库失败: %s", exc)


if __name__ == "__main__":
    main()
