package com.medlab.service;

import lombok.Data;

/**
 * 视觉识别结果项（化验单中的单一检查项）
 */
@Data
public class VisionItem {
    /** 检查项目名称（如：红细胞计数） */
    private String item;
    
    /** 数值（如：4.5） */
    private String value;
    
    /** 单位（如：10¹²/L） */
    private String unit;
    
    /** 正常范围（如：4.0-5.5） */
    private String normal_range;
    
    /**
     * 状态：
     * - "正常"  
     * - "↑ 升高"
     * - "↓ 降低"
     */
    private String status;
}
