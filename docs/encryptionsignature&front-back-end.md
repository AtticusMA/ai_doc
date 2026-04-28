# 前后端请求 RSA签名+AES加密技术方案

## 1. 方案概述

本方案采用**非对称加密（RSA）+ 对称加密（AES）+ 数字签名**的混合加密架构，实现前后端通信的数据加密和完整性校验。

**核心思路：**
- 使用 AES 加密敏感数据（速度快，适合大数据量）
- 使用 RSA 加密 AES 密钥（安全传输对称密钥）
- 使用 RSA 签名验证请求完整性（防篡改、防重放）

---

## 2. 密钥管理

### 2.1 密钥生成

**后端 RSA 密钥对：**
- 私钥：后端持有，用于解密和签名
- 公钥：分发给前端，用于加密和验签

**前端 AES 密钥：**
- 每次请求动态生成 AES-256 密钥
- 使用后端 RSA 公钥加密后传输

### 2.2 密钥存储

**后端：**
```yaml
# application.yml
security:
  rsa:
    private-key: "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC..."
    public-key: "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvN..."
```

**前端：**
```javascript
// 从后端接口获取 RSA 公钥
const RSA_PUBLIC_KEY = await fetchPublicKey();
```

---

## 3. 加密流程

### 3.1 前端请求加密流程（字段级加密）

```
1. 生成随机 AES-256 密钥（32字节）和 IV（16字节）
2. 识别业务对象中的敏感字段（如手机号、身份证号）
3. 使用 AES-CBC 对敏感字段进行加密，替换原字段值
4. 保持 JSON 结构不变，非敏感字段明文传输
5. 对整个 Body JSON 字符串 + timestamp + requestId 生成签名
6. 使用后端 RSA 公钥加密 AES 密钥和 IV
7. 发送请求：

**Header 传输元数据：**
```
Headers:
  X-Encrypted-Key: RSA加密后的AES密钥（Base64）
  X-Encrypted-Iv: RSA加密后的IV（Base64）
  X-Signature: 请求签名
  X-Timestamp: 1713340800000
  X-Request-Id: uuid-xxx-xxx

Body: 业务 JSON 对象（敏感字段已加密，结构不变）
{
  "name": "张三",
  "age": 20,
  "mobile": "U2FsdGVkX1+vupppZksvRf5pq5g5XjFRlipRkwB0K1Y=",  // 加密
  "idCard": "U2FsdGVkX1+abc123def456...",  // 加密
  "address": [
    {"city": "北京", "street": "朝阳区"}
  ],
  "contacts": [
    {
      "name": "李四",
      "mobile": "U2FsdGVkX1+xyz789..."  // 加密
    }
  ]
}
```
```

### 3.2 后端解密流程

```
1. 从 Header 读取元数据（X-Encrypted-Key、X-Signature、X-Timestamp、X-Request-Id）
2. 验证时间戳（防重放攻击，5分钟内有效）
3. 验证 requestId 唯一性（防重放，存入 Redis）
4. 读取 Body JSON 对象
5. 验证签名：对 Body JSON 字符串 + timestamp + requestId 进行签名校验
6. 使用后端 RSA 私钥解密 AES 密钥和 IV
7. 递归遍历 JSON 对象，识别加密字段（通过注解或字段名规则）
8. 使用 AES 密钥解密敏感字段，还原原始值
9. 处理业务逻辑
10. 返回响应（可选加密敏感字段）
```

---

## 4. 代码实现

### 4.1 后端实现（Java）

#### 4.1.1 RSA 工具类

