package com.medlab.service;

import lombok.Data;

/**
 * OCR 服务异常
 * 
 * 用于处理调用 Python OCR 服务时的各种异常情况：
 * 1. 网络异常（超时、连接失败）
 * 2. HTTP 错误（4xx、5xx）
 * 3. 业务异常（JSON 解析错误、参数错误）
 * 
 * 异常处理流程：
 * 1. OcrServiceClient 捕获异常并转换为该类
 * 2. 在 Controller 中统一处理并返回正确的 HTTP 状态码
 * 3. 记录详细的错误信息用于日志分析
 */
@Data
public class OcrServiceException extends RuntimeException {
    private int httpStatusCode;

    public OcrServiceException(String message, int httpStatusCode) {
        super(message);
        this.httpStatusCode = httpStatusCode;
    }

    public OcrServiceException(String message, Throwable cause, int httpStatusCode) {
        super(message, cause);
        this.httpStatusCode = httpStatusCode;
    }

    public int getHttpStatusCode() {
        return httpStatusCode;
    }
}
