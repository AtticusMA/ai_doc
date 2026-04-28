# 项目优化建议清单

> 基于代码实际扫描结果，按优先级排列。每项均附带真实代码位置和修复方案。

---

## 一、数据库与 SQL 查询

### 1.1 N+1 查询问题

**严重程度：高** | **影响：每次列表查询产生额外 N 次数据库访问**

| 位置 | 代码 | 说明 |
|------|------|------|
| `manage/EapEnterpriseCardServiceImpl.java` L1614-1616 | `for (EnterpriseCardVO vo : list) { if(isEmpty(vo.getSingleAmount())) { vo.setSingleAmount(eapEnterpriseCardMapper.selectByPrimaryKey(vo.getBatchId()).getSingleAmount()); } }` | 批次列表分页查询后，循环内逐条查 `eap_enterprise_card` 表补 `singleAmount` |
| `user/EapEnterpriseCardServiceImpl.java` L157-161 | 同上模式 | user 模块同样存在 |
| `manage/ThirdOrderTaskServiceImpl.java` L247 | `eapCardMapper.selectByPrimaryKey(enterpriseCard.getCardId())` | 循环内查卡类型和性质 |
| `user/ShoppingCartServiceImpl.java` L671-673 | 连续 3 次 `mallRegionMapper.selectByPrimaryKey` 查省/市/区名 | 每次下单都产生 3 次额外查询 |

**修复方案：**
- **方案 A（推荐）**：修改 SQL/XML，在主查询中 JOIN 或子查询一次性带出所需字段
- **方案 B**：查询后收集所有需要补充的 ID，批量 `selectByExample` + `IN` 查询，再 Map 回填

```java
// 修复示例：批量查询替代循环内单条查询
List<Long> batchIds = list.stream()
    .filter(v -> ObjectUtils.isEmpty(v.getSingleAmount()))
    .map(EnterpriseCardVO::getBatchId)
    .distinct()
    .collect(Collectors.toList());
if (!CollectionUtils.isEmpty(batchIds)) {
    EapEnterpriseCardExample ex = new EapEnterpriseCardExample();
    ex.createCriteria().andBatchIdIn(batchIds);
    Map<Long, BigDecimal> amountMap = eapEnterpriseCardMapper.selectByExample(ex)
        .stream().collect(Collectors.toMap(
            EapEnterpriseCard::getBatchId, 
            EapEnterpriseCard::getSingleAmount, (a, b) -> a));
    list.stream()
        .filter(v -> ObjectUtils.isEmpty(v.getSingleAmount()))
        .forEach(v -> v.setSingleAmount(amountMap.get(v.getBatchId())));
}
```

### 1.2 内存分页（假分页）

**严重程度：高** | **影响：全表加载到内存后 Java 端截取，数据量大时 OOM**

项目中大量使用 `CollectionUtil.doPage()` 进行内存分页，涉及 **25+ 处**，典型位置：

| 位置 | 说明 |
|------|------|
| `EapManageServiceOrderServiceImpl.java` L499/545/626/765/795/825/906 | 订单列表 7 处内存分页 |
| `EapServiceCustomerServiceImpl.java` L211/308 | 客户列表 |
| `EapServiceDoctorServiceImpl.java` L226 | 医生列表 |
| `WorkbenchServiceImpl.java` L434 | 风险备注列表 |
| `EapManageStatisticServiceImpl.java` L232/992 | 统计数据 |
| `EapDoctorSchedulingServiceImpl.java` L202 | 排班列表 |
| `EapServiceArticleServiceImpl.java` L123 | 文章列表 |
| `EapServiceInstitutionServiceImpl.java` L121/413 | 机构医生列表 |

**修复方案：**
- 将 `CollectionUtil.doPage()` 替换为 `PageHelper.startPage(pageNum, pageSize)` + 数据库端 `LIMIT` 分页
- 对于必须内存过滤的场景，先在 SQL 端尽量过滤，再用 PageHelper

### 1.3 SQL 注入风险 — `${}` 拼接用户输入

