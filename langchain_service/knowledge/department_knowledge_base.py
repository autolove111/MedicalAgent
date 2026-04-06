"""
科室专科知识库管理系统

每个科室维护独立的向量数据库：
  - 肾内科：肾脏病、肾功能异常、电解质代谢
  - 内分泌科：糖尿病、代谢综合征、激素异常
  - 血液科：血细胞异常、贫血、凝血功能
  - 肝胆病科：肝炎、肝硬化、黄疸

特点：
  - RAG 检索：诊疗时自动查询专科知识
  - 增强诊断准确性：基于科室特定文献
  - 支持细粒度检索：症状、指标、诊疗方案
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import os

from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader

logger = logging.getLogger(__name__)

# 尝试导入 Embeddings，如果失败则使用模拟
try:
    from langchain_openai import OpenAIEmbeddings
    HAS_OPENAI_EMBEDDINGS = True
except ImportError:
    try:
        from langchain.embeddings.openai import OpenAIEmbeddings
        HAS_OPENAI_EMBEDDINGS = True
    except ImportError:
        HAS_OPENAI_EMBEDDINGS = False
        logger.warning("【Embeddings】OpenAI Embeddings 不可用，将使用内置检索")


@dataclass
class DepartmentKnowledge:
    """科室知识库对象"""
    department: str              # 科室名
    vectorstore: Optional[FAISS] # 向量库
    retriever: Optional[object]  # 检索器
    document_count: int          # 文档数量
    specialties: List[str]       # 专科领域
    last_updated: str           # 最后更新时间


class DepartmentKnowledgeBase:
    """科室知识库管理器"""
    
    def __init__(self, base_path: str = "./department_knowledge"):
        """
        初始化科室知识库
        
        Args:
            base_path: 知识库存储基路径
        """
        self.base_path = base_path
        self.knowledge_bases: Dict[str, DepartmentKnowledge] = {}
        
        # 定义各科室的知识库配置
        self.department_configs = {
            "肾内科": {
                "specialties": ["慢性肾脏病", "肾功能不全", "高血压肾病", "糖尿病肾病", "电解质代谢"],
                "key_indicators": ["Cr", "BUN", "UA", "K", "Cl", "eGFR"],
                "documents_dir": os.path.join(base_path, "nephrology")
            },
            "内分泌科": {
                "specialties": ["糖尿病", "甲状腺疾病", "代谢综合征", "肥胖症", "脂质代谢异常"],
                "key_indicators": ["GLU", "HbA1c", "TSH", "T3", "T4", "TG", "TC"],
                "documents_dir": os.path.join(base_path, "endocrinology")
            },
            "血液科": {
                "specialties": ["贫血", "血小板异常", "白细胞异常", "凝血功能障碍", "血液恶性肿瘤"],
                "key_indicators": ["WBC", "RBC", "Hb", "HCT", "PLT", "MCV"],
                "documents_dir": os.path.join(base_path, "hematology")
            },
            "肝胆病科": {
                "specialties": ["病毒性肝炎", "肝硬化", "肝功能异常", "胆道疾病", "脂肪肝"],
                "key_indicators": ["ALT", "AST", "ALP", "TB", "DB", "GGT"],
                "documents_dir": os.path.join(base_path, "hepatology")
            },
        }
        
        logger.info(f"【知识库管理器】初始化，支持 {len(self.department_configs)} 个科室")
    
    def initialize_department_knowledge(self, department: str) -> DepartmentKnowledge:
        """
        初始化单个科室的知识库
        
        Args:
            department: 科室名称
        
        Returns:
            DepartmentKnowledge 对象
        """
        if department not in self.department_configs:
            raise ValueError(f"不支持的科室: {department}")
        
        config = self.department_configs[department]
        docs_dir = config["documents_dir"]
        
        logger.info(f"【{department}知识库】初始化中...")
        
        # 直接使用内置知识库（避免文件加载错误）
        logger.info(f"  使用内置专科知识库")
        documents = self._get_builtin_knowledge(department, config)
        logger.info(f"  已加载 {len(documents)} 份内置知识")
        
        # 分割文本
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = splitter.split_documents(documents)
        logger.info(f"  文本分割后得到 {len(chunks)} 个 chunks")
        
        # 创建向量库（使用简化的模拟，实际项目中使用真实 Embedding）
        vectorstore = None
        retriever = None
        
        if HAS_OPENAI_EMBEDDINGS and os.getenv("OPENAI_API_KEY"):
            try:
                # 尝试使用 OpenAI Embeddings
                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv("OPENAI_API_KEY"),
                    openai_api_base=os.getenv("OPENAI_API_BASE")
                )
                vectorstore = FAISS.from_documents(chunks, embeddings)
                retriever = vectorstore.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": 3}  # 返回最相关的 3 份文档
                )
                logger.info(f"  ✓ FAISS 向量库创建成功")
            except Exception as e:
                logger.warning(f"  无法使用真实 Embedding: {str(e)[:100]}，将使用内置检索")
                retriever = self._create_builtin_retriever(chunks, config)
        else:
            if not HAS_OPENAI_EMBEDDINGS:
                logger.info(f"  ⚠ OpenAI Embeddings 不可用，使用内置检索")
            else:
                logger.info(f"  ⚠ 未设置 OPENAI_API_KEY，使用内置检索")
            retriever = self._create_builtin_retriever(chunks, config)
        
        kb = DepartmentKnowledge(
            department=department,
            vectorstore=vectorstore,
            retriever=retriever,
            document_count=len(documents),
            specialties=config["specialties"],
            last_updated="2026-04-01"
        )
        
        self.knowledge_bases[department] = kb
        logger.info(f"✓ {department}知识库初始化完成")
        
        return kb
    
    def _get_builtin_knowledge(self, department: str, config: Dict) -> List:
        """获取内置知识（如果文件不存在）"""
        from langchain.schema import Document
        
        builtin_content = {
            "肾内科": """