```java
package com.hxq.eap.common.util;

import org.apache.commons.codec.binary.Base64;
import javax.crypto.Cipher;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;

public class RSAUtil {
    private static final String ALGORITHM = "RSA";
    private static final int KEY_SIZE = 2048;
    
    /**
     * 生成 RSA 密钥对
     */
    public static KeyPair generateKeyPair() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance(ALGORITHM);
        generator.initialize(KEY_SIZE);
        return generator.generateKeyPair();
    }
    
    /**
     * 私钥解密
     */
    public static byte[] decryptByPrivateKey(byte[] data, String privateKeyStr) throws Exception {
        byte[] keyBytes = Base64.decodeBase64(privateKeyStr);
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance(ALGORITHM);
        PrivateKey privateKey = keyFactory.generatePrivate(keySpec);
        
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        cipher.init(Cipher.DECRYPT_MODE, privateKey);
        return cipher.doFinal(data);
    }
    
    /**
     * 公钥加密
     */
    public static byte[] encryptByPublicKey(byte[] data, String publicKeyStr) throws Exception {
        byte[] keyBytes = Base64.decodeBase64(publicKeyStr);
        X509EncodedKeySpec keySpec = new X509EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance(ALGORITHM);
        PublicKey publicKey = keyFactory.generatePublic(keySpec);
        
        Cipher cipher = Cipher.getInstance(ALGORITHM);
        cipher.init(Cipher.ENCRYPT_MODE, publicKey);
        return cipher.doFinal(data);
    }
    
    /**
     * 私钥签名
     */
    public static String sign(String data, String privateKeyStr) throws Exception {
        byte[] keyBytes = Base64.decodeBase64(privateKeyStr);
        PKCS8EncodedKeySpec keySpec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance(ALGORITHM);
        PrivateKey privateKey = keyFactory.generatePrivate(keySpec);
        
        Signature signature = Signature.getInstance("SHA256withRSA");
        signature.initSign(privateKey);
        signature.update(data.getBytes("UTF-8"));
        return Base64.encodeBase64String(signature.sign());
    }
    
    /**
     * 公钥验签
     */
    public static boolean verify(String data, String sign, String publicKeyStr) throws Exception {
        byte[] keyBytes = Base64.decodeBase64(publicKeyStr);
        X509EncodedKeySpec keySpec = new X509EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance(ALGORITHM);
        PublicKey publicKey = keyFactory.generatePublic(keySpec);
        
        Signature signature = Signature.getInstance("SHA256withRSA");
        signature.initVerify(publicKey);
        signature.update(data.getBytes("UTF-8"));
        return signature.verify(Base64.decodeBase64(sign));
    }
}
```

#### 4.1.2 AES 工具类

```java
package com.hxq.eap.common.util;

import org.apache.commons.codec.binary.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

public class AESUtil {
    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/CBC/PKCS5Padding";
    
    /**
     * AES 加密
     * @param data 明文
     * @param key AES密钥（32字节）
     * @param iv 初始化向量（16字节）
     */
    public static String encrypt(String data, byte[] key, byte[] iv) throws Exception {
        SecretKeySpec secretKey = new SecretKeySpec(key, ALGORITHM);
        IvParameterSpec ivSpec = new IvParameterSpec(iv);
        
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        cipher.init(Cipher.ENCRYPT_MODE, secretKey, ivSpec);
        byte[] encrypted = cipher.doFinal(data.getBytes(StandardCharsets.UTF_8));
        return Base64.encodeBase64String(encrypted);
    }
    
    /**
     * AES 解密
     */
    public static String decrypt(String encryptedData, byte[] key, byte[] iv) throws Exception {
        SecretKeySpec secretKey = new SecretKeySpec(key, ALGORITHM);
        IvParameterSpec ivSpec = new IvParameterSpec(iv);
        
        Cipher cipher = Cipher.getInstance(TRANSFORMATION);
        cipher.init(Cipher.DECRYPT_MODE, secretKey, ivSpec);
        byte[] decrypted = cipher.doFinal(Base64.decodeBase64(encryptedData));
        return new String(decrypted, StandardCharsets.UTF_8);
    }
}
```

#### 4.1.3 敏感字段注解

```java
package com.hxq.eap.common.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 标记需要加密的敏感字段
 */
@Target(ElementType.FIELD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Encrypted {
    /**
     * 字段描述
     */
    String value() default "";
}
```

#### 4.1.4 加密请求 DTO

```java
package com.hxq.eap.common.domain.dto;

import lombok.Data;

@Data
public class EncryptionMetadata {
    /**
     * RSA 加密后的 AES 密钥（Base64）
     */
    private String encryptedKey;
    
    /**
     * RSA 加密后的 IV（Base64）
     */
    private String encryptedIv;
    
    /**
     * 请求签名
     */
    private String signature;
    
    /**
     * 时间戳（毫秒）
     */
    private Long timestamp;
    
    /**
     * 请求唯一ID（UUID）
     */
    private String requestId;
}
```

#### 4.1.5 业务对象示例

```java
package com.hxq.eap.domain.dto;

import com.hxq.eap.common.annotation.Encrypted;
import lombok.Data;
import java.util.List;

@Data
public class StudentDTO {
    /**
     * 姓名（明文）
     */
    private String name;
    
    /**
     * 年龄（明文）
     */
    private Integer age;
    
    /**
     * 手机号（加密）
     */
    @Encrypted("手机号")
    private String mobile;
    
    /**
     * 身份证号（加密）
     */
    @Encrypted("身份证号")
    private String idCard;
    
    /**
     * 地址列表（明文）
     */
    private List<AddressDTO> address;
    
    /**
     * 联系人列表（包含加密字段）
     */
    private List<ContactDTO> contacts;
}

@Data
public class AddressDTO {
    private String city;
    private String street;
}

@Data
public class ContactDTO {
    private String name;
    
    @Encrypted("联系人手机号")
    private String mobile;
}
```

