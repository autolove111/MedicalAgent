package com.medlab.service;

import com.medlab.entity.User;
import com.medlab.repository.UserRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.UUID;

/**
 * 用户医疗信息服务
 * 
 * 职责：
 * 1. 追加病历记录（对话确认后）
 * 2. 更新过敏药物（对话确认后）
 * 3. 查询用户病历历史（供模型参考）
 */
@Slf4j
@Service
public class UserMedicalService {
    
    @Autowired
    private UserRepository userRepository;
    


    /**
     * 获取用户的病历历史（供模型参考）
     *
     * @param userId 用户ID
     * @return 病历历史字符串
     */
    public String getMedicalHistory(UUID userId) {
        if (!userRepository.existsById(userId)) {
            throw new RuntimeException("用户不存在");
        }
        String history = userRepository.findLifetimeMedicalHistoryById(userId);
        return history != null ? history : "";
    }
    
    /**
     * 获取用户的过敏药物信息
     *
     * @param userId 用户ID
     * @return 过敏药物字符串
     */
    public String getDrugAllergy(UUID userId) {
        if (!userRepository.existsById(userId)) {
            throw new RuntimeException("用户不存在");
        }
        String drug = userRepository.findDrugAllergyById(userId);
        return drug != null ? drug : "";
    }
    
    /**
     * 获取用户的完整医疗摘要（病历+过敏药物，用于给AI模型做上下文）
     *
     * @param userId 用户ID
     * @return 格式化的医疗摘要
     */
    public String getMedicalSummaryForAI(UUID userId) {
        if (!userRepository.existsById(userId)) {
            throw new RuntimeException("用户不存在");
        }

        String drug = userRepository.findDrugAllergyById(userId);
        String history = userRepository.findLifetimeMedicalHistoryById(userId);

        StringBuilder sb = new StringBuilder();

        if (drug != null && !drug.isEmpty()) {
            sb.append("【过敏药物】").append(drug).append("\n");
        }

        if (history != null && !history.isEmpty()) {
            sb.append("【病历历史】").append(history);
        }

        return sb.toString();
    }
}
