package com.medlab.dto.request;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 登录请求 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoginRequest {

    @NotBlank(message = "身份证号不能为空")
    @Size(min = 18, max = 18, message = "身份证号应为18位")
    private String idNumber;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 255, message = "密码长度应为 6-255 字符")
    private String password;
}