**严重程度：高** | **影响：`${}` 直接拼入 SQL，存在注入攻击风险**

在 extend Mapper XML 中发现 **25+ 处** `like '%${xxx}%'` 拼接：

| 文件 | 涉及字段 |
|------|---------|
| `EapCardsExtMapper.xml` L70/86/93/133/192/202/209/246/257/263/269/278 | `batchName`, `entName`, `cardName`, `customerName` |
| `EapEnterpriseCardExtMapper.xml` L71/83/92 | `batchName`, `enterpriseName`, `cardName` |
| `EapBannerExtMapper.xml` L36/43 | `batchName`, `entName` |
| `EapTrainExtMapper.xml` L51/73/86/137 | `entName`, `userName`, `contentName` |
| `ArticleMapper.xml` L1431/1455 | `title` |
| `DoctorMapper.xml` L2358 | `keyword`（同时 name 和 id） |

**修复方案：** 将 `${}` 替换为 `#{}` + `CONCAT`：
```xml
<!-- 修改前（存在注入风险）-->
and batch_name like '%${batchName}%'

<!-- 修改后（安全）-->
and batch_name like CONCAT('%', #{batchName}, '%')
```

### 1.4 无分页的全表查询

**严重程度：中** | **影响：数据量增长后查询变慢、内存溢出**

以下场景 `selectByExample` 未加 `LIMIT` 或 `PageHelper`，返回全量数据：
- `WorkbenchServiceImpl.java` L430：查询全部 `CrisisInterventionDetail` 后内存分页
- `IvrEapServiceImpl.java` L883：查询全部匹配订单只取 `list.get(0)`，应加 `LIMIT 1`
- 各种 `selectByExample` 未设置 `pageSize`/`startPos` 的场景

---

## 二、时间类型不统一

### 2.1 `java.util.Date` 与 `java.time.LocalDateTime` 混用

**严重程度：中** | **影响：类型不兼容、序列化问题、代码混乱**

项目主体使用 `java.util.Date`，但以下位置使用了 `LocalDateTime`：

| 文件 | 说明 |
|------|------|
| `GoodsDrugCourier.java` | 实体类 4 个时间字段全部用 `LocalDateTime`（`courierTime`, `deliverOperatorTime`, `receiptOperatorTime`, `createTime`） |
| `LogAspect.java` L65 | 日志切面 `LocalDateTime.now()` |
| `EnterpriseMonthlyStatsJobServiceImpl.java` L76 | `LocalDateTime.of(...)` 转 `Date` |
| `InitServiceDoctorOrderServiceImpl.java` L564 | `LocalDateTime.now().plusHours(48)` 转 `Date` |
| `IvrEapServiceImpl.java` L201/L1042 | 多处 `LocalDateTime` 与 `Date` 互转 |
| `OrderSendFiveSmsServiceImpl.java` | `LocalDateTime` 使用 |

**修复方案：**
- **统一为 `java.util.Date`**（与项目整体保持一致）
- `GoodsDrugCourier.java` 的 `LocalDateTime` 字段改为 `Date`，同步修改对应 Mapper XML
- 工具类中的 `LocalDateTime` 用法改为 `DateUtil` 中已有的 `Date` 工具方法
- 如需日期计算（加减时间），使用 `Calendar` 或 `DateUtil.addXxx()` 方法

---

## 三、代码质量与精简

### 3.1 上帝类 — Service 文件过大

**严重程度：高** | **影响：可读性差、维护困难、合并冲突频繁**

超过 800 行的 ServiceImpl 文件（共 39 个）：

