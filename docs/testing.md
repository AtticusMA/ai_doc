# 测试规范

## 1. 项目测试现状

项目以手动接口测试（Postman / Swagger）为主，自动化测试覆盖有限：

| 模块 | 测试内容 | 说明 |
|------|---------|------|
| `hosp-eap-job-admin` | DAO 层 + Controller 层单元测试 | JUnit 5 + `@SpringBootTest` + MockMvc，较完整 |
| `hosp-eap-web-user` | 工具类调试脚本（RedisUtils、TestTime） | 非正式测试，仅用于本地验证 |
| `hosp-eap-web-manage` | 仅 Application 启动类测试 | 基本无业务测试 |
| `hosp-eap-infra` | 仅 Application 启动类测试 | 基本无业务测试 |

## 2. 编写测试时的约束

### 测试框架
- JUnit 5（`@Test`, `@ExtendWith`）
- Spring Boot Test（`@SpringBootTest`）
- Mockito（`@Mock`, `@InjectMocks`）— 目前项目中未大量使用，但依赖已引入

### 测试文件位置
```
各模块/src/test/java/com/hxq/eap/...
```

### Service 层单元测试模板
```java
@ExtendWith(MockitoExtension.class)
public class XxxServiceTest {
    @Mock
    private XxxMapper xxxMapper;

    @InjectMocks
    private XxxServiceImpl xxxService;

    @Test
    void testMethod() {
        // Given
        when(xxxMapper.selectByPrimaryKey(1L)).thenReturn(mockEntity);
        // When
        XxxVo result = xxxService.getXxx(1L);
        // Then
        assertNotNull(result);
    }
}
```

### 注意事项
- 测试类中日期使用 `java.util.Date`，与生产代码保持一致
- 需要 Redis、数据库等外部依赖的测试，加 `@SpringBootTest` 并确保 `application-test.yml` 配置可用
- 测试中不要硬编码线上环境地址或密码
- PlainResult 断言：成功判断 `result.getCode() == 2000`
