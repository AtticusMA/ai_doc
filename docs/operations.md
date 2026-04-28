# 运维与部署

## 1. 容器化部署

### Docker 镜像
- **基础镜像**：`reg.haoxinqing.cn/devops/baseimage/java:skywalking-v202207291539`（内置 JDK + SkyWalking Agent）
- **时区**：`Asia/Shanghai`（Dockerfile 中硬编码）
- **语言**：`zh_CN.UTF-8`
- **端口**：8080
- **日志卷**：`/opt/logs`（Volume 挂载）
- **启动入口**：`/opt/web/docker-entrypoint.sh`

### Dockerfile 结构（各模块通用）
```dockerfile
FROM reg.haoxinqing.cn/devops/baseimage/java:skywalking-v202207291539
ENV APPNAME=hosp-eap-web-xxx
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
COPY target/*.jar /opt/web/${APPNAME}/app.jar
COPY docker-entrypoint.sh /opt/web/docker-entrypoint.sh
EXPOSE 8080
VOLUME ["/opt/logs"]
CMD ["/opt/web/docker-entrypoint.sh"]
```

## 2. CI/CD 流水线

- **工具**：Jenkins
- **配置文件**：各模块根目录 `Jenkinsfile`
- **构建方式**：共享库 `@Library('jenkinsLibrary@master')` + `pipelineRoute.build("java")`
- **流程**：Checkout → Maven Build → Docker Build → Docker Push → Deploy

## 3. 监控与日志

### APM 监控
- **SkyWalking**：通过基础镜像内的 Java Agent 自动接入，支持分布式链路追踪

### 异常告警
- **钉钉推送**：AOP 捕获异常后推送至钉钉群（manage 模块 `DingDingAspect`）

### 日志
- **框架**：Log4j2
- **存储路径**：`/opt/logs`（容器内挂载卷）

## 4. 环境隔离

通过 Nacos namespace 隔离不同环境配置：

| 环境 | Profile | 说明 |
|------|---------|------|
| 开发 | `dev` | `bootstrap-dev.yml` |
| 测试 | `test` | `bootstrap-test.yml` |
| 生产 | `prod` | `bootstrap-prod.yml` |

每个 profile 文件中配置对应的 Nacos namespace ID、数据库连接、Redis 地址等。
