package com.medlab.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.persistence.*;
import java.util.UUID;

/**
 * 用户实体类
 * 对应数据库 users 表
 * 
 * 职责：
 * 1. 存储用户注册信息（姓名、身份证号、密码）
 * 2. 存储过敏药物信息
 * 3. 记录用户一生的病历历史
 */
@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class User {
    
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(columnDefinition = "UUID")
    private UUID id;
    
    @Column(nullable = false, length = 100)
    private String realName;
    
    @Column(unique = true, nullable = false, length = 50)
    private String idNumber;
    
    @Column(nullable = false, length = 255)
    private String passwordHash;
    
    @Column(columnDefinition = "TEXT")
    private String drugAllergy;
    
    @Column(columnDefinition = "TEXT")
    private String lifetimeMedicalHistory;
}