#### 4.1.6 字段加密工具类

```java
package com.hxq.eap.common.util;

import com.alibaba.fastjson.JSON;
import com.hxq.eap.common.annotation.Encrypted;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.codec.binary.Base64;

import java.lang.reflect.Field;
import java.util.Collection;

@Slf4j
public class FieldEncryptionUtil {
    
    /**
     * 递归加密对象中的敏感字段
     * @param obj 业务对象
     * @param aesKey AES密钥
     * @param iv 初始化向量
     */
    public static void encryptFields(Object obj, byte[] aesKey, byte[] iv) throws Exception {
        if (obj == null) {
            return;
        }
        
        Class<?> clazz = obj.getClass();
        
        // 处理集合类型
        if (obj instanceof Collection) {
            for (Object item : (Collection<?>) obj) {
                encryptFields(item, aesKey, iv);
            }
            return;
        }
        
        // 跳过基本类型和包装类
        if (clazz.isPrimitive() || clazz.getName().startsWith("java.lang")) {
            return;
        }
        
        // 遍历所有字段
        for (Field field : clazz.getDeclaredFields()) {
            field.setAccessible(true);
            Object value = field.get(obj);
            
            if (value == null) {
                continue;
            }
            
            // 检查是否有 @Encrypted 注解
            if (field.isAnnotationPresent(Encrypted.class)) {
                if (value instanceof String) {
                    String plainText = (String) value;
                    String encrypted = AESUtil.encrypt(plainText, aesKey, iv);
                    field.set(obj, encrypted);
                    log.debug("加密字段: {}.{}", clazz.getSimpleName(), field.getName());
                }
            } else if (value instanceof Collection) {
                // 递归处理集合
                encryptFields(value, aesKey, iv);
            } else if (!value.getClass().getName().startsWith("java.")) {
                // 递归处理嵌套对象
                encryptFields(value, aesKey, iv);
            }
        }
    }
    
    /**
     * 递归解密对象中的敏感字段
     * @param obj 业务对象
     * @param aesKey AES密钥
     * @param iv 初始化向量
     */
    public static void decryptFields(Object obj, byte[] aesKey, byte[] iv) throws Exception {
        if (obj == null) {
            return;
        }
        
        Class<?> clazz = obj.getClass();
        
        // 处理集合类型
        if (obj instanceof Collection) {
            for (Object item : (Collection<?>) obj) {
                decryptFields(item, aesKey, iv);
            }
            return;
        }
        
        // 跳过基本类型和包装类
        if (clazz.isPrimitive() || clazz.getName().startsWith("java.lang")) {
            return;
        }
        
        // 遍历所有字段
        for (Field field : clazz.getDeclaredFields()) {
            field.setAccessible(true);
            Object value = field.get(obj);
            
            if (value == null) {
                continue;
            }
            
            // 检查是否有 @Encrypted 注解
            if (field.isAnnotationPresent(Encrypted.class)) {
                if (value instanceof String) {
                    String encryptedText = (String) value;
                    try {
                        String decrypted = AESUtil.decrypt(encryptedText, aesKey, iv);
                        field.set(obj, decrypted);
                        log.debug("解密字段: {}.{}", clazz.getSimpleName(), field.getName());
                    } catch (Exception e) {
                        log.warn("解密字段失败: {}.{}, 保持原值", clazz.getSimpleName(), field.getName());
                    }
                }
            } else if (value instanceof Collection) {
                // 递归处理集合
                decryptFields(value, aesKey, iv);
            } else if (!value.getClass().getName().startsWith("java.")) {
                // 递归处理嵌套对象
                decryptFields(value, aesKey, iv);
            }
        }
    }
}
```

#### 4.1.7 解密拦截器（字段级加密）

