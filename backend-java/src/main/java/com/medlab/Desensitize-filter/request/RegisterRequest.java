package com.medlab.dto.request;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

/**
 * 注册请求 DTO - 简化版本
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class RegisterRequest {
    
    @NotBlank(message = "真实姓名不能为空")
    @Size(min = 2, max = 100, message = "真实姓名长度应为 2-100 字符")
    private String realName;
    
    @NotBlank(message = "身份证号不能为空")
    @Pattern(regexp = "^[0-9X]{18}$", message = "身份证号格式不正确")
    private String idNumber;
    
    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 255, message = "密码长度应为 6-255 字符")
    private String password;
    
    @NotBlank(message = "确认密码不能为空")
    private String confirmPassword;

    @NotNull(message = "年龄不能为空")
    @Min(value = 0, message = "年龄不能小于0")
    @Max(value = 150, message = "年龄不能大于150")
    private Integer age;
}