肾内科诊疗指南摘要

【慢性肾脏病（CKD）分期】
- Stage 1: eGFR ≥ 90 ml/min/1.73m²，有肾脏损害标志
- Stage 2: eGFR 60-89，有肾脏损害标志
- Stage 3a: eGFR 45-59
- Stage 3b: eGFR 30-44
- Stage 4: eGFR 15-29
- Stage 5: eGFR < 15 或接受肾替代治疗

【血肌酐异常】
正常范围：44-133 μmol/L
- 升高 > 150：提示肾小球滤过率下降，进行性肾功能损害
- 管理：控制血压、蛋白尿、血糖，避免肾毒性药物

【尿素氮（BUN）异常】
正常范围：2.5-7.1 mmol/L
- 升高 > 10：肾功能损害、肾前性氮质血症
- 与 Cr 比值 > 20：提示肾前性原因（脱水、低血容量）

【尿酸异常处理】
- 高尿酸血症：> 420 μmol/L 时考虑治疗
- 优先处理：控制饮食、充分补液、使用别嘌醇

【电解质管理】
- 高钾：> 5.5 mmol/L，需立即干预
- 低钙：< 2.1 mmol/L，与肾功能恶化相关
- 低磷：2.5-4.5 mmol/L，恢复期需补充
            """,
            
            "内分泌科": """
内分泌科诊疗指南摘要

【糖尿病诊断标准】
- 空腹血糖 ≥ 126 mg/dL (≥ 7.0 mmol/L)
- 2小时血糖 ≥ 200 mg/dL (≥ 11.1 mmol/L)
- HbA1c ≥ 6.5%
- 随机血糖 ≥ 200 mg/dL + 症状

【糖尿病并发症管理】
- 糖尿病肾病：需要同时肾内科和内分泌科管理
- 血糖控制目标：HbA1c 7-8%
- 血压控制：< 130/80 mmHg（有蛋白尿）

【代谢指标解读】
- 甘油三酯异常：> 150 mg/dL 提示代谢紊乱
- 总胆固醇异常：> 200 mg/dL 需要处理
- LDL 升高：> 100 mg/dL 是心血管风险因素

【甲状腺功能】
- TSH 升高 + T4 低：提示甲状腺功能减退
- T3、T4 升高 + TSH 低：提示甲状腺功能亢进
            """,
            
            "血液科": """
血液科诊疗指南摘要

【血象异常处理】
- WBC 升高 > 11 × 10⁹/L：感染、炎症、血液系统疾病
- WBC 降低 < 4 × 10⁹/L：骨髓抑制、免疫系统异常
- Hb 降低 < 120 g/L：贫血，需要鉴别诊断

【贫血分类】
- 小细胞贫血 (MCV < 80)：缺铁性贫血、慢性病贫血
- 正常细胞贫血 (MCV 80-100)：溶血、出血、骨髓增生异常
- 大细胞贫血 (MCV > 100)：VB12 缺乏、叶酸缺乏

【血小板异常】
- PLT 升高 > 400 × 10⁹/L：反应性血小板增多、骨髓增生性疾病
- PLT 降低 < 100 × 10⁹/L：自身免疫、DIC、TTP

【慢性肾病贫血】
- 常见于 eGFR < 45
- 原因：促红细胞生成素（EPO）分泌不足
- 治疗：补铁、ESA 制剂、改善肾功能
            """,
            
            "肝胆病科": """
肝胆病科诊疗指南摘要

【肝功能异常判断】
- ALT 升高 > 40 U/L：肝细胞损害标志
- AST 升高 > 40 U/L：肝细胞损害、肌肉损害
- ALT > AST：急性肝炎、脂肪肝
- AST > ALT：肝硬化、酒精性肝病

【黄疸分类】
- 总胆红素升高 > 17 μmol/L：
  - 直接胆红素升高：肝内或肝外胆汁淤积
  - 间接胆红素升高：溶血、肝摄取异常

