# 接口管理 API 对接文档

本文档用于管理端维护“可对接接口清单”，以及按应用开通、关闭和配置接口。

## 通用说明

基础地址：`/api/v1`

认证方式：管理端接口均需要登录后携带 Bearer Token。

```http
Authorization: Bearer <admin_token>
Content-Type: application/json
```

响应格式：

```json
{
  "success": true,
  "message": "操作结果",
  "data": {}
}
```

## 字段说明

### 接口定义字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 接口显示名称 |
| `interface_key` | string | 是 | 接口唯一标识，例如 `kami_verify` |
| `method` | string | 是 | 请求方法，支持 `GET`、`POST`、`PUT`、`DELETE`、`PATCH` |
| `path` | string | 是 | 接口地址，例如 `/api/v1/sdk/verify` |
| `category` | string | 否 | 分类，例如 `core`、`points`、`device` |
| `status` | integer | 否 | `1` 启用，`0` 停用 |
| `request_params` | object | 否 | 请求参数说明 JSON |
| `response_example` | object | 否 | 响应示例 JSON |
| `doc_markdown` | string | 否 | 接口文档说明 |

### 应用接口配置字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `enabled` | boolean | 是 | 是否为当前应用开通该接口 |
| `quota_limit` | integer/null | 否 | 接口额度上限，`null` 表示不限 |
| `expires_at` | string/null | 否 | 到期时间，ISO 时间字符串，`null` 表示永久 |
| `config` | object | 否 | 应用级接口参数配置 |
| `remark` | string/null | 否 | 备注 |

## 1. 新增接口

`POST /api/v1/admin/interfaces`

```json
{
  "name": "卡密验证",
  "interface_key": "kami_verify",
  "method": "POST",
  "path": "/api/v1/sdk/verify",
  "category": "core",
  "status": 1,
  "request_params": {
    "kami_code": "卡密",
    "device_uuid": "设备唯一标识"
  },
  "response_example": {
    "success": true,
    "data": {
      "expire_time": "2026-12-31T23:59:59"
    }
  },
  "doc_markdown": "用于业务端提交卡密和设备信息完成验证。"
}
```

## 2. 接口列表

`GET /api/v1/admin/interfaces`

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `category` | string | 按分类过滤 |
| `status` | integer | `1` 启用，`0` 停用 |

## 3. 编辑接口

`PUT /api/v1/admin/interfaces/{interface_id}`

请求体可传任意需要修改的字段：

```json
{
  "name": "卡密验证 V2",
  "status": 1,
  "doc_markdown": "更新后的接口说明"
}
```

## 4. 查看应用接口列表

`GET /api/v1/admin/apps/{app_id}/interfaces`

返回所有接口定义，并附带当前应用的开通状态和配置：

```json
{
  "success": true,
  "data": [
    {
      "interface_id": 1,
      "name": "卡密验证",
      "interface_key": "kami_verify",
      "method": "POST",
      "path": "/api/v1/sdk/verify",
      "category": "core",
      "status": 1,
      "enabled": true,
      "quota_limit": null,
      "expires_at": null,
      "config": {},
      "remark": "核心验证接口"
    }
  ]
}
```

## 5. 配置或开通应用接口

`PUT /api/v1/admin/apps/{app_id}/interfaces/{interface_id}`

```json
{
  "enabled": true,
  "quota_limit": 100000,
  "expires_at": "2026-12-31T23:59:59",
  "config": {
    "rate_limit_per_minute": 600
  },
  "remark": "生产应用开通"
}
```

关闭接口：

```json
{
  "enabled": false,
  "quota_limit": null,
  "expires_at": null,
  "config": {},
  "remark": "暂停使用"
}
```

## 后台页面入口

管理端页面已提供两个入口：

| 页面 | 功能 |
| --- | --- |
| `接口管理 / 新增接口` | 录入接口名称、标识、方法、接口地址、请求参数、响应示例和文档 |
| `接口管理 / 接口列表` | 查看、筛选、编辑接口，查看接口文档 |
| `应用管理 / 接口列表` | 按应用开通接口、配置额度、到期时间、接口参数，并查看文档 |