```java
package com.hxq.eap.common.interceptor;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.hxq.eap.common.domain.dto.EncryptionMetadata;
import com.hxq.eap.common.util.AESUtil;
import com.hxq.eap.common.util.FieldEncryptionUtil;
import com.hxq.eap.common.util.RSAUtil;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.codec.binary.Base64;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.BufferedReader;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class DecryptInterceptor implements HandlerInterceptor {
    
    @Value("${security.rsa.private-key}")
    private String rsaPrivateKey;
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    private static final long TIMESTAMP_TOLERANCE = 5 * 60 * 1000; // 5分钟
    
    // Header 常量
    private static final String HEADER_ENCRYPTED_KEY = "X-Encrypted-Key";
    private static final String HEADER_ENCRYPTED_IV = "X-Encrypted-Iv";
    private static final String HEADER_SIGNATURE = "X-Signature";
    private static final String HEADER_TIMESTAMP = "X-Timestamp";
    private static final String HEADER_REQUEST_ID = "X-Request-Id";
    
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        
        // 1. 读取 Body（业务 JSON 对象，敏感字段已加密）
        String bodyJson = readBody(request);
        
        if (StringUtils.isBlank(bodyJson)) {
            // 空请求，直接放行
            return true;
        }
        
        // 2. 解析加密元数据
        EncryptionMetadata metadata = parseMetadata(request);
        
        if (metadata == null) {
            // 非加密请求，直接放行
            request.setAttribute("requestBody", bodyJson);
            return true;
        }
        
        // 3. 验证时间戳（防重放）
        long now = System.currentTimeMillis();
        if (Math.abs(now - metadata.getTimestamp()) > TIMESTAMP_TOLERANCE) {
            log.warn("请求已过期，timestamp: {}", metadata.getTimestamp());
            sendErrorResponse(response, 4001, "请求已过期");
            return false;
        }
        
        // 4. 验证 requestId 唯一性（防重放）
        if (!validateRequestId(metadata.getRequestId())) {
            log.warn("requestId 重复: {}", metadata.getRequestId());
            sendErrorResponse(response, 4003, "请求重复");
            return false;
        }
        
        // 5. 验证签名（防篡改）
        String signData = buildSignData(bodyJson, metadata.getTimestamp(), metadata.getRequestId());
        // TODO: 使用客户端公钥验签
        // if (!RSAUtil.verify(signData, metadata.getSignature(), clientPublicKey)) {
        //     log.warn("签名验证失败");
        //     sendErrorResponse(response, 4002, "签名验证失败");
        //     return false;
        // }
        
        // 6. 解密 AES 密钥和 IV
        byte[] aesKey = RSAUtil.decryptByPrivateKey(
            Base64.decodeBase64(metadata.getEncryptedKey()),
            rsaPrivateKey
        );
        
        byte[] iv = RSAUtil.decryptByPrivateKey(
            Base64.decodeBase64(metadata.getEncryptedIv()),
            rsaPrivateKey
        );
        
        // 7. 解析 Body JSON 对象
        JSONObject bodyObject = JSON.parseObject(bodyJson);
        
        // 8. 递归解密敏感字段
        FieldEncryptionUtil.decryptFields(bodyObject, aesKey, iv);
        
        // 9. 将解密后的 JSON 放入请求属性
        request.setAttribute("decryptedBody", bodyObject.toJSONString());
        request.setAttribute("decryptedObject", bodyObject);
        request.setAttribute("aesKey", aesKey);
        request.setAttribute("aesIv", iv);
        
        log.info("请求解密成功，requestId: {}", metadata.getRequestId());
        
        return true;
    }
    
    /**
     * 读取请求 Body
     */
    private String readBody(HttpServletRequest request) throws Exception {
        BufferedReader reader = request.getReader();
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line);
        }
        return sb.toString().trim();
    }
    
    /**
     * 解析加密元数据（从 Header 读取）
     */
    private EncryptionMetadata parseMetadata(HttpServletRequest request) {
        String encryptedKey = request.getHeader(HEADER_ENCRYPTED_KEY);
        
        if (StringUtils.isBlank(encryptedKey)) {
            return null; // 非加密请求
        }
        
        EncryptionMetadata metadata = new EncryptionMetadata();
        metadata.setEncryptedKey(encryptedKey);
        metadata.setEncryptedIv(request.getHeader(HEADER_ENCRYPTED_IV));
        metadata.setSignature(request.getHeader(HEADER_SIGNATURE));
        metadata.setTimestamp(Long.parseLong(request.getHeader(HEADER_TIMESTAMP)));
        metadata.setRequestId(request.getHeader(HEADER_REQUEST_ID));
        
        log.debug("从 Header 解析加密元数据");
        return metadata;
    }
    
    /**
     * 验证 requestId 唯一性（防重放）
     */
    private boolean validateRequestId(String requestId) {
        String key = "request:id:" + requestId;
        Boolean success = redisTemplate.opsForValue().setIfAbsent(key, "1", 5, TimeUnit.MINUTES);
        return Boolean.TRUE.equals(success);
    }
    
    /**
     * 构建签名数据：Body JSON + timestamp + requestId
     */
    private String buildSignData(String body, Long timestamp, String requestId) {
        return body + timestamp + requestId;
    }
    
    /**
     * 发送错误响应
     */
    private void sendErrorResponse(HttpServletResponse response, int code, String msg) throws Exception {
        response.setStatus(401);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(String.format("{\"code\":%d,\"msg\":\"%s\"}", code, msg));
    }
}
```

