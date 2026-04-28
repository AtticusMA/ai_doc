# CLAUDE.md

本文件为 AI 编程助手提供项目全局指导。

## 项目概述

hxq-eap 是好心情医疗 EAP（员工心理援助）系统，基于 Spring Boot 微服务架构，提供心理咨询预约、企业管理、卡券服务等功能。

**核心技术栈：**
- Java 1.8 / Spring Boot 2.3.12.RELEASE / Spring Cloud Alibaba 2.2.7.RELEASE
- Dubbo 3.1.8（Kryo 序列化）+ Nacos 注册中心与配置中心
- MyBatis + MyBatis Generator / MySQL 8.0 / Redis (Redisson)
- Knife4j/Swagger API 文档 / Log4j2 日志

## 模块结构

```
hxq-eap (根 pom)
├── hosp-eap-common              # 公共工具：注解、枚举、加密、校验、Web 组件
├── hosp-eap-infra               # 基础设施：MyBatis Mapper + POJO（双库：eap/hxq）
├── hosp-eap-web-manage          # 管理后台服务（企业管理、卡券、排班、服务配置）
│   └── hosp-eap-manage-contract # ★ Dubbo RPC 接口契约（接口+DTO，供其他模块依赖）
├── hosp-eap-web-user            # 用户端服务（咨询预约、绑卡、订单）
├── hosp-eap-web-third           # 第三方对接（钉钉、飞书、海港人寿）
├── hosp-eap-web-consultant      # 医生/咨询师端服务
├── hosp-eap-job-executor        # XXL-Job 任务执行器
└── hosp-eap-job-admin           # XXL-Job 任务管理后台
```

**关键说明：**
- `hosp-eap-manage-contract` 是 manage 的子模块，存放 Dubbo RPC 接口定义和传输 DTO，其他模块通过依赖此模块实现跨模块 RPC 调用
- `hosp-eap-infra` 的 mapper/pojo 按数据库分包：`mapper.eap` 对应 `hxq_eap` 库，`mapper.hxq` 对应 `hxq_common` 库

## 构建命令

```bash
# 全量构建
mvn clean package

# 单模块构建
cd hosp-eap-web-manage && mvn clean package

# MyBatis Generator 生成 Mapper/POJO
cd hosp-eap-infra && mvn mybatis-generator:generate
# 配置文件：hosp-eap-infra/src/main/resources/generatorConfig.xml

# 部署 contract 到 Maven 仓库（其他模块依赖）
cd hosp-eap-web-manage/hosp-eap-manage-contract && mvn clean deploy
```

**环境 Profile：** dev, test, sandbox, online, local
- 配置文件：各模块 `src/main/resources/bootstrap-{profile}.yml`
- 运行时配置：从 Nacos Config Server 加载

## 编码规范（必须严格遵守）

**响应码：**
- `2000` = 成功，`4xxx` = 参数/业务错误，`5xxx` = 程序异常

**返回值：** 统一使用 `PlainResult` 包装
```java
return PlainResult.success(data);
return PlainResult.error(4001, "参数错误");
```

**日期类型：** 项目统一使用 `java.util.Date`，**禁止**使用 `java.time.LocalDateTime`

**Service 事务：** `get*`/`select*` 方法只读，其余方法默认事务

**Controller 规范：**
- `@RestController` + `@RequestMapping`
- 每个接口必须标注 `@ApiOperation` + `@ApiImplicitParam`
- 入参使用 `*Param` DTO + `@RequestBody`，**禁止** `Map<String, Object>` 或 `JSONObject`

**异常处理：** 业务异常抛 `BizException`，由全局 `@ControllerAdvice` 统一捕获

**MyBatis 使用约束：**
- 查询列用 `<include refid="Base_Column_List"/>`，**禁止** `SELECT *`
- 动态条件用 `#{param}` 参数化查询，`${}`仅用于列名/排序等非用户输入
- 新增记录后需要 ID 时使用 `insertSelective`（支持 `<selectKey>` 返回自增 ID）
- `BeanUtils.copyProperties` 复制后**必须清空主键**（`setId(null)`）再 insert
- 分页**必须**用 `PageHelper.startPage(pageNum, pageSize)` 且紧跟查询语句

## Knowledge Base Routing

在执行以下任务时，**必须**先读取对应文档：

| 任务场景 | 必读文档 |
|---------|---------|
| 创建/修改数据库表、SQL、MyBatis XML | `docs/database.md` |
| 新增 Controller/Service 接口 | `docs/architecture.md` + `docs/development.md` |
| 新增或修改 Dubbo RPC 跨模块接口 | `docs/dubbo-rpc.md` |
| 编写测试用例 | `docs/testing.md` |
| 修改批次复制(copyBatch)相关逻辑 | 先查看 `EapEnterpriseCardServiceImpl.copyBatch` 完整方法 |
| 修改主页配置(EapHomePage/EapHomeItem) | 先查看 `copyHomePageConfig` 方法了解表关系 |
| 代码重构/性能优化/技术债务治理 | `docs/optimization.md` |

## 行为准则

1. **先思考**：陈述假设、提出疑问、展示替代方案，再动手编码
2. **最小改动**：只修改必要代码，匹配现有风格，不重构无关代码
3. **目标驱动**：定义可验证的成功标准，变更前后都要测试
4. **每行代码可追溯**：不添加需求外的功能、不过度抽象、不添加未请求的灵活性
5. **多步任务**：先陈述计划和验证检查点，再逐步执行
