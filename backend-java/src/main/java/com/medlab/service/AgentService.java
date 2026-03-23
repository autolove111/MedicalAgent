package com.medlab.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 智能体服务（LangChain Agent 客户端）
 * 
 * 职责：
 * 1. 建立 Java 后端与 Python LangChain 服务的通信
 * 2. 接收医学影像提取的文本，调用 Agent 进行分析
 * 3. 返回 Agent 的诊断分析结果
 * 
 * 工作流：
 * File Upload → Vision API 提取文本 → Agent 分析 → 返回诊断结论
 */
@Service
@RequiredArgsConstructor
public class AgentService {

    private static final Logger log = LoggerFactory.getLogger(AgentService.class);

    // LangChain 服务连接配置
    @Value("${langchain.service.url:http://localhost:8000}")
    private String langchainServiceUrl;

    @Value("${langchain.service.timeout:30000}")
    private long requestTimeout;

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 调用 LangChain Agent 进行医学报告分析
     * 
     * @param extractedText 从医学影像中提取的文本内容
     * @param userId        用户 ID（用于查询用户医学历史、过敏信息等）
     * @return Agent 的分析结果（诊断、建议等）
     */
    public String analyzeLabReport(String extractedText, String userId) {
        try {
            log.info("📤 调用 LangChain Agent：userId={}, textLength={}", userId, extractedText.length());

            // 构建请求 URL
            String url = UriComponentsBuilder.fromHttpUrl(langchainServiceUrl)
                    .path("/api/v1/agent/chat/stream")
                    .queryParam("userQuery", extractedText)
                    .queryParam("userId", userId != null ? userId : "anonymous")
                    .toUriString();

            log.debug("Agent 请求 URL: {}", url);

            // 设置请求头
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("User-Agent", "MedLabAgent-Backend");

            // 创建请求体（备选方案，如果 URL 参数不可用）
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("query", extractedText);
            requestBody.put("user_id", userId != null ? userId : "anonymous");

            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(requestBody, headers);

            // 🚀 同步调用 Agent 服务
            log.debug("🔄 等待 Agent 响应...");
            long startTime = System.currentTimeMillis();

            ResponseEntity<String> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    requestEntity,
                    String.class
            );

            long duration = System.currentTimeMillis() - startTime;
            log.info("✅ Agent 响应成功（耗时: {}ms）", duration);

            // 解析响应
            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                try {
                    JsonNode responseJson = objectMapper.readTree(response.getBody());
                    String analysisContent = responseJson.path("content").asText();
                    
                    if (analysisContent.isEmpty()) {
                        log.warn("⚠️ Agent 返回空的内容字段");
                        return "Agent 分析失败：返回结果为空";
                    }
                    
                    log.info("📊 分析结果长度: {} 字符", analysisContent.length());
                    return analysisContent;
                } catch (Exception e) {
                    log.error("❌ 解析 Agent 响应 JSON 失败: {}", e.getMessage());
                    return "Agent 分析失败：响应格式错误";
                }
            } else {
                log.error("❌ Agent 服务返回异常状态：{}", response.getStatusCode());
                return "Agent 分析失败：服务异常（状态码：" + response.getStatusCode() + "）";
            }

        } catch (Exception e) {
            log.error("❌ 调用 LangChain Agent 异常: {}", e.getMessage(), e);
            return "Agent 分析失败：" + e.getMessage();
        }
    }

    /**
     * 简化版：不需要用户 ID 的分析
     * 适用于临时或匿名分析
     */
    public String analyzeLabReport(String extractedText) {
        return analyzeLabReport(extractedText, "anonymous");
    }

    /**
     * 【方案 B】使用 OCR 识别结果进行 Agent 分析
     * 
     * 新工作流：
     * File Upload → OCR 服务识别 → Agent 分析（不再调用 Vision API）
     * 
     * @param ocrResult OCR 服务返回的识别结果（包含医学指标）
     * @param userId    用户 ID（用于查询用户医学历史、过敏信息等）
     * @return Agent 的分析结果（诊断、建议等）
     */
    public String analyzeWithOcrResult(AnalyzeVisionResponse ocrResult, String userId) {
        try {
            if (ocrResult == null || ocrResult.getAnalysis() == null) {
                return "❌ OCR 识别失败：无识别结果";
            }
            
            // 将 OCR 结果转换为易读的文本格式
            String extractedText = formatOcrResultToText(ocrResult);
            
            log.info("📤 调用 LangChain Agent（使用 OCR 结果）：userId={}, itemCount={}", 
                    userId, ocrResult.getAnalysis().size());
            
            // 构建请求 URL
            String url = UriComponentsBuilder.fromHttpUrl(langchainServiceUrl)
                    .path("/api/v1/agent/chat/stream")
                    .queryParam("userQuery", extractedText)
                    .queryParam("userId", userId != null ? userId : "anonymous")
                    .toUriString();

            log.debug("Agent 请求 URL: {}", url);

            // 设置请求头
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("User-Agent", "MedLabAgent-Backend");

            // 创建请求体
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("query", extractedText);
            requestBody.put("user_id", userId != null ? userId : "anonymous");
            requestBody.put("ocr_result", ocrResult);  // 将 OCR 原始结果也传递给 Agent

            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(requestBody, headers);

            // 🚀 同步调用 Agent 服务
            log.debug("🔄 等待 Agent 响应...");
            long startTime = System.currentTimeMillis();

            ResponseEntity<String> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    requestEntity,
                    String.class
            );

            long duration = System.currentTimeMillis() - startTime;
            log.info("✅ Agent 响应成功（耗时: {}ms）", duration);

            // 解析响应
            if (response.getStatusCode() == HttpStatus.OK && response.getBody() != null) {
                try {
                    JsonNode responseJson = objectMapper.readTree(response.getBody());
                    String analysisContent = responseJson.path("content").asText();
                    
                    if (analysisContent.isEmpty()) {
                        log.warn("⚠️ Agent 返回空的内容字段");
                        return "Agent 分析失败：返回结果为空";
                    }
                    
                    log.info("📊 分析结果长度: {} 字符", analysisContent.length());
                    return analysisContent;
                } catch (Exception e) {
                    log.error("❌ 解析 Agent 响应 JSON 失败: {}", e.getMessage());
                    return "Agent 分析失败：响应格式错误";
                }
            } else {
                log.error("❌ Agent 服务返回异常状态：{}", response.getStatusCode());
                return "Agent 分析失败：服务异常（状态码：" + response.getStatusCode() + "）";
            }

        } catch (Exception e) {
            log.error("❌ 调用 LangChain Agent 异常: {}", e.getMessage(), e);
            return "Agent 分析失败：" + e.getMessage();
        }
    }

    /**
     * 将 OCR 识别结果转换为易读的文本格式
     * 便于 Agent 进行进一步分析
     */
    private String formatOcrResultToText(AnalyzeVisionResponse ocrResult) {
        if (ocrResult.getAnalysis() == null || ocrResult.getAnalysis().isEmpty()) {
            return "化验单识别结果为空";
        }
        
        StringBuilder sb = new StringBuilder();
        sb.append("【化验单识别结果】\n");
        
        for (VisionItem item : ocrResult.getAnalysis()) {
            sb.append(String.format("- %s: %s %s (正常范围：%s) [%s]\n",
                    item.getItem() != null ? item.getItem() : "未知",
                    item.getValue() != null ? item.getValue() : "N/A",
                    item.getUnit() != null ? item.getUnit() : "",
                    item.getNormal_range() != null ? item.getNormal_range() : "N/A",
                    item.getStatus() != null ? item.getStatus() : "未知"));
        }
        
        return sb.toString();
    }
}