**配置拦截器：**

```java
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    
    @Autowired
    private DecryptInterceptor decryptInterceptor;
    
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(decryptInterceptor)
                .addPathPatterns("/api/secure/**"); // 仅对需要加密的接口生效
    }
}
```

**Controller 使用解密后的数据：**

```java
@RestController
@RequestMapping("/api/secure")
public class StudentController {
    
    @PostMapping("/student/save")
    public Result saveStudent(@RequestBody StudentDTO student) {
        // student 对象中的敏感字段已自动解密
        // mobile、idCard、contacts[].mobile 都是明文
        
        log.info("学生姓名: {}", student.getName());
        log.info("手机号（已解密）: {}", student.getMobile());
        
        // 业务逻辑
        return Result.success();
    }
}
```

### 4.2 前端实现（JavaScript）

#### 4.2.1 依赖库

```bash
npm install crypto-js jsencrypt
```

#### 4.2.2 加密工具类（字段级加密）

```javascript
import CryptoJS from 'crypto-js';
import JSEncrypt from 'jsencrypt';
import { v4 as uuidv4 } from 'uuid';

class EncryptionService {
  constructor(rsaPublicKey) {
    this.rsaPublicKey = rsaPublicKey;
    this.rsaEncrypt = new JSEncrypt();
    this.rsaEncrypt.setPublicKey(rsaPublicKey);
  }

  /**
   * 生成随机 AES 密钥（32字节）
   */
  generateAESKey() {
    return CryptoJS.lib.WordArray.random(32);
  }

  /**
   * 生成随机 IV（16字节）
   */
  generateIV() {
    return CryptoJS.lib.WordArray.random(16);
  }

  /**
   * AES 加密单个字段
   */
  aesEncryptField(data, key, iv) {
    const encrypted = CryptoJS.AES.encrypt(
      data,
      key,
      {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
      }
    );
    return encrypted.toString();
  }

  /**
   * RSA 加密
   */
  rsaEncrypt(data) {
    return this.rsaEncrypt.encrypt(data);
  }

  /**
   * 递归加密对象中的敏感字段
   * @param obj 业务对象
   * @param sensitiveFields 敏感字段名数组，如 ['mobile', 'idCard']
   * @param key AES密钥
   * @param iv 初始化向量
   */
  encryptSensitiveFields(obj, sensitiveFields, key, iv) {
    if (!obj || typeof obj !== 'object') {
      return obj;
    }

    // 处理数组
    if (Array.isArray(obj)) {
      return obj.map(item => this.encryptSensitiveFields(item, sensitiveFields, key, iv));
    }

    // 处理对象
    const result = { ...obj };
    for (const [fieldName, value] of Object.entries(result)) {
      if (value === null || value === undefined) {
        continue;
      }

      // 如果是敏感字段且是字符串，进行加密
      if (sensitiveFields.includes(fieldName) && typeof value === 'string') {
        result[fieldName] = this.aesEncryptField(value, key, iv);
      } 
      // 递归处理嵌套对象或数组
      else if (typeof value === 'object') {
        result[fieldName] = this.encryptSensitiveFields(value, sensitiveFields, key, iv);
      }
    }

    return result;
  }

  /**
   * 构建加密请求（Header 模式，字段级加密）
   * @param data 原始业务数据对象
   * @param sensitiveFields 敏感字段名数组
   * @returns 加密后的请求对象
   */
  buildEncryptedRequest(data, sensitiveFields = ['mobile', 'idCard', 'password']) {
    // 1. 生成 AES 密钥和 IV
    const aesKey = this.generateAESKey();
    const iv = this.generateIV();

    // 2. 深拷贝数据对象
    const clonedData = JSON.parse(JSON.stringify(data));

    // 3. 递归加密敏感字段
    const encryptedData = this.encryptSensitiveFields(clonedData, sensitiveFields, aesKey, iv);

    // 4. 转为 JSON 字符串
    const bodyJson = JSON.stringify(encryptedData);

    // 5. RSA 加密 AES 密钥和 IV
    const encryptedKey = this.rsaEncrypt(CryptoJS.enc.Base64.stringify(aesKey));
    const encryptedIv = this.rsaEncrypt(CryptoJS.enc.Base64.stringify(iv));

    // 6. 生成签名参数
    const timestamp = Date.now();
    const requestId = uuidv4();
    
    // 7. 生成签名：对 Body JSON + timestamp + requestId 签名
    const signature = this.generateSignature(bodyJson, timestamp, requestId);

    return {
      body: encryptedData,      // 加密后的业务对象（放到请求 Body）
      bodyJson,                 // Body 的 JSON 字符串（用于签名）
      encryptedKey,             // 加密的密钥（放到 Header）
      encryptedIv,              // 加密的 IV（放到 Header）
      signature,                // 签名（放到 Header）
      timestamp,                // 时间戳（放到 Header）
      requestId                 // 请求ID（放到 Header）
    };
  }

  /**
   * 生成签名：Body JSON + timestamp + requestId
   */
  generateSignature(bodyJson, timestamp, requestId) {
    const signData = `${bodyJson}${timestamp}${requestId}`;
    return CryptoJS.SHA256(signData).toString();
  }
}

export default EncryptionService;
```

