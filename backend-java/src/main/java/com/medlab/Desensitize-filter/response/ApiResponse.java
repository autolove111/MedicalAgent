package com.medlab.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 通用 API 响应 DTO
 * 所有 API 层响应都使用此格式
 * 包含：
 * 1. 响应状态码（code）   
 * 2. 响应消息（message）
 * 3. 响应数据（data） - 泛型，适用于各种类型的数据
 * 4. 响应时间戳（timestamp） - 记录响应生成的时间，便于调试和日志记录
 * 设计原则：
 * 1. 统一响应格式，简化前端处理逻辑
 * 2. 提供静态工厂方法，方便创建成功和错误响应
 * 3. 包含时间戳，便于追踪请求和响应的时间点
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ApiResponse<T> {
    
    private String code;
    
    private String message;
    
    private T data;
    
    private Long timestamp;
    
    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .code("200")
                .message("success")
                .data(data)
                .timestamp(System.currentTimeMillis())
                .build();
    }
    
    public static <T> ApiResponse<T> success(T data, String message) {
        return ApiResponse.<T>builder()
                .code("200")
                .message(message)
                .data(data)
                .timestamp(System.currentTimeMillis())
                .build();
    }
    
    public static <T> ApiResponse<T> error(String code, String message) {
        return ApiResponse.<T>builder()
                .code(code)
                .message(message)
                .timestamp(System.currentTimeMillis())
                .build();
    }
    
    public static <T> ApiResponse<T> error(String message) {
        return ApiResponse.<T>builder()
                .code("500")
                .message(message)
                .timestamp(System.currentTimeMillis())
                .build();
    }
}
