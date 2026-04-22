package com.medlab.service;

import com.medlab.entity.User;
import com.medlab.repository.UserRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.Period;
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

    /**
     * 从用户数据库信息计算年龄（单位：岁，向下取整）。
     */
    public Double getAgeYears(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));

        if (user.getAge() != null) {
            return Math.max(user.getAge().doubleValue(), 0.0);
        }

        LocalDate birthDate = parseBirthDateFromIdNumber(user.getIdNumber());
        if (birthDate == null) {
            return null;
        }

        int years = Period.between(birthDate, LocalDate.now()).getYears();
        return (double) Math.max(years, 0);
    }

    public Boolean isPediatric(UUID userId) {
        Double ageYears = getAgeYears(userId);
        return ageYears != null && ageYears < 14.0;
    }

    private LocalDate parseBirthDateFromIdNumber(String idNumber) {
        if (idNumber == null) {
            return null;
        }

        String raw = idNumber.trim();
        try {
            if (raw.matches("\\d{17}[\\dXx]")) {
                String yyyymmdd = raw.substring(6, 14);
                int year = Integer.parseInt(yyyymmdd.substring(0, 4));
                int month = Integer.parseInt(yyyymmdd.substring(4, 6));
                int day = Integer.parseInt(yyyymmdd.substring(6, 8));
                return LocalDate.of(year, month, day);
            }
            if (raw.matches("\\d{15}")) {
                String yymmdd = raw.substring(6, 12);
                int year = 1900 + Integer.parseInt(yymmdd.substring(0, 2));
                int month = Integer.parseInt(yymmdd.substring(2, 4));
                int day = Integer.parseInt(yymmdd.substring(4, 6));
                return LocalDate.of(year, month, day);
            }
        } catch (Exception e) {
            log.warn("身份证出生日期解析失败: {}", e.getMessage());
            return null;
        }
        return null;
    }
}