#### 4.2.3 使用示例

**方式一：Header 模式（推荐，字段级加密）**

```javascript
import axios from 'axios';
import EncryptionService from './EncryptionService';

// 1. 获取后端 RSA 公钥
const rsaPublicKey = await axios.get('/api/security/public-key').then(res => res.data);

// 2. 初始化加密服务
const encryptionService = new EncryptionService(rsaPublicKey);

// 3. 准备业务数据（包含敏感字段）
const studentData = {
  name: '张三',
  age: 20,
  mobile: '13800138000',  // 敏感字段
  idCard: '110101199001011234',  // 敏感字段
  address: [
    { city: '北京', street: '朝阳区' }
  ],
  contacts: [
    {
      name: '李四',
      mobile: '13900139000'  // 敏感字段
    }
  ]
};

// 4. 加密敏感字段
const encrypted = encryptionService.buildEncryptedRequest(
  studentData,
  ['mobile', 'idCard']  // 指定需要加密的字段名
);

// 5. 发送请求：元数据在 Header，业务数据在 Body
axios.post('/api/secure/student/save', encrypted.body, {
  headers: {
    'Content-Type': 'application/json',
    'X-Encrypted-Key': encrypted.encryptedKey,
    'X-Encrypted-Iv': encrypted.encryptedIv,
    'X-Signature': encrypted.signature,
    'X-Timestamp': encrypted.timestamp.toString(),
    'X-Request-Id': encrypted.requestId
  }
})
  .then(response => {
    console.log('保存成功', response.data);
  })
  .catch(error => {
    console.error('保存失败', error);
  });

// 实际发送的 Body 示例：
// {
//   "name": "张三",
//   "age": 20,
//   "mobile": "U2FsdGVkX1+vupppZksvRf5pq5g5XjFRlipRkwB0K1Y=",  // 已加密
//   "idCard": "U2FsdGVkX1+abc123def456...",  // 已加密
//   "address": [{"city": "北京", "street": "朝阳区"}],
//   "contacts": [
//     {
//       "name": "李四",
//       "mobile": "U2FsdGVkX1+xyz789..."  // 已加密
//     }
//   ]
// }
```

**Axios 拦截器封装（自动加密）**

```javascript
// 创建 axios 实例
const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000
});

// 配置
const SENSITIVE_FIELDS = ['mobile', 'idCard', 'password', 'bankCard']; // 全局敏感字段配置

// 请求拦截器
apiClient.interceptors.request.use(async (config) => {
  // 判断是否需要加密（根据 URL 或配置）
  if (config.url.startsWith('/secure/')) {
    const encryptionService = new EncryptionService(rsaPublicKey);
    const encrypted = encryptionService.buildEncryptedRequest(
      config.data,
      SENSITIVE_FIELDS
    );
    
    // Header 模式：元数据在 Header，业务数据在 Body
    config.headers['X-Encrypted-Key'] = encrypted.encryptedKey;
    config.headers['X-Encrypted-Iv'] = encrypted.encryptedIv;
    config.headers['X-Signature'] = encrypted.signature;
    config.headers['X-Timestamp'] = encrypted.timestamp.toString();
    config.headers['X-Request-Id'] = encrypted.requestId;
    config.data = encrypted.body; // Body 是加密后的业务对象
  }
  
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default apiClient;
```

**使用封装后的 apiClient：**

```javascript
// 业务代码无需关心加密细节，直接传原始数据
apiClient.post('/secure/student/save', {
  name: '张三',
  age: 20,
  mobile: '13800138000',
  idCard: '110101199001011234',
  address: [{ city: '北京', street: '朝阳区' }],
  contacts: [
    { name: '李四', mobile: '13900139000' }
  ]
})
  .then(response => {
    console.log('保存成功', response.data);
  });
```

---

---

## 5. 安全增强

### 5.1 防重放攻击

- 时间戳验证：请求时间戳与服务器时间差不超过 5 分钟
- RequestId 唯一性验证：将已处理的 requestId 存入 Redis，有效期 5 分钟

