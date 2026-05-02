package com.medlab.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 认证响应 DTO
 * 登录/注册成功后返回
 * 包含：
 * 1. JWT 令牌（token） - 用于后续请求的身份验证
 * 2. 令牌类型（tokenType） - 通常为 "Bearer"
 * 3. 令牌过期时间（expiresIn） - 以秒为单位，指示令牌的有效期
 * 4. 用户信息（user） - 包含用户的基本信息（不包含
 *  敏感信息，如密码、身份证号）
 * 设计原则：   
 * 1. 提供必要的认证信息，支持前端进行身份验证和授权
 * 2. 包含用户信息，方便前端显示用户相关数据
 *  3. 设计简洁，避免暴露敏感信息
 *  
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class AuthResponse {

    private String token;

    private String tokenType;

    private Long expiresIn;

    private UserInfoResponse user;
}
