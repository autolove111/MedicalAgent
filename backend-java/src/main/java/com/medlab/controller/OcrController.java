package com.medlab.controller;

import com.medlab.service.OcrServiceClient;
import com.medlab.service.AnalyzeVisionResponse;
import com.medlab.service.OcrServiceException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.Map;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;
import java.util.List;

/**
 * OCR 识别 REST 接口
 * 
 * 职责：
 * 1. 🎯 接收前端上传的文件（由 FileUploadController 处理）
 * 2. 📤 触发 Python OCR 服务的异步识别
 * 3. 📥 返回异步识别结果给前端
 * 
 * 设计特点：
 * - ⚡ 异步接口：返回 Mono<ResponseEntity>，不阻塞 Tomcat 线程
 * - 🔄 链式处理：使用 flatMap 进行多步异步操作
 * - 🛡️ 错误处理：统一处理业务异常、网络异常、超时异常
 * - 📊 日志记录：详细记录每个请求的生命周期
 * 
 * 与同步 Controller 的区别：
 * ✅ 异步（当前）：方法返回 Mono/Flux，Spring 自动处理异步推送
 * ❌ 同步（传统）：阻塞线程，需要线程池支撑高并发
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/ocr")
@RequiredArgsConstructor
public class OcrController {

    private final OcrServiceClient ocrServiceClient;

    /**
     * 异步视觉识别接口
     * 
     * 流程：
     * 1. 📝 前端提供文件路径（Java 已上传并保存）
     * 2. 🚀 通过 WebClient 异步调用 Python OCR 服务
     * 3. ⏳ 不阻塞其他请求（使用反应式编程）
     * 4. 📥 返回科技识别结果：VisionItem 列表
     * 5. 🛡️ 异常处理：超时、网络、业务错误
     * 
     * HTTP 状态码：
     * - 200 OK: 识别成功
     * - 400 Bad Request: 参数错误（文件不存在）
     * - 504 Gateway Timeout: Python 服务超时
     * - 500 Internal Server Error: 其他错误
     * 
     * @param filePath 文件绝对路径（例：/opt/medlab/uploads/report.jpg）
     * @param model    LLM 模型（可选，默认使用配置值）
     * @return 异步识别结果
     * 
     * 示例请求：
     * POST /api/v1/ocr/analyze-vision?filePath=/uploads/report.jpg&model=qwen-vl-plus
     * 
     * 示例响应（200 OK）:
     * {
     *   "status": "success",
     *   "file_path": "/uploads/report.jpg",
     *   "model": "qwen-vl-plus",
     *   "analysis": [
     *     {
     *       "item": "红细胞计数",
     *       "value": "4.5",
     *       "unit": "10¹²/L",
     *       "normal_range": "4.0-5.5",
     *       "status": "正常"
     *     }
     *   ]
     * }
     */
    @PostMapping("/analyze-vision")
    public Mono<ResponseEntity<Map<String, Object>>> analyzeVisionAsync(
            @RequestParam String filePath,
            @RequestParam(required = false) String model) {

        log.info("🎯 接收视觉识别请求：file={}, model={}", filePath, model);

        // 参数验证
        if (filePath == null || filePath.trim().isEmpty()) {
            log.warn("❌ 缺少必填参数：filePath");
            return Mono.just(ResponseEntity.badRequest()
                    .body(Map.of("error", "Missing parameter: filePath")));
        }

        // 🚀 异步调用 Python OCR 服务（核心）
        return ocrServiceClient.analyzeVisionAsync(filePath, model)
                // 🎯 成功处理：封装为 HTTP 响应
                .map(response -> ResponseEntity.ok().body(
                    Map.of(
                        "status", response.getStatus(),
                        "file_path", response.getFile_path(),
                        "model", response.getModel(),
                        "analysis", response.getAnalysis()
                    )))
                // 🛡️ 错误处理：捕获异常并转换为 HTTP 错误响应
                .onErrorResume(error -> {
                    if (error instanceof OcrServiceException) {
                        OcrServiceException ocrError = (OcrServiceException) error;
                        int statusCode = ocrError.getHttpStatusCode();
                        HttpStatus httpStatus = HttpStatus.resolve(statusCode) != null
                                ? HttpStatus.resolve(statusCode)
                                : HttpStatus.INTERNAL_SERVER_ERROR;
                        
                        log.error("❌ 识别失败（{}）：{}", statusCode, error.getMessage());
                        return Mono.just(ResponseEntity.status(httpStatus)
                                .body(Map.of(
                                    "error", error.getMessage(),
                                    "status_code", statusCode
                                )));
                    }
                    
                    log.error("❌ 未知错误：{}", error.getMessage(), error);
                    return Mono.just(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                            .body(Map.of(
                                "error", "Internal server error: " + error.getMessage(),
                                "status_code", 500
                            )));
                });
    }

    /**
     * 批量异步识别接口
     * 
     * 用途：
     * - 🏥 医院场景：同时处理多个患者的化验报告
     * - 📊 批量导入：导入多个历史记录
     * - 🔄 并发处理：充分利用异步特性
     *
     * @param filePaths 文件路径列表
     * @return 映射：[文件路径 -> 识别结果]
     */
    @PostMapping("/analyze-batch")
    public Mono<ResponseEntity<Map<String, Object>>> analyzeBatchAsync(
            @RequestBody List<String> filePaths) {

        log.info("📋 接收批量识别请求：共 {} 个文件", filePaths.size());

        if (filePaths == null || filePaths.isEmpty()) {
            return Mono.just(ResponseEntity.badRequest()
                    .body(Map.of("error", "Empty file list")));
        }

        // 异步处理多个文件
        return ocrServiceClient.analyzeMultipleFilesAsync(filePaths)
                .map(results -> ResponseEntity.ok().body(
                    Map.of(
                        "status", "completed",
                        "total", filePaths.size(),
                        "results", results
                    )))
                .onErrorResume(error -> {
                    log.error("❌ 批量识别失败：{}", error.getMessage());
                    return Mono.just(ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                            .body(Map.of(
                                "error", error.getMessage(),
                                "status_code", 500
                            )));
                });
    }

    /**
     * 健康检查端点
     * 
     * 作用：
     * - 🔍 验证 Python OCR 服务连接状态
     * - 🚀 在文件上传后调用，确保后续识别可以进行
     * - 📊 用于监控和告警系统
     *
     * @return 健康状态
     */
    @GetMapping("/health")
    public Mono<ResponseEntity<Map<String, Object>>> healthCheckAsync() {
        return ocrServiceClient.healthCheckAsync()
                .map(healthy -> {
                    Map<String, Object> body = new HashMap<>();
                    if (healthy) {
                        body.put("status", "healthy");
                        body.put("service", "OCR Service");
                        body.put("message", "Python OCR service is available");
                        return ResponseEntity.ok().body(body);
                    } else {
                        body.put("status", "unhealthy");
                        body.put("service", "OCR Service");
                        body.put("message", "Python OCR service is unavailable");
                        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body);
                    }
                })
                .onErrorResume(error -> {
                    Map<String, Object> body = new HashMap<>();
                    body.put("status", "error");
                    body.put("service", "OCR Service");
                    body.put("message", error.getMessage());
                    return Mono.just(ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body));
                });
    }

    /**
     * 支持的模型列表
     * 
     * 提供给前端，让用户选择 LLM 模型
     */
    @GetMapping("/models")
    public ResponseEntity<Map<String, Object>> getAvailableModels() {
        return ResponseEntity.ok().body(Map.of(
            "models", List.of(
                Map.of(
                    "name", "qwen-vl-plus",
                    "description", "阿里千问（默认，最快，最便宜，中文优化）",
                    "is_default", true
                ),
                Map.of(
                    "name", "gpt-4o",
                    "description", "OpenAI GPT-4o（最强，昂贵）",
                    "is_default", false
                ),
                Map.of(
                    "name", "claude-3-5-sonnet",
                    "description", "Anthropic Claude（高可靠性）",
                    "is_default", false
                ),
                Map.of(
                    "name", "mock",
                    "description", "模拟数据（用于测试和开发）",
                    "is_default", false
                )
            )
        ));
    }
}