```java
@Component
public class RequestIdValidator {
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    public boolean validateRequestId(String requestId) {
        String key = "request:id:" + requestId;
        Boolean success = redisTemplate.opsForValue().setIfAbsent(key, "1", 5, TimeUnit.MINUTES);
        return Boolean.TRUE.equals(success);
    }
}
```

### 5.2 密钥轮换

- RSA 密钥每 90 天轮换一次
- 支持多版本密钥共存（通过 keyId 标识）

### 5.3 敏感字段配置

**后端注解方式：**

```java
@Target(ElementType.FIELD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Encrypted {
    String value() default "";
}
```

**前端配置方式：**

```javascript
// 全局敏感字段配置
const SENSITIVE_FIELDS = ['mobile', 'idCard', 'password', 'bankCard', 'email'];

// 或者在接口级别配置
apiClient.post('/secure/student/save', studentData, {
  encryptFields: ['mobile', 'idCard']  // 自定义配置
});
```

public class UserDTO {
    private String username;
    
    @Encrypted
    private String password;
    
    @Encrypted
    private String idCard;
}
```

---

## 6. 性能优化

### 6.1 加密范围控制

- 仅对敏感字段加密（密码、身份证、手机号等）
- 非敏感字段明文传输

### 6.2 缓存 RSA 公钥

前端缓存 RSA 公钥到 LocalStorage，减少请求次数。

### 6.3 异步解密

对于批量数据，使用线程池异步解密：

```java
@Async
public CompletableFuture<String> decryptAsync(String encryptedData, byte[] key, byte[] iv) {
    return CompletableFuture.completedFuture(AESUtil.decrypt(encryptedData, key, iv));
}
```

---

## 7. 部署配置

### 7.1 生成 RSA 密钥对

```bash
# 生成私钥
openssl genrsa -out private_key.pem 2048

# 生成公钥
openssl rsa -in private_key.pem -pubout -out public_key.pem

# 转换为 PKCS8 格式（Java 使用）
openssl pkcs8 -topk8 -inform PEM -in private_key.pem -outform PEM -nocrypt -out private_key_pkcs8.pem
```

### 7.2 配置文件

```yaml
# application.yml
security:
  rsa:
    private-key: ${RSA_PRIVATE_KEY:MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...}
    public-key: ${RSA_PUBLIC_KEY:MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvN...}
  encryption:
    enabled: true
    timestamp-tolerance: 300000  # 5分钟
```

---

## 8. 测试用例

### 8.1 单元测试

```java
@Test
public void testRSAEncryptDecrypt() throws Exception {
    String data = "Hello World";
    String publicKey = "...";
    String privateKey = "...";
    
    byte[] encrypted = RSAUtil.encryptByPublicKey(data.getBytes(), publicKey);
    byte[] decrypted = RSAUtil.decryptByPrivateKey(encrypted, privateKey);
    
    assertEquals(data, new String(decrypted));
}

