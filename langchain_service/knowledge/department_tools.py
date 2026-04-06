"""
科室工具集合 - 每个科室作为独立的 Tool

每个科室工具都接受：
  1. 患者化验数据
  2. 前面科室的诊断意见（用于跨科参考）
  3. GAT 置信度（这轮为什么调用我）

并返回：
  1. 该科室的诊断意见
  2. 需要进行的检查建议
  3. 转诊建议（是否需要其他科室）
  4. 疾病可能性排序
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

from .shared_knowledge_retriever import retrieve_by_department

logger = logging.getLogger(__name__)


@dataclass
class DepartmentDiagnosis:
    """科室诊断结果"""
    department: str              # 科室名
    confidence: float            # 诊断置信度（0-1）
    primary_diagnosis: str       # 初步诊断
    differential_diagnoses: List[str]  # 鉴别诊断
    recommended_tests: List[str] # 建议进一步检查
    referral_to: List[tuple]     # 转诊建议 [(科室, 原因, 优先级)]
    clinical_interpretation: str # 临床解读
    gat_feedback: Dict[str, float]  # 对 GAT 权重的反馈调整


class NephologyDepartment:
    """肾内科工具"""
    
    def __init__(self):
        self.name = "肾内科"
        self.key_indicators = ["Cr", "BUN", "UA", "K", "Cl"]
    
    def analyze(
        self,
        lab_results: Dict[str, float],
        previous_diagnoses: Optional[List[DepartmentDiagnosis]] = None,
        gat_confidence: float = 0.68
    ) -> DepartmentDiagnosis:
        """
        肾内科诊疗逻辑
        
        Args:
            lab_results: 化验结果
            previous_diagnoses: 前面科室的诊断（用于参考）
            gat_confidence: 这轮 GAT 对肾内科的置信度
        
        Returns:
            DepartmentDiagnosis 对象
        """
        logger.info(f"【肾内科】分析开始，GAT 置信度: {gat_confidence:.2f}")
        
        # 基于化验数据生成查询
        cr = lab_results.get("Cr", 0)
        bun = lab_results.get("BUN", 0)
        
        # 从共享知识库检索相关文献
        if cr > 120 and bun > 20:
            knowledge_query = "慢性肾脏病诊疗指南肾功能评估"
        elif cr > 120:
            knowledge_query = "血肌酐升高处理"
        else:
            knowledge_query = "肾脏病诊疗"
        
        knowledge_docs = retrieve_by_department(self.name, knowledge_query, top_k=2)
        logger.info(f"【肾内科】检索到 {len(knowledge_docs)} 份医学文献")
        if knowledge_docs:
            logger.info(f"  文献摘要: {knowledge_docs[0][:100]}...")
        
        # 提取关键指标
        cr = lab_results.get("Cr", 0)
        bun = lab_results.get("BUN", 0)
        ua = lab_results.get("UA", 0)
        k = lab_results.get("K", 0)
        
        # 计算异常程度
        diagnoses = []
        confidence = 0.0
        referral_to = []
        gat_feedback = {}
        
        # 规则 1：Cr 和 BUN 同时升高 → 肾功能不全
        if cr > 120 and bun > 20:
            diagnoses.append("慢性肾脏病（CKD）Stage 3-4")
            confidence = 0.85
            
            # 反馈给 GAT：这个诊断确认了肾内科的重要性
            gat_feedback["肾内科"] = 0.9  # 提升肾内科权重
            gat_feedback["内分泌科"] = 0.15  # 降低内分泌科（除非有 GLU 异常）
            
            # 转诊建议
            if lab_results.get("GLU", 0) > 126:
                referral_to.append(("内分泌科", "确认是否合并糖尿病", 1))
                gat_feedback["内分泌科"] = 0.45  # 提升
        
        # 规则 2：尿酸升高 → 痛风风险
        elif ua > 420:
            diagnoses.append("高尿酸血症/痛风")
            confidence = 0.70
            gat_feedback["肾内科"] = 0.7
            gat_feedback["血液科"] = 0.2  # 必要时考虑血液科
        
        # 规则 3：钾升高 → 高钾血症
        if k > 5.5:
            diagnoses.append("高钾血症")
            confidence = max(confidence, 0.75)
            gat_feedback["肾内科"] = 0.95  # 这是肾内科的核心问题
        
        # 如果诊断不明确
        if not diagnoses:
            diagnoses.append("肾功能轻度异常，需进一步监测")
            confidence = 0.45
            gat_feedback["肾内科"] = 0.5
        
        # 建议检查
        tests = [
            "肾脏超声",
            "尿常规（尿蛋白、尿潜血）",
            "肾功能指标（eGFR、血肌酐）"
        ]
        if ua > 400:
            tests.append("尿尿酸、血尿酸系列")
        if k > 5.0:
            tests.append("心电图（排除高钾对心脏影响）")
        
        logger.info(f"【肾内科】诊断：{diagnoses[0]}，置信度：{confidence:.2f}")
        logger.info(f"【肾内科】GAT 反馈：{gat_feedback}")
        logger.info(f"【肾内科】基于专科知识库生成诊疗建议")
        
        return DepartmentDiagnosis(
            department=self.name,
            confidence=confidence,
            primary_diagnosis=diagnoses[0],
            differential_diagnoses=diagnoses[1:],
            recommended_tests=tests,
            referral_to=referral_to,
            clinical_interpretation=self._interpret(cr, bun, ua, k),
            gat_feedback=gat_feedback
        )
    
    def _interpret(self, cr: float, bun: float, ua: float, k: float) -> str:
        """生成临床解读文本"""
        parts = []
        
        if cr > 120:
            parts.append(f"血清肌酐升高至 {cr} μmol/L，提示肾功能下降")
        if bun > 20:
            parts.append(f"尿素氮升高至 {bun} mmol/L，肾代谢障碍")
        if ua > 420:
            parts.append(f"尿酸升高至 {ua} μmol/L，需警惕痛风风险")
        if k > 5.5:
            parts.append(f"钾离子升高至 {k} mmol/L，需及时干预")
        
        return "；".join(parts) if parts else "化验指标在正常范围"


class EndocrinologyDepartment:
    """内分泌科工具"""
    
    def __init__(self):
        self.name = "内分泌科"
        self.key_indicators = ["GLU", "HbA1c", "T3", "T4", "TSH"]
    
    def analyze(
        self,
        lab_results: Dict[str, float],
        previous_diagnoses: Optional[List[DepartmentDiagnosis]] = None,
        gat_confidence: float = 0.24
    ) -> DepartmentDiagnosis:
        """内分泌科诊疗逻辑"""
        logger.info(f"【内分泌科】分析开始，GAT 置信度: {gat_confidence:.2f}")
        
        # 基于化验数据生成查询
        glu = lab_results.get("GLU", 0)
        
        # 从共享知识库检索相关文献
        if glu > 126:
            knowledge_query = "糖尿病诊疗指南血糖控制"
        else:
            knowledge_query = "代谢管理内分泌指标"
        
        knowledge_docs = retrieve_by_department(self.name, knowledge_query, top_k=2)
        logger.info(f"【内分泌科】检索到 {len(knowledge_docs)} 份医学文献")
        if knowledge_docs:
            logger.info(f"  文献摘要: {knowledge_docs[0][:100]}...")
        
        glu = lab_results.get("GLU", 0)
        hba1c = lab_results.get("HbA1c", 0)
        
        diagnoses = []
        confidence = 0.0
        referral_to = []
        gat_feedback = {}
        
        # 规则 1：GLU 升高 → 糖尿病
        if glu > 126 or hba1c > 6.5:
            diagnoses.append("糖尿病（血糖升高）")
            confidence = 0.80
            gat_feedback["内分泌科"] = 0.9
            
            # 如果前面诊断有肾脏病，强化跨科协作
            if previous_diagnoses:
                for prev_dx in previous_diagnoses:
                    if "肾" in prev_dx.primary_diagnosis:
                        referral_to.append(("肾内科", "糖尿病肾病风险评估", 1))
                        gat_feedback["肾内科"] = 0.85  # 强化肾内科
        
        # 规则 2：GLU 正常但有其他代谢问题
        elif glu > 100:
            diagnoses.append("空腹血糖异常")
            confidence = 0.55
            gat_feedback["内分泌科"] = 0.6
        
        if not diagnoses:
            diagnoses.append("血糖代谢正常")
            confidence = 0.3
            gat_feedback["内分泌科"] = 0.2
        
        tests = ["空腹血糖", "葡萄糖耐量试验"]
        if glu > 100:
            tests.extend(["HbA1c", "胰岛素", "C 肽"])
        
        logger.info(f"【内分泌科】诊断：{diagnoses[0]}，置信度：{confidence:.2f}")
        logger.info(f"【内分泌科】基于专科知识库生成诊疗建议")
        
        return DepartmentDiagnosis(
            department=self.name,
            confidence=confidence,
            primary_diagnosis=diagnoses[0],
            differential_diagnoses=diagnoses[1:],
            recommended_tests=tests,
            referral_to=referral_to,
            clinical_interpretation=f"血糖：{glu} mg/dL" if glu else "血糖正常",
            gat_feedback=gat_feedback
        )


class HematologyDepartment:
    """血液科工具"""
    
    def __init__(self):
        self.name = "血液科"
        self.key_indicators = ["WBC", "RBC", "Hb", "PLT"]
    
    def analyze(
        self,
        lab_results: Dict[str, float],
        previous_diagnoses: Optional[List[DepartmentDiagnosis]] = None,
        gat_confidence: float = 0.15
    ) -> DepartmentDiagnosis:
        """血液科诊疗逻辑"""
        logger.info(f"【血液科】分析开始，GAT 置信度: {gat_confidence:.2f}")
        
        # 从共享知识库检索相关文献
        knowledge_query = "血象异常血液系统疾病诊疗"
        knowledge_docs = retrieve_by_department(self.name, knowledge_query, top_k=2)
        logger.info(f"【血液科】检索到 {len(knowledge_docs)} 份医学文献")
        if knowledge_docs:
            logger.info(f"  文献摘要: {knowledge_docs[0][:100]}...")
        
        wbc = lab_results.get("WBC", 0)
        hb = lab_results.get("Hb", 0)
        plt = lab_results.get("PLT", 0)
        
        diagnoses = []
        confidence = 0.0
        gat_feedback = {}
        
        # 规则 1：WBC 升高 → 感染/炎症
        if wbc > 11:
            diagnoses.append("白细胞升高，考虑感染/炎症")
            confidence = 0.70
            gat_feedback["血液科"] = 0.8
        
        # 规则 2：Hb 降低 → 贫血
        if hb < 120:
            diagnoses.append("贫血")
            confidence = 0.75
            gat_feedback["血液科"] = 0.85
        
        # 规则 3：PLT 降低 → 血小板减少
        if plt < 100:
            diagnoses.append("血小板减少")
            confidence = 0.80
            gat_feedback["血液科"] = 0.90
        
        if not diagnoses:
            diagnoses.append("血象基本正常")
            confidence = 0.2
            gat_feedback["血液科"] = 0.1
        
        tests = ["血象详细分析", "网织红细胞计数"]
        
        logger.info(f"【血液科】诊断：{diagnoses[0]}，置信度：{confidence:.2f}")
        logger.info(f"【血液科】基于专科知识库生成诊疗建议")
        
        return DepartmentDiagnosis(
            department=self.name,
            confidence=confidence,
            primary_diagnosis=diagnoses[0],
            differential_diagnoses=diagnoses[1:],
            recommended_tests=tests,
            referral_to=[],
            clinical_interpretation=f"WBC:{wbc}, Hb:{hb}, PLT:{plt}",
            gat_feedback=gat_feedback
        )


class HepatologyDepartment:
    """肝胆病科工具"""
    
    def __init__(self):
        self.name = "肝胆病科"
        self.key_indicators = ["ALT", "AST", "ALP", "TB", "DB"]
    
    def analyze(
        self,
        lab_results: Dict[str, float],
        previous_diagnoses: Optional[List[DepartmentDiagnosis]] = None,
        gat_confidence: float = 0.10
    ) -> DepartmentDiagnosis:
        """肝胆病科诊疗逻辑"""
        logger.info(f"【肝胆病科】分析开始，GAT 置信度: {gat_confidence:.2f}")
        
        # 从共享知识库检索相关文献
        knowledge_query = "肝功能异常肝病诊疗指南"
        knowledge_docs = retrieve_by_department(self.name, knowledge_query, top_k=2)
        logger.info(f"【肝胆病科】检索到 {len(knowledge_docs)} 份医学文献")
        if knowledge_docs:
            logger.info(f"  文献摘要: {knowledge_docs[0][:100]}...")
        
        alt = lab_results.get("ALT", 0)
        ast = lab_results.get("AST", 0)
        
        diagnoses = []
        confidence = 0.0
        gat_feedback = {}
        
        # 规则 1：ALT/AST 升高 → 肝功能异常
        if alt > 40 or ast > 40:
            diagnoses.append("肝功能异常")
            confidence = 0.75
            gat_feedback["肝胆病科"] = 0.8
        
        if not diagnoses:
            diagnoses.append("肝功能正常")
            confidence = 0.2
            gat_feedback["肝胆病科"] = 0.1
        
        tests = ["肝功能系列"]
        
        logger.info(f"【肝胆病科】诊断：{diagnoses[0]}，置信度：{confidence:.2f}")
        logger.info(f"【肝胆病科】基于专科知识库生成诊疗建议")
        
        return DepartmentDiagnosis(
            department=self.name,
            confidence=confidence,
            primary_diagnosis=diagnoses[0],
            differential_diagnoses=diagnoses[1:],
            recommended_tests=tests,
            referral_to=[],
            clinical_interpretation=f"ALT:{alt}, AST:{ast}",
            gat_feedback=gat_feedback
        )


# 工具注册表
DEPARTMENT_TOOLS = {
    "肾内科": NephologyDepartment(),
    "内分泌科": EndocrinologyDepartment(),
    "血液科": HematologyDepartment(),
    "肝胆病科": HepatologyDepartment(),
}


def create_department_tool(dept_name: str):
    """获取或创建科室工具"""
    if dept_name not in DEPARTMENT_TOOLS:
        raise ValueError(f"不支持的科室: {dept_name}")
    return DEPARTMENT_TOOLS[dept_name]


def call_department_tool(
    dept_name: str,
    lab_results: Dict[str, float],
    previous_diagnoses: Optional[List[DepartmentDiagnosis]] = None,
    gat_confidence: float = 0.5
) -> DepartmentDiagnosis:
    """
    调用科室工具（这是主 Agent 的接口）
    
    Args:
        dept_name: 科室名称
        lab_results: 化验数据
        previous_diagnoses: 前面科室的诊断
        gat_confidence: GAT 对这个科室的置信度
    
    Returns:
        DepartmentDiagnosis
    """
    tool = create_department_tool(dept_name)
    return tool.analyze(lab_results, previous_diagnoses, gat_confidence)
