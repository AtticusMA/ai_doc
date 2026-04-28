# CLAUDE.md — hosp-eap-web-manage

本文件为 manage 模块的补充说明。全局规范见根目录 `CLAUDE.md`。

## 模块定位

管理后台 API 服务，提供企业管理、卡券开卡、服务配置、医生排班、运营报表等管理功能。

- **应用名：** `hxq-eap-web-manage`
- **默认端口：** 8890
- **启动类：** `HospEapWebManageApplication`
- **启用特性：** `@EnableCaching`, `@EnableAsync`, `@EnableSwagger2`, `@ServletComponentScan`
- **数据源：** 排除自动配置，通过 Nacos 动态加载

## 子模块：hosp-eap-manage-contract

Dubbo RPC 接口契约模块，存放跨模块调用的接口定义和传输对象：

```
com.hxq.eap.contract
├── rpc/    # Dubbo 接口（RpcEnterpriseService, RpcRefundService）
├── req/    # 请求 DTO（CopyBatchParam, OrderRefundParam, CopyEnterpriseParam）
└── res/    # 响应 VO（CopyBatchVo, OrderRefundVo, CopyEnterpriseVo）
```

**RPC 实现类位置：** `com.hxq.eap.manage.rpc.impl`（本模块内）

## 包结构

```
com.hxq.eap.manage
├── controller/         # REST 接口（按业务功能命名，如 EapCardController）
├── domain/
│   ├── condition/      # 查询条件（分 eap/ 和 hxq/ 子目录）
│   ├── dto/            # 请求 DTO（分 eap/, api/, req/ 等子目录）
│   └── vo/             # 响应 VO
├── service/
│   ├── eap/            # hxq_eap 库的业务 Service（含 impl/）
│   └── hxq/            # hxq_common 库的业务 Service（含 impl/）
├── rpc/impl/           # Dubbo RPC 接口实现（@DubboService 暴露）
├── component/          # 自定义组件（Excel 处理器等）
├── config/             # Spring 配置、AOP 切面
├── excelmodel/         # EasyPOI Excel 模型定义
├── thread/             # 线程池、异步任务工具
└── utils/              # 工具类
```

## 操作日志 AOP

Controller 方法通过 `@ApiLogInfo` 注解自动记录操作日志：
```java
@ApiLogInfo(menuName = "卡券管理-开卡管理", operateName = "新增或编辑批次", operateType = 4)
```
- 日志存入 `eap_manage_operate_log` 表（异步插入）
- 自动记录：操作详情、用户/角色/部门、请求参数、执行耗时、IP 地址

## 用户会话

```java
EapManageUser manageUser = UserLoginDetails.getUserSessionDate(request);
// 可获取: userId, loginName, name, entId, entName, deptId, deptName, roleId
```

**注意：** Dubbo RPC 场景下无 HttpServletRequest，需使用 `copyBatch(param, manageUser)` 重载方法直接传入用户对象。

## 日期格式

Jackson 全局配置：`yyyy-MM-dd HH:mm:ss`，时区 `Asia/Shanghai`

## API 文档

- Knife4j UI: `http://localhost:8890/doc.html`
- Swagger UI: `http://localhost:8890/swagger-ui/index.html`

## 部署

- Docker：`Dockerfile` + `docker-entrypoint.sh`，暴露端口 8080
- CI/CD：Jenkins Pipeline（`Jenkinsfile`）
