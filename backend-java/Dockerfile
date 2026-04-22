# --- 第一阶段：构建阶段 ---
FROM maven:3.9-eclipse-temurin-17 AS builder

# 设置字符集，防止构建过程中的中文乱码
ENV LANG C.UTF-8

WORKDIR /app

# 利用 Docker 层缓存：先只复制 pom.xml
COPY pom.xml .
RUN mvn dependency:go-offline -B

# 再复制源码并打包
COPY src ./src
RUN mvn clean package -DskipTests -q

# --- 第二阶段：运行阶段 ---
# 使用 jre-alpine 版本，镜像体积更小（约 100MB+）
FROM eclipse-temurin:17-jre-alpine

# 设置运行时字符集环境（非常重要！）
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

WORKDIR /app

# 从构建阶段拷贝 JAR 包
# 建议指定具体名称，防止 target 下有多个 jar 导致拷贝失败
COPY --from=builder /app/target/*.jar app.jar

# 创建必要目录
RUN mkdir -p /app/uploads /app/logs

# 健康检查：增加起始等待时间 (start-period)
# 防止应用还没启动完就被 Docker 误判为不健康
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/api/v1/file/health || exit 1

# 启动参数优化
# 添加 -Dfile.encoding=UTF-8 确保 Java 内部处理字符串也是 UTF-8
ENTRYPOINT ["java", "-Dfile.encoding=UTF-8", "-Dlog4j.configurationFile=/app/logs/log4j2.xml", "-jar", "app.jar"]

EXPOSE 8080