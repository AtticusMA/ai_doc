# Dubbo RPC 跨模块调用开发指南

## 1. 概述

项目使用 Dubbo 3.1.8 + Nacos 实现跨模块 RPC 调用。接口契约定义在 `hosp-eap-manage-contract` 子模块中，服务提供者在 `hosp-eap-web-manage` 中实现。

**序列化协议：** Kryo（`dubbo.protocol.serialization=kryo`）
**注意：** 所有 RPC 传输对象必须实现 `java.io.Serializable`

## 2. 模块结构

```
hosp-eap-web-manage/
├── hosp-eap-manage-contract/              # 接口契约 jar（被消费端依赖）
│   └── src/main/java/com/hxq/eap/contract/
│       ├── rpc/                           # 接口定义
│       │   ├── RpcEnterpriseService.java
│       │   └── RpcRefundService.java
│       ├── req/                           # 请求 DTO
│       │   ├── CopyBatchParam.java
│       │   ├── CopyEnterpriseParam.java
│       │   └── OrderRefundParam.java
│       └── res/                           # 响应 VO
│           ├── CopyBatchVo.java
│           ├── CopyEnterpriseVo.java
│           └── OrderRefundVo.java
└── src/main/java/com/hxq/eap/manage/rpc/
    └── impl/                              # 接口实现（@DubboService 暴露）
        ├── RpcEnterpriseServiceImpl.java
        └── RpcRefundServiceImpl.java
```

## 3. 新增 RPC 接口的完整步骤

### Step 1: 在 contract 模块定义接口和 DTO

```java
// contract/rpc/RpcXxxService.java
package com.hxq.eap.contract.rpc;

import com.hxq.eap.common.web.PlainResult;
import com.hxq.eap.contract.req.XxxParam;
import com.hxq.eap.contract.res.XxxVo;

public interface RpcXxxService {
    PlainResult<XxxVo> doSomething(XxxParam param);
}
```

```java
// contract/req/XxxParam.java — 必须实现 Serializable
package com.hxq.eap.contract.req;

import java.io.Serializable;

public class XxxParam implements Serializable {
    private static final long serialVersionUID = 1L;
    // 字段 + getter/setter（contract 模块无 Lombok，必须手写）
}
```

```java
// contract/res/XxxVo.java — 必须实现 Serializable
package com.hxq.eap.contract.res;

import java.io.Serializable;

public class XxxVo implements Serializable {
    private static final long serialVersionUID = 1L;
    // 字段 + getter/setter
}
```

### Step 2: 在 manage 模块实现接口

```java
// manage/rpc/impl/RpcXxxServiceImpl.java
package com.hxq.eap.manage.rpc.impl;

import com.hxq.eap.contract.rpc.RpcXxxService;
import org.apache.dubbo.config.annotation.DubboService;

@Slf4j
@DubboService
public class RpcXxxServiceImpl implements RpcXxxService {

    @Autowired
    private XxxService xxxService;

    @Override
    public PlainResult<XxxVo> doSomething(XxxParam param) {
        // 注意：RPC 场景无 HttpServletRequest
        // 如需用户信息，从参数传入或构造系统用户
        try {
            // 转换 contract DTO → manage 内部 DTO
            // 调用内部 Service
            return PlainResult.success(result);
        } catch (Exception e) {
            log.error("RPC 调用异常", e);
            return PlainResult.error(5001, "操作失败: " + e.getMessage());
        }
    }
}
```

### Step 3: 在消费端依赖 contract 并调用

**pom.xml 添加依赖：**
```xml
<dependency>
    <groupId>com.hxq.eap</groupId>
    <artifactId>hosp-eap-manage-contract</artifactId>
    <version>${contract.version}</version>
</dependency>
```

**消费端调用：**
```java
@DubboReference
private RpcXxxService rpcXxxService;

public void callRemote() {
    XxxParam param = new XxxParam();
    param.setXxx(...);
    PlainResult<XxxVo> result = rpcXxxService.doSomething(param);
    if (result.getCode() == 2000) {
        XxxVo data = result.getResult();
    }
}
```

### Step 4: 部署 contract 到 Maven 仓库

```bash
cd hosp-eap-web-manage/hosp-eap-manage-contract
mvn clean deploy
```

## 4. 关键约束与注意事项

### 序列化
- 所有 RPC DTO 必须 `implements Serializable` + 声明 `serialVersionUID`
- `PlainResult` 已实现 Serializable（之前修复过）
- **contract 模块不使用 Lombok**，必须手写 getter/setter

### Nacos 服务发现
- 消费端 `dubbo.cloud.subscribed-services` 必须填写**应用名**（如 `hosp-eap-web-manage`），不是模块名
- 消费端和提供端必须在**同一 Nacos namespace** 下
- 每个环境的 `bootstrap-{profile}.yml` 都必须配置 `dubbo.registry.address` 和 `dubbo.registry.parameters.namespace`

### Dubbo 配置
- 必须在 `bootstrap-{profile}.yml` 中显式配置 `dubbo.application.name`
- 端口冲突时配置 `dubbo.protocol.port`（如 `-1` 自动分配）
- `dubbo.scan.base-packages` 必须覆盖 RPC 实现类所在包

### HttpServletRequest 问题
- Dubbo RPC 调用中**无法获取 HttpServletRequest**
- 解决方案：Service 方法提供无 request 的重载版本，直接传入用户对象
- 示例：`copyBatch(param)` → `copyBatch(param, manageUser)`

### contract 模块构建
- `pom.xml` 中必须配置 `<relativePath>../../pom.xml</relativePath>`
- 必须显式禁用 `spring-boot-maven-plugin` 的 repackage（避免生成 fat jar）
- 根 `pom.xml` 的 `<modules>` 中 contract 必须在 manage 之前声明