| 文件 | 行数 | 模块 |
|------|------|------|
| `EapManageServiceOrderServiceImpl.java` | **7464** | manage |
| `ServiceOrderServiceImpl.java` | **6105** | user |
| `DoctorServiceImpl.java` | **4311** | user |
| `UserCenterServiceImpl.java` | **3275** | user |
| `AdvisoryInquiryOrderServiceImpl.java` | **3175** | user |
| `EapEnterpriseCardServiceImpl.java` | **2967** | manage |
| `EapCreateGenerationOrderServiceImpl.java` | **2902** | manage |
| `EapHomePageServiceImpl.java` | **2618** | user |
| `EntPlaceConsulServiceImpl.java` | **2376** | user |
| `UserServiceImpl.java` | **2350** | user |
| `RegistrationOrderServiceImpl.java` | **2272** | user |
| `PayServiceImpl.java` | **2209** | user |
| `EapCreatOrderServiceImpl.java` | **1965** | manage |
| `ContentServiceServiceImpl.java` | **1774** | user |
| `EapRefundServiceImpl.java` | **1772** | manage |
| `PatientDoctorCommentServiceImpl.java` | **1739** | user |
| `ShoppingCartServiceImpl.java` | **1698** | user |
| `UserServiceImpl.java` | **1633** | manage |
| `EapExcelServiceImpl.java` | **1612** | manage |

**修复方案：** 按业务子领域拆分，例如：
```
EapManageServiceOrderServiceImpl（7464行）拆分为：
├── ServiceOrderQueryService      — 查询/列表
├── ServiceOrderCreateService     — 创建订单
├── ServiceOrderRefundService     — 退款逻辑
├── ServiceOrderExportService     — Excel 导出
└── ServiceOrderStatusService     — 状态变更
```

### 3.2 异常处理不规范 — `e.printStackTrace()`

**严重程度：中** | **影响：异常信息打印到 stdout 而非日志框架，生产环境丢失堆栈**

发现 **25+ 处** `e.printStackTrace()`，集中在：

| 文件 | 数量 |
|------|------|
| `DateUtil.java` | 6 处 |
| `UcClient.java` | 4 处 |
| `GetDataTest.java` | 5 处 |
| `HttpClientUtils.java` | 2 处 |
| `AESSaltUtil.java`、`AESUtil.java`、`RSAUtil.java` | 各 1 处 |
| `UserLoginInterceptor.java` | 1 处 |
| `PayServiceImpl.java` L1445 | Service 层也有 |

**修复方案：** 全局替换为 `log.error("描述", e)`：
```java
// 修改前
e.printStackTrace();

// 修改后
log.error("处理异常", e);
```

### 3.3 重复代码模式

**严重程度：中** | **影响：修改一处需改多处，容易遗漏**

**（1）用户初始化逻辑重复**

| 文件 | 方法 |
|------|------|
| `EapCreatOrderServiceImpl.java` L1698-1742 | `initUser` 流程：查 User → 不存在则创建 → 查 Patient → 查 UserThird |
| `EapServiceCustomerServiceImpl.java` L1447-1463 | 类似的 `initUser` 流程，但查询方式不同（unionid vs mobile） |

应抽取为公共 `UserInitService`。

**（2）分页结果封装重复**

至少 20+ 处重复以下模板代码：
```java
int total = voList.size();
int totalPage = total / pageSize + (total % pageSize == 0 ? 0 : 1);
PlainResultPage<XXX> plainResultPage = new PlainResultPage<>();
plainResultPage.setPageNum(pageNum);
plainResultPage.setPageSize(pageSize);
plainResultPage.setTotal((long) total);
plainResultPage.setTotalPage(totalPage);
plainResultPage.setList(pageList);
```

应封装为工具方法：
```java
public static <T> PlainResultPage<T> buildPage(List<T> list, int pageNum, int pageSize, long total) {
    int totalPage = (int) Math.ceil((double) total / pageSize);
    PlainResultPage<T> page = new PlainResultPage<>();
    page.setPageNum(pageNum);
    page.setPageSize(pageSize);
    page.setTotal(total);
    page.setTotalPage(totalPage);
    page.setList(list);
    return page;
}
```

**（3）`selectByExample` + `list.get(0)` 模式**

多处先查列表再取第一条，应改为 `selectOneByExample` 或加 `LIMIT 1`：
```java
// 修改前
List<ServiceOrder> list = serviceOrderMapper.selectByExample(example);
if (!CollectionUtils.isEmpty(list)) { return list.get(0); }

// 修改后
ServiceOrder order = serviceOrderMapper.selectOneByExample(example);
```

