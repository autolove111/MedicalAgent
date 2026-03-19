package com.medlab.controller;

import com.medlab.service.SessionChatService;
import com.medlab.service.StorageService;
import com.medlab.service.UserMedicalService;
import com.medlab.service.MedicalFacadeService;
import com.medlab.util.JwtTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
@CrossOrigin(origins = "*")
public class AgentController {

    private static final Logger logger = LoggerFactory.getLogger(AgentController.class);

    @Value("${langchain.service.url:http://localhost:8000}")
    private String langchainServiceUrl;

    @Autowired
    private WebClient.Builder webClientBuilder;

    @Autowired
    private UserMedicalService userMedicalService;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Autowired
    private SessionChatService sessionChatService;

    @Autowired
    private MedicalFacadeService medicalFacadeService;

    private WebClient getWebClient() {
        return webClientBuilder.baseUrl(langchainServiceUrl).build();
    }

    /**
     * 流式聊天接口：负责提取用户ID并转发给 Python Agent
     */
    @PostMapping(value = "/agent/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamChat(@RequestParam String userQuery,
                                 @RequestHeader(value = "Authorization", required = false) String authHeader) {
        SseEmitter emitter = new SseEmitter(0L);
        
        // 1. 尝试从 Token 中提取 userId
        String currentUserId = null;
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            try {
                String token = authHeader.substring(7);
                if (jwtTokenProvider.validateToken(token)) {
                    currentUserId = jwtTokenProvider.getUserIdFromToken(token).toString();
                    logger.info("成功识别登录用户 ID: {}", currentUserId);
                }
            } catch (Exception e) {
                logger.warn("Token 解析失败，将以匿名模式继续: {}", e.getMessage());
            }
        }

        // 2. 【核心修复】定义 final 变量供 Lambda 使用
        final String finalUserId = currentUserId;

        try {
            WebClient client = getWebClient();

            // 3. 构建请求并转发给 Python 侧
            client.post()
                    .uri(uriBuilder -> {
                        var builder = uriBuilder.path("/api/v1/agent/chat/stream")
                                .queryParam("userQuery", userQuery);
                        // 如果有用户ID，则挂载到 URL 参数中
                        if (finalUserId != null) {
                            builder.queryParam("userId", finalUserId);
                        }
                        return builder.build();
                    })
                    .header("Authorization", authHeader != null ? authHeader : "")
                    .accept(MediaType.TEXT_EVENT_STREAM)
                    .retrieve()
                    .bodyToFlux(String.class)
                    .subscribe(
                            chunk -> {
                                try {
                                    emitter.send(chunk);
                                } catch (Exception e) {
                                    emitter.completeWithError(e);
                                }
                            },
                            err -> {
                                logger.error("转发 Python 流时发生错误: ", err);
                                emitter.completeWithError(err);
                            },
                            () -> emitter.complete()
                    );
        } catch (Exception e) {
            logger.error("初始化 WebClient 请求失败: ", e);
            emitter.completeWithError(e);
        }
        
        return emitter;
    }

    /**
     * 内部调用接口：供 Python Agent 以后台方式查询病历
     */
    @GetMapping("/internal/user/medical-history")
    public ResponseEntity<Map<String, String>> getMedicalHistoryById(@RequestParam("userId") String userId) {
        Map<String, String> resp = new HashMap<>();
        try {
            UUID uid = UUID.fromString(userId);
            String history = userMedicalService.getMedicalHistory(uid);
            String drug = userMedicalService.getDrugAllergy(uid);

            resp.put("status", "success");
            resp.put("medicalHistory", history != null ? history : "暂无病历记录");
            resp.put("drugAllergy", drug != null ? drug : "无已知过敏史");
            return ResponseEntity.ok(resp);
        } catch (Exception e) {
            resp.put("status", "error");
            resp.put("message", "无效的 UUID 格式");
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(resp);
        }
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        Map<String, String> response = new HashMap<>();
        response.put("status", "UP");
        response.put("message", "MedLabAgent Backend is running");
        return ResponseEntity.ok(response);
    }

    // 其他业务接口保持转发逻辑即可...
    @PostMapping("/agent/analyze")
    public ResponseEntity<Map<String, String>> analyzeReport(@RequestParam String reportContent,
                                                             @RequestHeader(value = "Authorization", required = false) String authHeader) {
        return ResponseEntity.ok(sessionChatService.analyzeWithAuth(authHeader, reportContent));
    }

    @PostMapping("/agent/upload-report")
    public ResponseEntity<Map<String, String>> uploadReport(
            @RequestParam("file") MultipartFile file,
            @RequestHeader(value = "Authorization", required = false) String authHeader) {
        return ResponseEntity.ok(medicalFacadeService.handleUploadAndAppend(file, authHeader));
    }
}