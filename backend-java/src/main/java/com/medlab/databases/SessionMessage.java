package com.medlab.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 会话临时消息实体
 * 存储用户在线期间的多轮对话历史，用于给AI提供上下文。
 * 用户登出时按 userId 清空。
 */
@Entity
@Table(name = "session_messages")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SessionMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    @Column(columnDefinition = "UUID")
    private UUID id;

    /** 关联的用户ID，用于区分不同用户的会话 */
    @Column(nullable = false, columnDefinition = "UUID")
    private UUID userId;

    /** 消息角色：user 或 assistant */
    @Column(nullable = false, length = 20)
    private String role;

    /** 消息内容 */
    @Column(columnDefinition = "TEXT")
    private String content;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}
