package com.medlab.service;

import com.medlab.entity.SessionMessage;
import com.medlab.repository.SessionMessageRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import java.util.HashMap;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.MediaType;
import org.springframework.beans.factory.annotation.Autowired;
import com.medlab.service.UserMedicalService;
import com.medlab.util.JwtTokenProvider;

/**
 * 会话对话历史服务
 * 
 * 职责：
 * 1. 保存每轮用户提问和AI回复
 * 2. 查询某用户的全部会话历史（按时间升序）
 * 3. 用户登出时清空该用户的全部会话记录
 */
@Slf4j
@Service
public class SessionChatService {

    @Autowired
    private SessionMessageRepository sessionMessageRepository;

    @Autowired
    private WebClient.Builder webClientBuilder;

    @Value("${langchain.service.url:http://langchain-service:8000}")
    private String langchainServiceUrl;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Autowired
    private UserMedicalService userMedicalService;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    /**
     * 接收前端传入的 Authorization header（可能为空），解析后调用内部的 chat 方法
     */
    public Map<String, String> chatWithAuth(String authHeader, String userQuery) {
        try {
            UUID userId = null;
            if (authHeader != null && authHeader.startsWith("Bearer ")) {
                String token = authHeader.substring(7);
                if (jwtTokenProvider.validateToken(token)) {
                    userId = jwtTokenProvider.getUserIdFromToken(token);
                }
            }
            return chat(userId, userQuery);
        } catch (Exception e) {
            Map<String, String> err = new HashMap<>();
            err.put("content", "认证或会话处理出错: " + e.getMessage());
            return err;
        }
    }

    /**
     * 保存一条会话消息
     */
    // 将一条消息持久化到会话表（userId 可以为空表示匿名）
    public void saveMessage(UUID userId, String role, String content) {
        SessionMessage msg = new SessionMessage();
        msg.setUserId(userId);
        msg.setRole(role);
        msg.setContent(content);
        msg.setCreatedAt(LocalDateTime.now());
        sessionMessageRepository.save(msg);
    }

    private WebClient getWebClient() {
        // 构造用于调用外部 langchain 服务的 WebClient
        return webClientBuilder.baseUrl(langchainServiceUrl).build();
    }

    /**
     * 与 LangChain 同步聊天（非流式）
     */
    // 组装用户上下文和历史，发送到外部 langchain 服务，保存用户与助手的消息
    public Map<String, String> chat(UUID userId, String userQuery) {
        try {
            String userContext = null;
            if (userId != null) {
                try {
                    userContext = userMedicalService.getMedicalSummaryForAI(userId);
                } catch (Exception e) {
                    userContext = null;
                }
            }

            List<SessionMessage> history = null;
            if (userId != null) history = getHistory(userId);

            // 保存用户问题
            if (userId != null) saveMessage(userId, "user", userQuery);

            Map<String, Object> request = new HashMap<>();
            request.put("query", userQuery);
            request.put("user_id", userId != null ? userId.toString() : null);
            request.put("user_context", userContext);
            request.put("history", history);

            String responseBody = getWebClient()
                    .post()
                    .uri("/api/v1/agent/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            Map<String, String> result = new HashMap<>();
            if (responseBody != null) {
                var node = objectMapper.readTree(responseBody);
                if (node.has("content")) {
                    String content = node.get("content").asText();
                    result.put("content", content);
                    if (userId != null) saveMessage(userId, "assistant", content);
                    return result;
                }
            }
            result.put("content", responseBody != null ? responseBody : "");
            if (userId != null) saveMessage(userId, "assistant", responseBody != null ? responseBody : "");
            return result;
        } catch (Exception e) {
            Map<String, String> err = new HashMap<>();
            err.put("content", "服务调用出错: " + e.getMessage());
            return err;
        }
    }

    /**
     * 同步分析医疗报告
     */
    // 将报告内容与用户上下文一起发送给外部分析接口，保存分析结果到会话
    public Map<String, String> analyzeReport(UUID userId, String reportContent) {
        try {
            String userContext = null;
            if (userId != null) {
                try {
                    userContext = userMedicalService.getMedicalSummaryForAI(userId);
                } catch (Exception e) {
                    userContext = null;
                }
            }

            Map<String, Object> request = new HashMap<>();
            request.put("query", reportContent);
            request.put("user_id", userId != null ? userId.toString() : null);
            request.put("user_context", userContext);

            String responseBody = getWebClient()
                    .post()
                    .uri("/api/v1/agent/analyze")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(request)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            String content = responseBody != null ? responseBody : "";
            if (userId != null) saveMessage(userId, "assistant", "【医疗报告分析】\n" + content);

            Map<String, String> resp = new HashMap<>();
            resp.put("content", content);
            return resp;
        } catch (Exception e) {
            Map<String, String> err = new HashMap<>();
            err.put("content", "服务调用出错: " + e.getMessage());
            return err;
        }
    }

    /**
     * 接收前端 Authorization header，解析后调用 analyzeReport
     */
    public Map<String, String> analyzeWithAuth(String authHeader, String reportContent) {
        try {
            UUID userId = null;
            if (authHeader != null && authHeader.startsWith("Bearer ")) {
                String token = authHeader.substring(7);
                if (jwtTokenProvider.validateToken(token)) {
                    userId = jwtTokenProvider.getUserIdFromToken(token);
                }
            }
            return analyzeReport(userId, reportContent);
        } catch (Exception e) {
            Map<String, String> err = new HashMap<>();
            err.put("content", "认证或分析处理出错: " + e.getMessage());
            return err;
        }
    }

    /**
     * 获取某用户的全部会话历史（按时间升序）
     */
    // 从 repository 读取用户的全部会话消息，按创建时间升序返回
    public List<SessionMessage> getHistory(UUID userId) {
        return sessionMessageRepository.findByUserIdOrderByCreatedAtAsc(userId);
    }

    /** 清空某用户的会话历史（用于登出） */
    public void clearHistory(UUID userId) {
        if (userId == null) return;
        sessionMessageRepository.deleteByUserId(userId);
    }


}
