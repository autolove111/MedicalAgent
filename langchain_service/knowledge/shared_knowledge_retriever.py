# -*- coding: utf-8 -*-
"""
统一的医学知识检索工具

各科室都可以调用这个工具来检索相关的医学文献和诊疗指南
"""

import os
import logging
from typing import List, Optional
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

logger = logging.getLogger(__name__)

# 尝试导入向量库相关库
try:
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    HAS_VECTORSTORE = True
except ImportError:
    HAS_VECTORSTORE = False


class MedicalKnowledgeRetriever:
    """
    统一的医学知识检索工具
    
    加载 medical_docs 目录中的所有文档，提供基于关键词和向量的检索功能
    各科室可以通过调用 retrieve() 方法获取相关文献
    """
    
    def __init__(self, docs_dir: str = "./medical_docs"):
        """
        初始化检索工具
        
        Args:
            docs_dir: 医学文档所在目录
        """
        self.docs_dir = docs_dir
        self.documents: List[Document] = []
        self.chunks: List = []
        self.vectorstore = None
        self.retriever = None
        
        # 初始化
        self._load_documents()
        self._split_chunks()
        self._create_retriever()
    
    def _load_documents(self):
        """从 medical_docs 目录加载所有文档"""
        if not os.path.exists(self.docs_dir):
            logger.warning(f"医学文档目录不存在: {self.docs_dir}")
            return
        
        try:
            # 直接使用 Python 文件系统读取，避免编码问题
            docs_path = Path(self.docs_dir)
            txt_files = list(docs_path.glob("**/*.txt"))
            
            logger.info(f"找到 {len(txt_files)} 个 .txt 文件")
            
            self.documents = []
            for txt_file in txt_files:
                try:
                    with open(txt_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    doc = Document(
                        page_content=content,
                        metadata={"source": str(txt_file)}
                    )
                    self.documents.append(doc)
                    logger.info(f"  ✓ 加载: {txt_file.name}")
                except Exception as e:
                    logger.warning(f"  ✗ 无法加载 {txt_file.name}: {str(e)[:50]}")
                    continue
            
            logger.info(f"✓ 成功加载 {len(self.documents)} 份医学文档")
        
        except Exception as e:
            logger.error(f"加载文档失败: {e}")
            self.documents = []
    
    def _split_chunks(self):
        """将文档分割成 chunks"""
        if not self.documents:
            logger.warning("没有文档可分割")
            return
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", "。", "，", " ", ""]
        )
        
        self.chunks = splitter.split_documents(self.documents)
        logger.info(f"✓ 文本分割完成: {len(self.chunks)} 个 chunks")
    
    def _create_retriever(self):
        """创建检索工具（向量库或关键词匹配）"""
        if not self.chunks:
            logger.warning("没有可用的 chunks")
            return
        
        # 尝试使用 FAISS 向量库
        if HAS_VECTORSTORE and os.getenv("OPENAI_API_KEY"):
            try:
                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv("OPENAI_API_KEY")
                )
                self.vectorstore = FAISS.from_documents(self.chunks, embeddings)
                logger.info(f"✓ FAISS 向量库创建成功")
                self.retriever = "vectorstore"
                return
            except Exception as e:
                logger.warning(f"FAISS 创建失败: {str(e)[:100]}，使用关键词匹配")
        
        # 使用关键词匹配作为回退方案
        self.retriever = "keyword"
        logger.info(f"✓ 使用关键词匹配检索器")
    
    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        检索相关文献
        
        Args:
            query: 查询文本
            top_k: 返回最相关的 k 份文献
        
        Returns:
            相关文献列表
        """
        if not self.chunks:
            logger.warning("检索器中没有文档")
            return []
        
        if self.retriever == "vectorstore" and self.vectorstore:
            # 使用向量库检索
            try:
                docs = self.vectorstore.similarity_search(query, k=top_k)
                results = [doc.page_content for doc in docs]
                return results
            except Exception as e:
                logger.warning(f"向量检索失败: {e}，降级到关键词匹配")
                return self._keyword_retrieve(query, top_k)
        else:
            # 使用关键词匹配检索
            return self._keyword_retrieve(query, top_k)
    
    def _keyword_retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """基于关键词的检索（回退方案）"""
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # 计算每个 chunk 与查询的匹配度
        scored_chunks = []
        for chunk in self.chunks:
            content = chunk.page_content.lower()
            # 计算匹配关键词数量
            match_count = sum(1 for word in query_words if word in content)
            if match_count > 0:
                scored_chunks.append((chunk.page_content, match_count))
        
        # 按匹配度排序，返回 top_k
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        results = [chunk[0] for chunk in scored_chunks[:top_k]]
        
        # 如果没有匹配，返回前 top_k 个 chunks
        if not results:
            results = [chunk.page_content for chunk in self.chunks[:top_k]]
        
        return results
    
    def retrieve_by_department(self, department: str, query: str, top_k: int = 2) -> List[str]:
        """
        按科室检索（提供更定制化的检索）
        
        Args:
            department: 科室名称
            query: 查询文本
            top_k: 返回文献数
        
        Returns:
            相关文献
        """
        # 为不同科室添加专科关键词
        department_keywords = {
            "肾内科": ["肾", "肌酐", "清除率", "KDIGO", "肾脏", "BUN"],
            "内分泌科": ["血糖", "代谢", "甲状腺", "代谢", "TSH"],
            "血液科": ["血细胞", "CBC", "WBC", "RBC", "血红蛋白", "贫血"],
            "肝胆病科": ["肝", "胆", "丙转氨酶", "ALT", "AST", "胆管"],
        }
        
        # 在查询中加入科室专科关键词
        keywords = department_keywords.get(department, [])
        enhanced_query = query + " " + " ".join(keywords)
        
        return self.retrieve(enhanced_query, top_k)


# 全局检索器实例
_retriever_instance: Optional[MedicalKnowledgeRetriever] = None


def get_medical_retriever() -> MedicalKnowledgeRetriever:
    """获取全局检索器实例"""
    global _retriever_instance
    
    if _retriever_instance is None:
        _retriever_instance = MedicalKnowledgeRetriever()
    
    return _retriever_instance


# 导出接口
def retrieve_knowledge(query: str, top_k: int = 3) -> List[str]:
    """
    检索医学知识（所有科室都可以调用这个函数）
    
    Args:
        query: 查询文本
        top_k: 返回文献数
    
    Returns:
        相关文献列表
    """
    retriever = get_medical_retriever()
    return retriever.retrieve(query, top_k)


def retrieve_by_department(department: str, query: str, top_k: int = 2) -> List[str]:
    """
    按科室检索医学知识
    
    Args:
        department: 科室名称
        query: 查询文本
        top_k: 返回文献数
    
    Returns:
        相关文献列表
    """
    retriever = get_medical_retriever()
    return retriever.retrieve_by_department(department, query, top_k)


if __name__ == "__main__":
    """测试共享检索工具"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    print("\n" + "="*70)
    print("【医学知识统一检索工具】")
    print("="*70)
    
    retriever = get_medical_retriever()
    
    print("\n【测试 1】通用检索")
    results = retrieve_knowledge("肾功能异常 Cr 升高", top_k=2)
    for i, result in enumerate(results, 1):
        print(f"\n结果 {i}:\n{result[:200]}...")
    
    print("\n" + "="*70)
    print("【测试 2】按科室检索")
    print("="*70)
    
    test_queries = [
        ("肾内科", "Cr 升高异常处理"),
        ("血液科", "血红蛋白贫血分类"),
        ("内分泌科", "血糖代谢"),
    ]
    
    for dept, query in test_queries:
        print(f"\n【{dept}】查询：'{query}'")
        results = retrieve_by_department(dept, query, top_k=1)
        if results:
            print(f"结果：{results[0][:150]}...")
