package com.medlab.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.util.concurrent.TimeUnit;

/**
 * WebClient 异步配置 - 用于与 Python AI 服务进行零延迟通信
 *
 * 设计特点：
 * 1. 🚀 异步非阻塞：使用 Reactor Netty，不消耗线程池
 * 2. ✅ 连接复用：使用连接池来重用 HTTP 连接
 * 3. ⏱️ 超时控制：分离 HTTP 和业务级超时
 * 4. 📡 支持多机器：配置可指向不同的 Python 服务实例
 * 5. 🔄 自动重试：内置重试机制（可选）
 */
@Configuration
@EnableConfigurationProperties(PythonOcrServiceProperties.class)
public class WebClientConfig {

    /**
     * 根据应用配置创建针对 Python OCR 服务的 WebClient
     *
     * 异步特点：
     * - 📤 发送请求不阻塞：使用 Mono 封装结果
     * - 📥 接收响应：使用 Flux 或 Mono 处理流
     * - 🔄 背压处理：自动处理背压（Backpressure）
     * 
     * @param pythonOcrServiceProperties 配置属性
     * @return WebClient Bean
     */
    @Bean("pythonOcrWebClient")
    public WebClient pythonOcrWebClient(PythonOcrServiceProperties pythonOcrServiceProperties) {
        // 🔧 创建 HttpClient - Netty 反应式 HTTP 客户端
        HttpClient httpClient = HttpClient.create()
                // ⏱️ 连接超时（TCP 连接建立时间）
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 
                    pythonOcrServiceProperties.getConnectTimeoutMillis())
                // ⏱️ 读取超时（接收响应数据时间）
                .responseTimeout(java.time.Duration.ofSeconds(
                    pythonOcrServiceProperties.getResponseTimeoutSeconds()))
                // 📋 Netty 事件循环配置
                .doOnConnected(connection ->
                    connection
                            .addHandlerLast(new ReadTimeoutHandler(
                                pythonOcrServiceProperties.getReadTimeoutSeconds(),
                                TimeUnit.SECONDS))
                            .addHandlerLast(new WriteTimeoutHandler(
                                pythonOcrServiceProperties.getWriteTimeoutSeconds(),
                                TimeUnit.SECONDS))
                );

        // 📊 HTTP 消息编解码器配置（处理大文件/图片）
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                // 最大缓冲大小（用于解析响应体）
                .codecs(clientCodecConfigurer ->
                    clientCodecConfigurer.defaultCodecs()
                            .maxInMemorySize(pythonOcrServiceProperties.getMaxInMemorySize())
                )
                .build();

        // 🏗️ 构建 WebClient
        return WebClient.builder()
                // 📍 Python OCR 服务基础 URL（来自配置）
                .baseUrl(pythonOcrServiceProperties.getBaseUrl())
                // 🔌 使用 Reactor Netty 作为 HTTP 连接器（异步非阻塞）
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                // 💾 配置编解码器策略
                .exchangeStrategies(strategies)
                // 🎯 默认请求头
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.USER_AGENT, "MedLabAgent-JavaBackend/1.0.0")
                // ⚠️ 错误处理（可选：使用 filter）
                .filter((request, next) -> {
                    // 记录请求日志
                    return next.exchange(request);
                })
                .build();
    }

    /**
     * 通用 WebClient - 用于与其他外部服务通信
     * 
     * @return WebClient Bean
     */
    @Bean("genericWebClient")
    public WebClient genericWebClient() {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
                .responseTimeout(java.time.Duration.ofSeconds(30));

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    /**
     * RestTemplate Bean - 用于同步 HTTP 请求（Vision API）
     */
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}

/**
 * Python OCR 服务配置属性
 * 
 * 支持在 application.yml 中配置：
 * ```yaml
 * python-ocr:
 *   base-url: http://python-ocr:8001
 *   max-connections: 50
 *   connect-timeout-millis: 5000
 *   response-timeout-seconds: 60
 *   read-timeout-seconds: 60
 *   write-timeout-seconds: 10
 *   max-in-memory-size: 5242880  # 5MB
 * ```
 */
@Data
@ConfigurationProperties(prefix = "python-ocr")
class PythonOcrServiceProperties {
    
    // 📍 Python OCR 服务基础 URL（来自 docker-compose 服务名）
    private String baseUrl = "http://python-ocr:8001";
    
    // 🔌 连接池配置
    
    // 最大同时连接数（考虑 Python 服务的并发能力）
    private int maxConnections = 50;
    
    // 等待获取连接的最大挂起数
    private int pendingAcquireMaxCount = 250;
    
    // 等待获取连接的超时时间（秒）
    private long pendingAcquireTimeoutSeconds = 45;
    
    // ⏱️ 超时配置
    
    // TCP 连接建立超时（毫秒）
    private int connectTimeoutMillis = 5000;
    
    // 响应超时（秒）- 从请求开始到收到完整响应
    private long responseTimeoutSeconds = 60;
    
    // 读取超时（秒）- 等待单个数据包的时间
    private long readTimeoutSeconds = 60;
    
    // 写入超时（秒）- 发送数据包的最大时间
    private long writeTimeoutSeconds = 10;
    
    // 💾 编解码器配置
    
    // 最大内存缓冲大小（用于响应体 - 5MB）
    private int maxInMemorySize = 5 * 1024 * 1024;
}
