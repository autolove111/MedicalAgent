package com.medlab.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "python-ocr")
public class PythonOcrServiceProperties {
    
    /**
     * OCR 服务基础 URL
     * Docker 环境: http://python-ocr:8001
     * 本地开发: http://localhost:8001
     */
    private String baseUrl = "http://python-ocr:8001";
    
    /**
     * 连接超时（毫秒）- TCP 连接建立时间
     */
    private int connectTimeoutMillis = 5000;
    
    /**
     * 响应超时（秒）- 等待完整响应的时间
     */
    private long responseTimeoutSeconds = 90;
    
    /**
     * 读超时（秒）- 单个数据包读取超时
     */
    private int readTimeoutSeconds = 90;
    
    /**
     * 写超时（秒）- 单个数据包发送超时
     */
    private int writeTimeoutSeconds = 10;
    
    /**
     * 最大内存缓冲（字节）- 用于解析响应体（5MB）
     */
    private int maxInMemorySize = 5 * 1024 * 1024;
}
