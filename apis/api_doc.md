# API Documentation

生产环境请以实际域名为准。

---

## 1. 认证（JWT）

**认证方式**：HTTP Bearer  
**请求头**：

```
Authorization: Bearer <access_token>
```

### 1.1 获取 Token

**POST** `/api/auth/token`

**Request**

```json
{
  "client_id": "your_client_id",
  "client_secret": "your_client_secret"
}
```

**Response**

```json
{
  "access_token": "xxx",
  "refresh_token": "yyy",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000
}
```

**说明**

- `access_token`：访问业务 API 的短期令牌
- `refresh_token`：用于刷新 `access_token` 的长期令牌（一次性旋转）

---

### 1.2 刷新 Token

**POST** `/api/auth/refresh`

**Request**

```json
{
  "refresh_token": "yyy"
}
```

**Response**

```json
{
  "access_token": "new_xxx",
  "refresh_token": "new_yyy",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000
}
```

**说明**

- 旧 `refresh_token` 会立刻失效
- 请用新的 `refresh_token` 继续后续刷新

---

## 2. 健康检查

**GET** `/api/health`  
**Header**：必须携带 `Authorization`

**Response**

```json
{
  "message": "hello world",
  "timestamp": "2026-03-05T12:34:56.789012"
}
```

---

## 3. 通用错误

**401 Unauthorized**

```json
{
  "detail": "Missing bearer token"
}
```

**401 Unauthorized**

```json
{
  "detail": "Invalid token"
}
```

**401 Unauthorized**

```json
{
  "detail": "Token expired"
}
```