---

## 四、架构优化

### 4.1 微服务边界不清晰

**现状：**
- `hosp-eap-web-manage` 承担了绝大部分业务逻辑（7464 行的订单 Service），职责过重
- `hosp-eap-web-user` 中存在大量与 manage 重复的逻辑
- RPC 调用目前仅 2 个接口（`RpcEnterpriseService`、`RpcRefundService`），模块间耦合主要通过共享数据库

**优化方向：**
- **短期**：通过 Dubbo RPC 扩展更多跨模块接口，减少 user/third 模块直接访问 manage 的数据库表
- **中期**：将订单、退款、支付等核心领域抽成独立 Service 模块
- **长期**：考虑按领域驱动（DDD）重新划分模块边界

### 4.2 数据库共享导致耦合

**现状：** 所有模块（manage/user/third/job）共享同一个数据库，通过各自的 Mapper 直接读写同一张表。

**问题：**
- 表结构变更需要同时修改多个模块的 Mapper/Example
- 无法独立部署和扩容
- 数据一致性靠代码人为保证

**优化方向：**
- 核心数据操作归口到 manage 模块，其他模块通过 RPC 访问
- 只读查询可保留直接数据库访问，但写操作应走统一入口

### 4.3 infra 层与业务层边界模糊

**现状：** `hosp-eap-infra` 仅包含 pojo/mapper/xml，属于纯数据访问层。但 extend Mapper 中包含复杂业务 SQL（多表 JOIN、子查询），使得业务逻辑散落在 XML 中。

**优化方向：**
- 复杂查询逻辑上移到 Service 层，Mapper 只做单表 CRUD
- 需要多表关联时，在 Service 层组装，避免 XML 中写超过 100 行的 SQL

---

## 五、代码规范与格式

### 5.1 命名不一致

| 问题 | 示例 |
|------|------|
| 方法名拼写错误 | `selectEnterpeiseCardVO`（应为 `Enterprise`） |
| 变量名不规范 | `toatl`（应为 `total`）、`liste`、`mc`、`stimes1` |
| 驼峰/下划线混用 | DTO 字段用驼峰，但 SQL 参数部分用下划线 |
| Example 变量名过长 | `crisisInterventionDetailExample`，可简化为 `detailExample` |

### 5.2 魔法数字 / 硬编码

```java
// 散布在代码各处的魔法数字
criteria.andServiceIdIn(Arrays.asList(2L, 3L));    // 2、3 是什么服务？
criteria.andStatusIn(Arrays.asList(2, 3));          // 2、3 是什么状态？
criteria.andTypeIn(Arrays.asList(0, 1, 2, 5));     // 用户类型？
criteria.andSpmNotIn(Arrays.asList("8.0","29.0","28.0")); // SPM 含义？
```

**修复方案：** 定义枚举常量或 `static final` 常量，提高可读性。项目已有 `CommonEnum` 体系，应统一使用。

### 5.3 事务边界不明确

部分 Service 方法涉及多表写操作但未标注 `@Transactional`，如：
- `EapServiceInstitutionServiceImpl` 中循环 `insertSelective`
- `EapCreatOrderServiceImpl` 中创建用户 + 就诊人 + 三方用户

---

## 六、优先级排序建议

| 优先级 | 类别 | 预期收益 |
|--------|------|---------|
| P0 紧急 | SQL 注入（`${}` → `#{}`） | 安全漏洞修复 |
| P1 高 | N+1 查询修复 | 列表接口性能提升 5-10 倍 |
| P1 高 | 内存分页 → 数据库分页 | 防止数据增长后 OOM |
| P2 中 | `e.printStackTrace()` → `log.error()` | 生产日志完整性 |
| P2 中 | 时间类型统一为 Date | 减少类型转换 bug |
| P3 低 | 上帝类拆分 | 长期可维护性 |
| P3 低 | 重复代码抽取公共方法 | 减少改动遗漏风险 |
| P4 规划 | 微服务边界优化 | 架构演进 |
