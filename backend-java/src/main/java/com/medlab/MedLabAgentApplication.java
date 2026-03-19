package com.medlab;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * MedLabAgent 系统主应用启动类
 * 这是整个医疗实验室AI智能体系统的入口点
 * 
 * 功能职责：
 * 1. 启动Spring Boot应用框架cd backend-java
 * 2. 配置自动扫描基础包下的所有Spring组件
 * 3. 初始化所有Bean和依赖注入
 */
@SpringBootApplication
public class MedLabAgentApplication {

    public static void main(String[] args) {
        SpringApplication.run(MedLabAgentApplication.class, args);
        System.out.println("\n========================================");
        System.out.println("MedLabAgent System Started Successfully");
        System.out.println("========================================\n");
    }
}
