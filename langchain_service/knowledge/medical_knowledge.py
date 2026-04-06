"""
医学知识库和病历查询增强模块
提供参考范围查询、指标异常检测等功能
"""

import logging
from typing import Dict, List, Optional, Tuple
from .reference_ranges import REFERENCE_RANGES, get_reference_range, format_reference_text

logger = logging.getLogger(__name__)


class MedicalKnowledgeBase:
    """医学知识库 - 提供参考范围和指标诊断"""
    
    def __init__(self):
        self.reference_ranges = REFERENCE_RANGES
        self.indicator_mapping = self._build_indicator_mapping()
    
    def _build_indicator_mapping(self) -> Dict[str, List[str]]:
        """构建指标到科室的映射表"""
        return {
            "肾内科": ["Cr", "BUN", "eGFR", "UA", "Na", "K", "Cl", "Ca", "P"],
            "血液科": ["WBC", "RBC", "HB", "HCT", "PLT"],
            "肝胆病科": ["ALT", "AST", "GGT", "ALP", "TBIL", "DBIL"],
            "内分泌科": ["GLU", "CHOL", "TG", "HDL", "LDL"],
            "心内科": ["Ca", "K", "CHOL", "TG", "HDL", "LDL"],
            "感染科": ["WBC", "PLT", "Cr", "ALT"],
        }
    
    def get_reference_range(self, indicator: str, gender: Optional[str] = None) -> Dict:
        """
        获取指标参考范围
        
        Args:
            indicator: 指标代码（如 'Cr', 'WBC'）
            gender: 性别（'M' 或 'F'），某些指标需要
        
        Returns:
            参考范围字典
        """
        ref = self.reference_ranges.get(indicator.upper())
        if not ref:
            return {}
        
        result = ref.copy()
        
        # 性别特异性参考范围处理
        if gender and gender.upper() in ["M", "MALE", "男", "男性"]:
            if "male" in ref:
                result["range"] = ref["male"]
            elif "normal" in ref:
                result["range"] = ref["normal"]
        elif gender and gender.upper() in ["F", "FEMALE", "女", "女性"]:
            if "female" in ref:
                result["range"] = ref["female"]
            elif "normal" in ref:
                result["range"] = ref["normal"]
        elif "male" in ref or "female" in ref:
            # 如果没有指定性别但有性别差异，返回两个范围
            pass
        elif "normal" in ref:
            result["range"] = ref["normal"]
        
        return result
    
    def check_abnormality(
        self, 
        indicator: str, 
        value: float, 
        gender: Optional[str] = None
    ) -> Dict:
        """
        检查指标是否异常
        
        Returns:
            {
                "is_abnormal": bool,
                "level": "critical" | "high" | "low" | "normal",
                "message": str,
                "min_normal": float,
                "max_normal": float
            }
        """
        ref = self.get_reference_range(indicator, gender)
        if not ref:
            return {"is_abnormal": False, "message": f"未知指标: {indicator}"}
        
        result = {
            "indicator": indicator,
            "value": value,
            "is_abnormal": False,
            "level": "normal",
            "message": ""
        }
        
        # 获取正常范围
        normal_range = ref.get("range") or {}
        if not normal_range:
            return result
        
        min_normal = normal_range.get("min")
        max_normal = normal_range.get("max")
        
        result["min_normal"] = min_normal
        result["max_normal"] = max_normal
        
        # 检查危急值
        if "critical_low" in ref and value < ref["critical_low"]:
            result["is_abnormal"] = True
            result["level"] = "critical"
            result["message"] = f"⚠️⚠️【危急值】{ref['name']}严重过低（{value} {ref.get('unit', '')}）"
            return result
        
        if "critical_high" in ref and value > ref["critical_high"]:
            result["is_abnormal"] = True
            result["level"] = "critical"
            result["message"] = f"🚨【危急值】{ref['name']}严重过高（{value} {ref.get('unit', '')}）"
            return result
        
        # 检查异常范围
        if min_normal is not None and value < min_normal:
            result["is_abnormal"] = True
            result["level"] = "low"
            result["message"] = f"↓ {ref['name']} 过低（{value} {ref.get('unit', '')}，正常值 ≥{min_normal}）"
        elif max_normal is not None and value > max_normal:
            result["is_abnormal"] = True
            result["level"] = "high"
            result["message"] = f"↑ {ref['name']} 过高（{value} {ref.get('unit', '')}，正常值 ≤{max_normal}）"
        else:
            result["message"] = f"✓ {ref['name']} 正常（{value} {ref.get('unit', '')}）"
        
        return result
    
    def analyze_lab_results(
        self, 
        results: Dict[str, float], 
        gender: Optional[str] = None
    ) -> Dict:
        """
        批量分析实验室结果
        
        Args:
            results: {"Cr": 120, "BUN": 25, ...}
            gender: 患者性别
        
        Returns:
            分析报告
        """
        abnormalities = []
        normals = []
        unknowns = []
        
        for indicator, value in results.items():
            check = self.check_abnormality(indicator, value, gender)
            if "message" in check and check["message"]:
                if check["is_abnormal"]:
                    abnormalities.append(check)
                else:
                    normals.append(check)
            else:
                unknowns.append(indicator)
        
        # 根据异常指标推荐科室
        recommended_departments = self._recommend_departments(abnormalities)
        
        return {
            "status": "OK" if not abnormalities else "ABNORMAL",
            "abnormalities": abnormalities,
            "normals": normals,
            "unknowns": unknowns,
            "recommended_departments": recommended_departments,
            "summary": self._generate_summary(abnormalities, normals)
        }
    
    def _recommend_departments(self, abnormalities: List[Dict]) -> List[str]:
        """根据异常指标推荐科室"""
        departments = {}
        
        for abnormality in abnormalities:
            indicator = abnormality.get("indicator", "").upper()
            for dept, indicators in self.indicator_mapping.items():
                if indicator in indicators:
                    departments[dept] = departments.get(dept, 0) + 1
        
        # 按相关性排序
        sorted_depts = sorted(departments.items(), key=lambda x: x[1], reverse=True)
        return [dept for dept, _ in sorted_depts]
    
    def _generate_summary(self, abnormalities: List[Dict], normals: List[Dict]) -> str:
        """生成结果摘要"""
        if not abnormalities and normals:
            return "所有检查指标在正常范围内，身体状况良好。"
        
        if abnormalities:
            critical = [a for a in abnormalities if a["level"] == "critical"]
            high = [a for a in abnormalities if a["level"] == "high"]
            low = [a for a in abnormalities if a["level"] == "low"]
            
            summary = ""
            if critical:
                summary += f"【危急值】{len(critical)}项指标异常；"
            if high:
                summary += f"【升高】{len(high)}项指标升高；"
            if low:
                summary += f"【降低】{len(low)}项指标降低；"
            
            return summary.rstrip("；") + "。建议及时就医。"
        
        return "检查完成。"
    
    def get_formatted_reference_text(self, indicator: str) -> str:
        """获取指标的格式化说明"""
        return format_reference_text(indicator)


