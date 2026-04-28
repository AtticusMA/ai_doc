# Database Architecture

## 1. 基础信息

- **数据库引擎：** MySQL 8.0
- **ORM：** MyBatis XML Mapper + MyBatis Generator 生成
- **双库架构：** `hxq_eap`（主业务库） + `hxq_common`（公共库）

## 2. 数据库分包

| 数据库 | Mapper 包 | POJO 包 |
|--------|-----------|---------|
| `hxq_eap` | `com.hxq.eap.infra.mapper.eap` | `com.hxq.eap.infra.pojo.eap` |
| `hxq_common` | `com.hxq.eap.infra.mapper.hxq` | `com.hxq.eap.infra.pojo.hxq` |

扩展 Mapper（手写 SQL）：`com.hxq.eap.infra.mapper.eap.extend`

## 3. 核心表清单

### 企业与卡券
| 表名 | 说明 | 主键 |
|------|------|------|
| `eap_enterprise` | 企业租户信息 | `enterprise_id` |
| `eap_enterprise_card` | 企业批次/开卡配置 | `batch_id` |
| `eap_card` | 卡券模板定义 | `id` |
| `eap_cards` | 卡密记录（每张实体卡） | `card_id` |
| `eap_card_service` | 批次绑定的服务配置 | `card_service_id` |
| `eap_batch_frequency` | 批次频次设置 | `frequency_id` |

### 主页与展示
| 表名 | 说明 | 主键 | 关联 |
|------|------|------|------|
| `eap_home_page` | 主页配置（按 batch_no 区分） | `id` | batch_no → eap_enterprise_card |
| `eap_home_item` | 主页配置项（功能入口） | `id` | page_id → eap_home_page.id |
| `eap_banner` | Banner 轮播图（按 batch_no） | `banner_id` | batch_no → eap_enterprise_card |
| `eap_category` | 服务分类 | `id` | - |

### 服务资源
| 表名 | 说明 |
|------|------|
| `eap_service_article` | 文章服务资源 |
| `eap_service_video` | 视频服务资源 |
| `eap_service_topic_course` | 专题课程服务 |
| `eap_service_product` | 商品服务 |
| `eap_service_advisory` | 量表/问卷服务 |
| `eap_service_doctor` | 服务人员配置 |
| `eap_service_institution` | 面询机构 |
| `eap_service_meeting` | 会议服务 |
| `eap_service_sleep_product` | 睡眠监测产品 |

### 订单与支付
| 表名 | 说明 |
|------|------|
| `eap_service_order` | 服务预约订单 |
| `eap_service_order_extend` | 订单扩展信息 |
| `eap_pay_order` | 支付交易记录 |
| `eap_refund_order` | 退款记录 |

### 用户
| 表名 | 说明 |
|------|------|
| `eap_customer` | C 端用户信息 |
| `eap_wx_user` | 微信用户绑定 |
| `eap_manage_user` | 管理后台用户 |
| `eap_manage_role` | 管理后台角色 |
| `eap_manage_dept` | 管理后台部门 |

### 第三方对接
| 表名 | 说明 |
|------|------|
| `third_task` | 第三方推送任务 |
| `eap_dingtalk_push_record` | 钉钉推送记录 |

## 4. 字段设计约定

### 审计字段（几乎所有表都有）
```sql
create_time  DATETIME     -- 创建时间
mod_time     DATETIME     -- 修改时间
create_name  VARCHAR(50)  -- 创建人
mod_name     VARCHAR(50)  -- 修改人
```

### 主键
- 使用 `BIGINT` 自增主键
- POJO 对应 `Long` 类型

### 软删除
- 使用 `status` 字段：`0`=默认, `1`=启用, `2`=停用, `99`=删除
- 部分表有 `del_status`（如 eap_banner：`0`=正常, `1`=已删除）

### 命名
- 表名/列名：snake_case
- 业务表前缀：`eap_`

## 5. MyBatis XML 开发规范

### 查询列
```xml
<!-- 正确：使用 Base_Column_List -->
<select id="selectById" resultMap="BaseResultMap">
    select <include refid="Base_Column_List"/> from eap_xxx where id = #{id}
</select>

<!-- 错误：禁止 SELECT * -->
<select id="selectById">
    select * from eap_xxx where id = #{id}
</select>
```

### 参数化查询
```xml
<!-- 正确：使用 #{} 防止 SQL 注入 -->
<if test="batchNo != null">
    and batch_no = #{batchNo}
</if>

<!-- ${} 仅用于列名/排序字段，且必须来自可控的服务端逻辑 -->
<if test="orderByClause != null">
    order by ${orderByClause}
</if>
```

### LIKE 查询
```xml
<!-- 使用 concat 函数避免 SQL 注入（推荐） -->
and name like concat('%', #{keyword}, '%')
```

### 批量插入
```xml
<insert id="insertBatch">
    insert into eap_xxx (col1, col2) values
    <foreach collection="list" item="item" separator=",">
        (#{item.col1}, #{item.col2})
    </foreach>
</insert>
```

## 6. MyBatis Generator 使用

```bash
cd hosp-eap-infra
mvn mybatis-generator:generate
```

配置文件：`src/main/resources/generatorConfig.xml`
- 修改 `<table tableName="xxx">` 指定生成目标表
- 生成产物：Mapper 接口 + XML + POJO + Example 类
- **注意：** 生成后检查 XML 是否覆盖了手写的扩展 SQL
