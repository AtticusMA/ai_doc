# Development Standards & Guidelines

## 1. Java 编码规范

### 命名规则
- **类名：** UpperCamelCase（如 `EapCardController`）
- **变量/方法：** lowerCamelCase（如 `batchCount`）
- **常量：** UPPER_SNAKE_CASE（如 `MAX_RETRY_COUNT`）

### Lombok 使用
- DTO/VO 类使用 `@Data`；Service 使用 `@Slf4j`
- **不要**在有继承关系的实体上用 `@Data`（会影响 equals/hashCode）

### 日期类型
- **必须使用 `java.util.Date`**，项目所有实体类（`EapEnterpriseCard`、`EapHomePage` 等）均使用 `Date`
- **禁止使用 `java.time.LocalDateTime`**，会导致类型不兼容

## 2. API 接口规范

### 返回值
所有接口统一返回 `PlainResult` 包装：
```java
// 成功
return PlainResult.success(data);

// 失败
return PlainResult.error(IErrorCodeEnums.VALIDATED_PARAMS.getCode(), "Error message");
throw new BizException(5001, "业务异常描述");
```

### Controller 结构
```java
@Slf4j
@Api(tags = "XxxController", description = "模块描述")
@RestController
@RequestMapping(value = "/hxq-eap-manage-api/xxx")
public class XxxController {

    @ApiOperation(value = "接口描述")
    @PostMapping(value = "/methodName")
    @ApiLogInfo(menuName = "模块名", operateName = "操作名", operateType = 1)
    @ApiImplicitParams({
        @ApiImplicitParam(paramType = "header", name = "token", dataType = "String", required = true, value = "用户token")
    })
    public PlainResult<XxxVO> method(@RequestBody @Valid XxxParam param) {
        return service.method(param);
    }
}
```

### 入参规范
- 使用 `*Param` DTO 对象 + `@RequestBody`
- **禁止**使用 `Map<String, Object>` 或 `JSONObject` 作为入参
- 使用 JSR-303 注解校验：`@NotNull`, `@NotBlank`, `@Size` 等

## 3. Service 规范

### 事务配置
- `get*`/`select*` 方法 → 只读事务
- 其他方法 → 默认事务
- 需要显式声明时：`@Transactional(value = "transactionManager", rollbackFor = Exception.class)`

### 包组织
- `service/eap/` → `hxq_eap` 数据库业务
- `service/hxq/` → `hxq_common` 数据库业务
- 接口文件放 `service/eap/`，实现放 `service/eap/impl/`

## 4. 异常处理

- **业务异常：** 抛出 `BizException`（可传 code + message）
- **全局捕获：** 由 `@ControllerAdvice` 全局异常处理器统一包装为 `PlainResult` 返回
- **Service 内部：** 用 `ObjectUtils.isEmpty()` 做空判断，避免 NPE

## 5. 对象复制注意事项

使用 `BeanUtils.copyProperties(source, target)` 时：
```java
EapEnterpriseCard newBatch = new EapEnterpriseCard();
BeanUtils.copyProperties(sourceBatch, newBatch);
newBatch.setBatchId(null);  // ★ 必须清空主键再 insert
newBatch.setCreateTime(new Date());
newBatch.setModTime(new Date());
```

## 6. 分页查询规范

```java
// PageHelper.startPage 必须紧跟查询语句，中间不能有其他 SQL
PageHelper.startPage(pageNum, pageSize);
List<Xxx> list = mapper.selectXxx(param);
PageInfo<Xxx> pageInfo = new PageInfo<>(list);
```