class PatientHistoryEnhancer:
    """患者病历增强器 - 补充参考范围和历史对比"""
    
    def __init__(self, kb: Optional[MedicalKnowledgeBase] = None):
        self.kb = kb or MedicalKnowledgeBase()
    
    def enhance_medical_summary(
        self,
        base_summary: str,
        current_results: Optional[Dict[str, float]] = None,
        gender: Optional[str] = None
    ) -> str:
        """
        增强病历摘要，添加参考范围和异常检测
        
        Args:
            base_summary: 基础病历摘要（来自数据库）
            current_results: 当前检验结果
            gender: 患者性别
        
        Returns:
            增强后的病历摘要
        """
        enhanced = base_summary + "\n"
        
        if current_results:
            analysis = self.kb.analyze_lab_results(current_results, gender)
            
            enhanced += "\n【当前检验结果分析】\n"
            enhanced += f"状态：{analysis['status']}\n"
            enhanced += f"汇总：{analysis['summary']}\n"
            
            if analysis['abnormalities']:
                enhanced += "\n【异常指标】\n"
                for abnorm in analysis['abnormalities']:
                    enhanced += f"- {abnorm['message']}\n"
                    # 添加参考范围
                    if abnorm.get('min_normal') is not None:
                        enhanced += f"  参考范围：{abnorm['min_normal']} - {abnorm.get('max_normal', '∞')} {abnorm.get('unit', '')}\n"
            
            if analysis['recommended_departments']:
                enhanced += f"\n【建议科室】{', '.join(analysis['recommended_departments'])}\n"
        
        return enhanced


# 导出函数供外部使用
def create_knowledge_base() -> MedicalKnowledgeBase:
    """创建医学知识库实例"""
    return MedicalKnowledgeBase()


def enhance_patient_context(
    base_summary: str,
    results: Optional[Dict[str, float]] = None,
    gender: Optional[str] = None
) -> str:
    """便捷函数：直接增强患者上下文"""
    enhancer = PatientHistoryEnhancer()
    return enhancer.enhance_medical_summary(base_summary, results, gender)


if __name__ == "__main__":
    # 测试
    kb = MedicalKnowledgeBase()
    
    # 测试单个指标异常检测
    print("=" * 60)
    print("单个指标检查")
    print("=" * 60)
    check = kb.check_abnormality("Cr", 150, gender="M")
    print(check)
    
    print("\n" + "=" * 60)
    print("批量分析")
    print("=" * 60)
    
    # 测试批量分析
    results = {
        "Cr": 150,      # 异常升高
        "BUN": 15,      # 异常升高
        "WBC": 3.0,     # 异常降低
        "HB": 140,      # 正常
        "PLT": 200,     # 正常
    }
    
    analysis = kb.analyze_lab_results(results, gender="M")
    print(f"状态：{analysis['status']}")
    print(f"摘要：{analysis['summary']}")
    print(f"推荐科室：{analysis['recommended_departments']}")
    
    print("\n" + "=" * 60)
    print("病历增强")
    print("=" * 60)
    
    base_summary = "患者既往史：无\n过敏药物：无"
    enhanced = enhance_patient_context(base_summary, results, gender="M")
    print(enhanced)