【常见肝病】
- 病毒性肝炎：HBsAg、HCV 抗体检查
- 脂肪肝：丰富脂肪饮食、超重/肥胖
- 肝硬化：腹水、脾肿大、凝血功能异常

【肝脏合成功能】
- 白蛋白：肝脏合成能力标志，< 33 提示肝硬化
- 国际标准化比值(INR)：> 1.3 提示凝血功能异常
- 胆碱酯酶：低值提示肝脏合成功能严重受损
            """
        }
        
        docs = []
        content = builtin_content.get(department, "暂无知识库")
        doc = Document(
            page_content=content,
            metadata={"source": f"{department}_builtin", "specialty": config["specialties"][0]}
        )
        docs.append(doc)
        
        logger.info(f"  使用 {department} 内置知识库")
        return docs
    
    def _create_builtin_retriever(self, chunks: List, config: Dict):
        """创建内置检索器（不使用向量库）"""
        
        def retriever_func(query: str) -> List[str]:
            """简单的关键词匹配检索"""
            results = []
            query_lower = query.lower()
            
            for chunk in chunks:
                content = chunk.page_content.lower()
                # 检查查询关键词是否在文档中出现
                if any(keyword in content for keyword in query_lower.split()):
                    results.append(chunk.page_content)
                    if len(results) >= 3:
                        break
            
            if not results and chunks:
                results = [chunks[0].page_content]
            
            return results
        
        return retriever_func
    
    def _create_sample_knowledge(self, department: str, docs_dir: str, config: Dict):
        """创建示例知识库目录和文件"""
        os.makedirs(docs_dir, exist_ok=True)
        
        sample_content = {
            "肾内科": "肾脏病诊疗指南：慢性肾脏病分期、肾功能评估、电解质管理",
            "内分泌科": "糖尿病管理指南：诊断标准、血糖控制、并发症筛查",
            "血液科": "血液系统疾病诊疗：贫血分类、血小板异常、凝血功能",
            "肝胆病科": "肝病诊疗指南：肝功能异常、黄疸鉴别、肝硬化管理"
        }
        
        sample_file = os.path.join(docs_dir, f"{department}_知识库.txt")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(sample_content.get(department, ""))
        
        logger.info(f"  创建示例知识库: {sample_file}")
    
    def retrieve_from_department(
        self,
        department: str,
        query: str,
        top_k: int = 3
    ) -> List[str]:
        """
        从科室知识库检索相关文档
        
        Args:
            department: 科室名称
            query: 查询文本
            top_k: 返回的文档数量
        
        Returns:
            相关文档列表
        """
        if department not in self.knowledge_bases:
            self.initialize_department_knowledge(department)
        
        kb = self.knowledge_bases[department]
        
        if not kb.retriever:
            logger.warning(f"【{department}】检索器未初始化")
            return []
        
        try:
            # 如果是 FAISS 检索器
            if hasattr(kb.retriever, 'get_relevant_documents'):
                docs = kb.retriever.get_relevant_documents(query)
                return [doc.page_content for doc in docs[:top_k]]
            
            # 如果是自定义检索函数
            elif callable(kb.retriever):
                results = kb.retriever(query)
                return results[:top_k]
            
        except Exception as e:
            logger.error(f"【{department}】检索失败: {e}")
        
        return []
    
    def get_department_specialties(self, department: str) -> List[str]:
        """获取科室专科领域"""
        if department in self.department_configs:
            return self.department_configs[department]["specialties"]
        return []
    
    def get_department_key_indicators(self, department: str) -> List[str]:
        """获取科室关键指标"""
        if department in self.department_configs:
            return self.department_configs[department]["key_indicators"]
        return []


# 全局知识库实例
_department_kb_manager = None


def get_department_kb_manager() -> DepartmentKnowledgeBase:
    """获取全局知识库管理器"""
    global _department_kb_manager
    if _department_kb_manager is None:
        _department_kb_manager = DepartmentKnowledgeBase()
    return _department_kb_manager


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    manager = DepartmentKnowledgeBase()
    
    # 初始化所有科室知识库
    for dept in ["肾内科", "内分泌科", "血液科", "肝胆病科"]:
        print(f"\n初始化 {dept}...")
        manager.initialize_department_knowledge(dept)
    
    # 测试检索
    print("\n" + "="*60)
    print("【知识库检索测试】")
    print("="*60)
    
    queries = [
        ("肾内科", "慢性肾脏病诊疗"),
        ("内分泌科", "糖尿病管理"),
        ("血液科", "贫血分类"),
        ("肝胆病科", "肝功能异常"),
    ]
    
    for dept, query in queries:
        print(f"\n【{dept}】查询: {query}")
        results = manager.retrieve_from_department(dept, query, top_k=2)
        for i, result in enumerate(results, 1):
            print(f"  [{i}] {result[:80]}...")