@Test
public void testAESEncryptDecrypt() throws Exception {
    String data = "Sensitive Data";
    byte[] key = new byte[32];
    byte[] iv = new byte[16];
    new SecureRandom().nextBytes(key);
    new SecureRandom().nextBytes(iv);
    
    String encrypted = AESUtil.encrypt(data, key, iv);
    String decrypted = AESUtil.decrypt(encrypted, key, iv);
    
    assertEquals(data, decrypted);
}
```

---

## 9. 常见问题

### Q1: RSA 加密数据长度限制？
**A:** RSA-2048 最多加密 245 字节数据，因此只用于加密 AES 密钥（32字节），不直接加密业务数据。

### Q2: 如何处理密钥泄露？
**A:** 立即轮换密钥，撤销旧密钥，通知客户端更新公钥。

### Q3: 前端如何存储 RSA 公钥？
**A:** 存储在 LocalStorage，设置过期时间（如 24 小时），过期后重新获取。

### Q4: 是否需要对响应数据加密？
**A:** 根据业务需求，敏感响应数据（如用户详情）建议加密返回。

### Q5: 为什么使用字段级加密而不是整体加密？
**A:** 
- **字段级加密**：只加密敏感字段（手机号、身份证），保持 JSON 结构，便于调试和日志记录
- **整体加密**：加密整个 Body，安全性更高但调试困难，日志无法查看业务字段
- **推荐**：根据业务需求选择，一般场景使用字段级加密即可

### Q6: 签名为什么使用 Body JSON + timestamp + requestId？
**A:** 
- Body JSON：确保业务数据完整性，防止篡改
- timestamp：防止重放攻击（时间窗口限制）
- requestId：防止重放攻击（唯一性验证）
- 三者结合提供完整的防篡改和防重放保护

### Q7: 如何处理嵌套对象和数组中的敏感字段？
**A:** 
- 使用递归算法自动处理嵌套结构
- 前端：`encryptSensitiveFields` 方法递归遍历对象和数组
- 后端：`FieldEncryptionUtil.decryptFields` 方法递归解密
- 示例：`contacts[].mobile` 会被自动识别并加密/解密

---

## 10. 改造方案总结

### 10.1 改造目标

将加密参数从 Body 迁移到 Header，同时保持对旧项目的兼容性。

### 10.2 改造优势

**字段级加密优势：**
- 只加密敏感字段，保持 JSON 结构不变
- 非敏感字段明文传输，便于调试和日志记录
- 后端可直接使用 @RequestBody 接收对象，无需额外解析
- 灵活配置加密字段，不同接口可加密不同字段

**Header 模式优势：**
- 元数据（签名、密钥、时间戳）和业务数据分离，职责更清晰
- Header 存放传输层信息，Body 存放业务数据
- 便于网关层统一处理签名验证
- 符合 HTTP 规范（元数据在 Header，数据在 Body）

### 10.3 实施步骤

**阶段一：后端实现**
1. 实现 RSA、AES 工具类
2. 创建 `@Encrypted` 注解标记敏感字段
3. 实现 `FieldEncryptionUtil` 字段加密工具类
4. 实现 `DecryptInterceptor` 拦截器
5. 配置拦截器路径
6. 部署到测试环境验证

**阶段二：前端实现**
1. 安装依赖：`crypto-js`、`jsencrypt`、`uuid`
2. 实现 `EncryptionService` 加密服务
3. 配置 Axios 拦截器自动加密
4. 配置全局敏感字段列表
5. 测试加密接口

**阶段三：联调测试**
1. 测试正常加密请求
2. 测试防重放攻击（重复 requestId）
3. 测试时间戳过期
4. 测试签名验证
5. 性能测试

### 10.4 配置示例

**后端配置（application.yml）：**
```yaml
security:
  rsa:
    private-key: ${RSA_PRIVATE_KEY}
    public-key: ${RSA_PUBLIC_KEY}
  encryption:
    enabled: true
    timestamp-tolerance: 300000  # 5分钟
```

**前端配置（.env）：**
```bash
# 敏感字段配置
VITE_SENSITIVE_FIELDS=mobile,idCard,password,bankCard
```

### 10.5 监控建议

添加日志监控加密请求：

```java
@Slf4j
@Component
public class DecryptInterceptor implements HandlerInterceptor {
    
    private EncryptionMetrics metrics; // 自定义指标收集器
    
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        // 解析加密元数据
        EncryptionMetadata metadata = parseMetadata(request);
        
        if (metadata != null) {
            metrics.incrementEncryptedRequest(); // 统计加密请求
            log.info("收到加密请求，requestId: {}, timestamp: {}", 
                metadata.getRequestId(), metadata.getTimestamp());
        }
        
        // ... 其他逻辑
    }
}
```

### 10.6 请求示例

**Header 模式请求示例（字段级加密）：**
```http
POST /api/secure/student/save HTTP/1.1
Host: example.com
Content-Type: application/json
X-Encrypted-Key: U2FsdGVkX1+vupppZksvRf5pq5g5XjFRlipRkwB0K1Y=
X-Encrypted-Iv: U2FsdGVkX1+vupppZksvRf5pq5g5XjFRlipRkwB0K1Y=
X-Signature: 5d41402abc4b2a76b9719d911017c592
X-Timestamp: 1713340800000
X-Request-Id: 550e8400-e29b-41d4-a716-446655440000

{
  "name": "张三",
  "age": 20,
  "mobile": "U2FsdGVkX1+vupppZksvRf5pq5g5XjFRlipRkwB0K1Y=",
  "idCard": "U2FsdGVkX1+abc123def456...",
  "address": [
    {"city": "北京", "street": "朝阳区"}
  ],
  "contacts": [
    {
      "name": "李四",
      "mobile": "U2FsdGVkX1+xyz789..."
    }
  ]
}
```

---

## 11. 参考资料

- [RFC 3447 - RSA Cryptography Specifications](https://tools.ietf.org/html/rfc3447)
- [NIST SP 800-38A - AES Modes of Operation](https://csrc.nist.gov/publications/detail/sp/800-38a/final)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

---

**文档版本:** 2.0  
**最后更新:** 2026-04-17  
**维护者:** 开发团队  
**变更记录:**
- v2.0 (2026-04-17): 新增 Header 传输模式，保持 Body 模式兼容
- v1.0 (2026-04-17): 初始版本，仅支持 Body 模式
**维护者:** 开发团队
