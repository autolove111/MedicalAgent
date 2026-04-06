"""
检验指标参考范围数据库
提供统一的医学参考值，支持 RAG 系统和患者病历查询
"""

REFERENCE_RANGES = {
    # ===== 肾功能指标 =====
    "Cr": {
        "name": "血肌酐 (Creatinine)",
        "unit": "μmol/L",
        "male": {"min": 80, "max": 115},
        "female": {"min": 60, "max": 93},
        "critical_high": 500,
        "critical_low": 30,
        "description": "肾功能主要标志，升高提示肾脏清除功能下降",
        "clinical_stages": {
            "G1": {"min": None, "max": None, "desc": "正常肾功能（>90 mL/min）"},
            "G2": {"min": None, "max": None, "desc": "轻度肾功能下降（60-89 mL/min）"},
            "G3a": {"min": None, "max": None, "desc": "轻中度肾功能下降（45-59 mL/min）"},
            "G3b": {"min": None, "max": None, "desc": "中重度肾功能下降（30-44 mL/min）"},
            "G4": {"min": None, "max": None, "desc": "重度肾功能下降（15-29 mL/min）"},
            "G5": {"min": None, "max": None, "desc": "肾功能衰竭（<15 mL/min）"}
        }
    },
    "BUN": {
        "name": "血尿素氮 (Blood Urea Nitrogen)",
        "unit": "mmol/L",
        "normal": {"min": 2.5, "max": 8.0},
        "critical_high": 15,
        "description": "肾脏清除功能标志，升高可能提示肾脏病变或脱水"
    },
    "eGFR": {
        "name": "估算肾小球滤过率 (Estimated GFR)",
        "unit": "mL/min/1.73m²",
        "male": {"min": 90, "max": None},
        "female": {"min": 85, "max": None},
        "description": "更准确的肾功能评估指标，基于Cr和年龄等计算"
    },
    "UA": {
        "name": "血尿酸 (Uric Acid)",
        "unit": "μmol/L",
        "male": {"min": 200, "max": 400},
        "female": {"min": 140, "max": 320},
        "critical_high": 600,
        "description": "尿酸代谢指标，升高与痛风、肾脏病相关"
    },

    # ===== 血液系统指标 (CBC) =====
    "WBC": {
        "name": "白细胞计数 (White Blood Cell Count)",
        "unit": "×10⁹/L",
        "normal": {"min": 4.5, "max": 11.0},
        "critical_low": 1.5,
        "critical_high": 30,
        "description": "免疫细胞数量，升高提示感染或炎症，降低提示免疫抑制"
    },
    "RBC": {
        "name": "红细胞计数 (Red Blood Cell Count)",
        "unit": "×10¹²/L",
        "male": {"min": 4.5, "max": 5.9},
        "female": {"min": 4.1, "max": 5.1},
        "critical_low": 2.0,
        "critical_high": 8.0,
        "description": "红细胞数量，降低提示贫血，升高提示脱水或真性红细胞增多症"
    },
    "HB": {
        "name": "血红蛋白 (Hemoglobin)",
        "unit": "g/L",
        "male": {"min": 130, "max": 175},
        "female": {"min": 115, "max": 150},
        "critical_low": 70,
        "description": "携氧蛋白质，降低提示贫血"
    },
    "HCT": {
        "name": "血细胞比容 (Hematocrit)",
        "unit": "%",
        "male": {"min": 41, "max": 53},
        "female": {"min": 36, "max": 46},
        "description": "红细胞容积百分比，用于评估贫血程度"
    },
    "PLT": {
        "name": "血小板计数 (Platelet Count)",
        "unit": "×10⁹/L",
        "normal": {"min": 150, "max": 400},
        "critical_low": 50,
        "critical_high": 1000,
        "description": "止血细胞，降低增加出血风险，升高增加血栓风险"
    },

    # ===== 肝功能指标 =====
    "ALT": {
        "name": "丙氨酸氨基转移酶 (Alanine Aminotransferase)",
        "unit": "U/L",
        "male": {"min": None, "max": 40},
        "female": {"min": None, "max": 32},
        "critical_high": 500,
        "description": "肝脏损伤标志，升高提示肝炎或肝脏病变"
    },
    "AST": {
        "name": "天冬氨酸氨基转移酶 (Aspartate Aminotransferase)",
        "unit": "U/L",
        "normal": {"min": None, "max": 40},
        "critical_high": 500,
        "description": "肝脏和心肌损伤标志，AST/ALT比值>1提示酒精性肝病"
    },
    "GGT": {
        "name": "γ-谷氨酰转肽酶 (Gamma-Glutamyl Transferase)",
        "unit": "U/L",
        "male": {"min": None, "max": 64},
        "female": {"min": None, "max": 36},
        "description": "胆逆流标志，升高与胆石症或肝病相关"
    },
    "ALP": {
        "name": "碱性磷酸酶 (Alkaline Phosphatase)",
        "unit": "U/L",
        "adult": {"min": 30, "max": 120},
        "description": "骨代谢标志，升高与骨病或肝病相关"
    },
    "TBIL": {
        "name": "总胆红素 (Total Bilirubin)",
        "unit": "μmol/L",
        "normal": {"min": None, "max": 20},
        "critical_high": 50,
        "description": "肝脏排泄功能标志，升高提示肝炎或溶血"
    },
    "DBIL": {
        "name": "直接胆红素 (Direct Bilirubin)",
        "unit": "μmol/L",
        "normal": {"min": None, "max": 5},
        "description": "胆道排泄功能标志，升高提示胆汁淤积"
    },

    # ===== 代谢指标 =====
    "GLU": {
        "name": "血糖 (Glucose)",
        "unit": "mmol/L",
        "fasting": {"min": 3.9, "max": 6.0},
        "postprandial": {"min": None, "max": 7.8},
        "critical_low": 2.8,
        "critical_high": 30,
        "description": "能量代谢标志，升高提示糖尿病，降低提示低血糖"
    },
    "CHOL": {
        "name": "总胆固醇 (Total Cholesterol)",
        "unit": "mmol/L",
        "optimal": {"min": None, "max": 5.2},
        "borderline_high": {"min": 5.2, "max": 6.2},
        "high": {"min": 6.2, "max": None},
        "description": "脂质代谢指标，升高与心血管疾病风险相关"
    },
    "TG": {
        "name": "甘油三酯 (Triglycerides)",
        "unit": "mmol/L",
        "normal": {"min": None, "max": 1.7},
        "borderline_high": {"min": 1.7, "max": 2.3},
        "high": {"min": 2.3, "max": None},
        "description": "脂质代谢指标，升高与代谢综合征相关"
    },
    "HDL": {
        "name": "高密度脂蛋白 (High-Density Lipoprotein)",
        "unit": "mmol/L",
        "male": {"min": 1.0, "max": None},
        "female": {"min": 1.3, "max": None},
        "description": "保护性脂蛋白，升高降低心血管风险"
    },
    "LDL": {
        "name": "低密度脂蛋白 (Low-Density Lipoprotein)",
        "unit": "mmol/L",
        "optimal": {"min": None, "max": 2.6},
        "borderline_high": {"min": 2.6, "max": 3.4},
        "high": {"min": 3.4, "max": None},
        "description": "致病性脂蛋白，升高增加心血管风险"
    },

    # ===== 电解质指标 =====
    "Na": {
        "name": "钠离子 (Sodium)",
        "unit": "mmol/L",
        "normal": {"min": 136, "max": 145},
        "critical_low": 120,
        "critical_high": 160,
        "description": "细胞外液主要阳离子，异常与脑水肿或脱水相关"
    },
    "K": {
        "name": "钾离子 (Potassium)",
        "unit": "mmol/L",
        "normal": {"min": 3.5, "max": 5.2},
        "critical_low": 2.5,
        "critical_high": 6.5,
        "description": "细胞内液主要阳离子，异常影响心脏传导"
    },
    "Cl": {
        "name": "氯离子 (Chloride)",
        "unit": "mmol/L",
        "normal": {"min": 98, "max": 107},
        "description": "主要阴离子，参与酸碱平衡"
    },
    "Ca": {
        "name": "血钙 (Calcium)",
        "unit": "mmol/L",
        "normal": {"min": 2.12, "max": 2.63},
        "critical_low": 1.8,
        "critical_high": 3.5,
        "description": "骨代谢和神经肌肉传导关键，异常与骨病或甲状旁腺病相关"
    },
    "Mg": {
        "name": "血镁 (Magnesium)",
        "unit": "mmol/L",
        "normal": {"min": 0.75, "max": 1.02},
        "description": "酶促反应必需元素，降低影响肌肉和神经功能"
    },
    "P": {
        "name": "血磷 (Phosphate)",
        "unit": "mmol/L",
        "normal": {"min": 0.81, "max": 1.45},
        "critical_low": 0.3,
        "critical_high": 2.5,
        "description": "能量代谢和骨矿化关键，异常与肾脏病或骨病相关"
    }
}


