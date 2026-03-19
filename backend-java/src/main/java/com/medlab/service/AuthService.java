package com.medlab.service;

import com.medlab.dto.request.LoginRequest;
import com.medlab.dto.request.RegisterRequest;
import com.medlab.dto.response.AuthResponse;
import com.medlab.dto.response.UserInfoResponse;
import com.medlab.entity.User;
import com.medlab.repository.UserRepository;
import com.medlab.util.JwtTokenProvider;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * 认证服务
 * 
 * 职责：
 * 1. 处理用户注册（密码加密、数据验证）
 * 2. 处理用户登录（密码验证、Token 生成）
 * 3. 管理用户信息更新
 */
@Slf4j
@Service
public class AuthService {
    
    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private JwtTokenProvider jwtTokenProvider;
    
    @Autowired
    private PasswordEncoder passwordEncoder;
    
    /**
     * 用户注册 - 简化版本（只需要真实姓名、身份证、密码）
     */
    @Transactional
    public AuthResponse register(RegisterRequest request) {
        // 验证密码一致性
        if (!request.getPassword().equals(request.getConfirmPassword())) {
            throw new RuntimeException("两次输入的密码不一致");
        }
        
        // 检查身份证号是否已注册
        if (userRepository.existsByIdNumber(request.getIdNumber())) {
            throw new RuntimeException("该身份证号已被注册");
        }
        
        // 创建新用户
        User user = new User();
        user.setRealName(request.getRealName());
        user.setIdNumber(request.getIdNumber());
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        
        User savedUser = userRepository.save(user);
        
        log.info("用户注册成功: {} ({})", savedUser.getRealName(), savedUser.getIdNumber());
        
        // 生成 Token 并返回
        return buildAuthResponse(savedUser);
    }
    
    /**
     * 用户登录
     */
    @Transactional
    public AuthResponse login(LoginRequest request) {
        User user = userRepository.findByIdNumber(request.getIdNumber())
                .orElseThrow(() -> new RuntimeException("身份证号或密码错误"));
        
        // 验证密码
        if (!passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            throw new RuntimeException("身份证号或密码错误");
        }
        
        log.info("用户登录成功: {}", user.getRealName());
        
        return buildAuthResponse(user);
    }
    
    /**
     * 根据身份证号获取用户信息
     */
    public UserInfoResponse getUserInfoByIdNumber(String idNumber) {
        User user = userRepository.findByIdNumber(idNumber)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        
        return convertToUserInfoResponse(user);
    }
    
    /**
     * 根据用户 ID 获取用户信息
     */
    public UserInfoResponse getUserInfoById(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        
        return convertToUserInfoResponse(user);
    }
    
    /**
     * 修改用户信息
     */
    @Transactional
    public UserInfoResponse updateUserInfo(UUID userId, User updateData) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        
        if (updateData.getRealName() != null) {
            user.setRealName(updateData.getRealName());
        }
        if (updateData.getDrugAllergy() != null) {
            user.setDrugAllergy(updateData.getDrugAllergy());
        }
        
        User savedUser = userRepository.save(user);
        log.info("用户信息更新成功: {}", savedUser.getRealName());
        
        return convertToUserInfoResponse(savedUser);
    }
    
    /**
     * 修改密码
     */
    @Transactional
    public void changePassword(UUID userId, String oldPassword, String newPassword) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        
        // 验证旧密码
        if (!passwordEncoder.matches(oldPassword, user.getPasswordHash())) {
            throw new RuntimeException("旧密码错误");
        }
        
        // 设置新密码
        user.setPasswordHash(passwordEncoder.encode(newPassword));
        userRepository.save(user);
        
        log.info("用户密码修改成功: {}", user.getRealName());
    }
    
    /**
     * 构建认证响应
     */
    private AuthResponse buildAuthResponse(User user) {
        String token = jwtTokenProvider.generateToken(user.getId(), user.getIdNumber());
        
        return AuthResponse.builder()
                .token(token)
                .tokenType("Bearer")
                .expiresIn(jwtTokenProvider.getExpirationTime())
                .user(convertToUserInfoResponse(user))
                .build();
    }
    
    /**
     * 转换为用户信息响应
     */
    private UserInfoResponse convertToUserInfoResponse(User user) {
        return UserInfoResponse.builder()
                .id(user.getId())
                .realName(user.getRealName())
                .build();
    }
}
