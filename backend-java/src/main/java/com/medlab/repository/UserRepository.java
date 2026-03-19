package com.medlab.repository;

import com.medlab.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/**
 * 用户数据访问层
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {
    /**
     * 根据身份证号查找用户
     */
    Optional<User> findByIdNumber(String idNumber);

    /**
     * 检查身份证号是否存在
     */
    boolean existsByIdNumber(String idNumber);

    /**
     * 追加病历记录到 lifetime_medical_history
     * 在现有内容后面追加新记录，用分号分隔
     */
    @Modifying
    @Query("UPDATE User u SET u.lifetimeMedicalHistory = " +
           "CASE WHEN u.lifetimeMedicalHistory IS NULL OR u.lifetimeMedicalHistory = '' " +
           "THEN :record ELSE CONCAT(u.lifetimeMedicalHistory, '；', :record) END " +
           "WHERE u.id = :userId")
    void appendMedicalHistory(@Param("userId") UUID userId, @Param("record") String record);

    /**
     * 更新过敏药物
     */
    @Modifying
    @Query("UPDATE User u SET u.drugAllergy = :drugAllergy WHERE u.id = :userId")
    void updateDrugAllergy(@Param("userId") UUID userId, @Param("drugAllergy") String drugAllergy);

    /**
     * 直接查询用户的 lifetimeMedicalHistory 字段（将逻辑放在 repository 层）
     * 返回 null 表示用户不存在或字段为空
     */
    @Query("SELECT u.lifetimeMedicalHistory FROM User u WHERE u.id = :userId")
    String findLifetimeMedicalHistoryById(@Param("userId") UUID userId);

    /**
     * 直接查询用户的 drugAllergy 字段（将逻辑放在 repository 层）
     */
    @Query("SELECT u.drugAllergy FROM User u WHERE u.id = :userId")
    String findDrugAllergyById(@Param("userId") UUID userId);
}