def get_reference_range(indicator_code: str) -> dict:
    """获取指定指标的参考范围"""
    return REFERENCE_RANGES.get(indicator_code, {})


def format_reference_text(indicator_code: str) -> str:
    """格式化参考范围为可读文本"""
    ref = get_reference_range(indicator_code)
    if not ref:
        return f"指标 {indicator_code} 参考范围未找到"
    
    text = f"## {ref.get('name', indicator_code)} ({indicator_code})\n"
    text += f"**单位**：{ref.get('unit', '未知')}\n\n"
    
    if "male" in ref and "female" in ref:
        male = ref["male"]
        female = ref["female"]
        text += f"**正常范围**：\n"
        text += f"- 男性：{male.get('min', '-')} - {male.get('max', '-')}\n"
        text += f"- 女性：{female.get('min', '-')} - {female.get('max', '-')}\n"
    elif "normal" in ref:
        normal = ref["normal"]
        text += f"**正常范围**：{normal.get('min', '-')} - {normal.get('max', '-')}\n"
    
    if "critical_low" in ref or "critical_high" in ref:
        text += "\n**危急值**：\n"
        if "critical_low" in ref:
            text += f"- 低于：{ref['critical_low']}\n"
        if "critical_high" in ref:
            text += f"- 高于：{ref['critical_high']}\n"
    
    if "description" in ref:
        text += f"\n**临床意义**：{ref['description']}\n"
    
    return text


if __name__ == "__main__":
    # 测试
    print(format_reference_text("Cr"))
    print("\n" + "="*60 + "\n")
    print(format_reference_text("WBC"))
