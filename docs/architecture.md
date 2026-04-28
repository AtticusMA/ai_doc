# System Architecture

## 1. 技术栈

| 层面 | 技术 | 版本 |
|------|------|------|
| 语言 | Java | 1.8 |
| 框架 | Spring Boot | 2.3.12.RELEASE |
| 微服务 | Spring Cloud Alibaba | 2.2.7.RELEASE |
| RPC | Apache Dubbo | 3.1.8（Kryo 序列化） |
| 注册/配置中心 | Nacos | 2.0.4 |
| 数据库 | MySQL | 8.0（Druid 1.2.8 连接池） |
| ORM | MyBatis | 2.2.0（Spring Boot Starter） |
| 缓存 | Redis | Redisson 3.16.3 |
| API 文档 | Knife4j | 3.0.3 |
| 日志 | Log4j2 | - |
| 工具 | Hutool 5.7.15, Fastjson 1.2.83, EasyPOI 3.2.0 | - |

## 2. 模块职责

| 模块 | 应用名 | 默认端口 | 职责 |
|------|--------|---------|------|
| hosp-eap-web-manage | hxq-eap-system-biz | 8890 | 管理后台（企业/卡券/排班/服务配置） |
| hosp-eap-web-user | hxq-eap-user | - | 用户端（咨询预约/绑卡/订单） |
| hosp-eap-web-third | hxq-eap-third | - | 第三方对接（钉钉/飞书/海港人寿） |
| hosp-eap-web-consultant | - | - | 医生/咨询师端 |
| hosp-eap-job-executor | - | - | 定时任务执行器 |
| hosp-eap-common | - | - | 公共组件（不可独立运行） |
| hosp-eap-infra | - | - | 数据访问层（不可独立运行） |
| hosp-eap-manage-contract | - | - | Dubbo RPC 接口契约（jar 包） |

## 3. 分层架构

```
HTTP Request
    ↓
Controller（参数校验、DTO 转换、@ApiLogInfo 日志）
    ↓
Service（业务逻辑、事务管理）
    ↓
├── Mapper（MyBatis 数据访问）→ MySQL
├── Redis（缓存/分布式锁）
└── Dubbo RPC（跨模块调用）→ 其他模块的 Service
```

## 4. 跨模块 RPC 拓扑

```
                    ┌──────────────────────┐
                    │  manage-contract     │
                    │  (接口 + DTO 定义)    │
                    └──────┬───────────────┘
                           │ 被依赖
            ┌──────────────┼──────────────┐
            ↓              ↓              ↓
    ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │ web-third    │ │ web-user │ │ job-executor │
    │ (@DubboRef)  │ │          │ │              │
    └──────┬───────┘ └──────────┘ └──────────────┘
           │ RPC 调用
           ↓
    ┌──────────────┐
    │ web-manage   │
    │ (@DubboSvc)  │
    │ rpc/impl/    │
    └──────────────┘
```

**当前已暴露的 RPC 服务：**
- `RpcEnterpriseService` — 企业/批次操作（copyBatch、copyEnterprise）
- `RpcRefundService` — 统一退款

详细开发指南见 `docs/dubbo-rpc.md`。

## 5. Nacos 环境隔离

不同 profile 对应不同 Nacos namespace，确保环境间服务完全隔离：

| Profile | Nacos Namespace |
|---------|----------------|
| dev | `7ebedcc3-...` |
| test | `bd569d7c-...` |
| local | `local` 或自定义 |

**关键约束：** 服务提供者和消费者必须在同一 namespace 下才能发现彼此。

## 6. 配置管理

- 启动配置：`bootstrap-{profile}.yml`（指定 Nacos 地址、namespace、data-id）
- 运行时配置：全部从 Nacos Config Server 加载
- 配置命名规则：`{应用名}-{profile}.yaml`，分组 `{PROFILE}_GROUP`
