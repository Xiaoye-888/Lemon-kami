# 卡密验证核心增强 API 文档

本文档覆盖本次新增和增强的卡密验证核心能力，不包含代理商、支付、商城、工单。

## 1. 卡密类型

| 类型 | 值 | 说明 |
| --- | --- | --- |
| 小时卡 | `hour` | 激活后有效 1 小时 |
| 天卡 | `day` | 激活后有效 1 天 |
| 周卡 | `week` | 激活后有效 7 天 |
| 月卡 | `month` | 激活后有效 30 天 |
| 季卡 | `quarter` | 激活后有效 90 天 |
| 年卡 | `year` | 激活后有效 365 天 |
| 永久卡 | `lifetime` | 无过期时间 |
| 次数卡 | `times` | 验证不扣次数，调用 consume 接口才扣减 |
| 积分卡 | `points` | 普通用户兑换为积分余额 |

## 2. 管理端：批量生成卡密

`POST /api/v1/admin/kamis/batch`

Query 参数：

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `app_id` | 是 | 应用 ID |
| `kami_type` | 是 | 卡密类型 |
| `count` | 是 | 生成数量，1-1000 |
| `times` | 次数卡必填 | 次数卡总次数 |
| `points_amount` | 积分卡必填 | 积分卡面额 |
| `batch_no` | 否 | 批次号，不填自动生成 |
| `points_valid_days` | 否 | 积分兑换后有效天数，不填永久 |
| `machine_bind_mode` | 否 | 机器码绑定模式：`no_limit` 不限制、`one_card_one_device` 一机一码、`one_card_multi_device` 一卡多机；默认 `one_card_one_device` |
| `authorization_owner` | 否 | 授权归属：`device` 设备授权、`user` 用户授权、`auto` 自动识别；默认 `device` |
| `user_bind_mode` | 否 | 用户绑定：`none` 不绑定用户、`auto` 自动识别绑定、`required` 必须绑定用户；默认 `none` |
| `code_prefix` | 否 | 卡密前缀，例如 `VIP-` |
| `code_length` | 否 | 随机后缀长度，默认 16 |
| `charset` | 否 | `upper_numeric`、`numeric`、`upper`、`lower_mixed` |

响应重点字段：

```json
{
  "success": true,
  "data": {
    "count": 2,
    "kami_type": "week",
    "batch_no": "custom-batch",
    "machine_bind_mode": "one_card_one_device",
    "code_prefix": "VIP-",
    "code_length": 8,
    "charset": "numeric",
    "codes": ["VIP-12345678", "VIP-87654321"]
  }
}
```

## 3. SDK：验证/消费卡密

`POST /api/v1/sdk/verify`

该接口仍使用现有 SDK 加密请求格式。解密后的业务字段：

```json
{
  "kami": "TIMES3",
  "uuid": "device-001",
  "fingerprint": "hardware-fingerprint",
  "user_id": 123,
  "username": "demo-user"
}
```

行为：

- 未使用卡密首次验证时自动激活并绑定设备。
- `machine_bind_mode=no_limit` 时不限制机器码；`one_card_one_device` 时一个卡密只能绑定一台设备；`one_card_multi_device` 时一个卡密可绑定多台设备并记录绑定明细。
- 用户授权能力在 `sdk.verify` 独立配置中开启；开启后，每个批次按自己的 `authorization_owner` 和 `user_bind_mode` 执行用户绑定策略。
- `user_bind_mode=auto` 时，每张卡密首次使用会自动识别：传入有效 `user_id`/`username` 则绑定到用户，未传用户则按设备授权；一旦绑定用户，后续验证和核销必须传入同一用户。
- `user_bind_mode=required` 时，验证和核销必须传入 `user_id` 或 `username`。
- 时间卡返回到期时间。
- 永久卡 `expire_time` 为 `null`。
- 次数卡验证只检查剩余次数，不扣减次数；业务侧完成一次消耗/核销时，需单独调用 `consume` 接口扣减。
- 开启 IP 绑定后，后续验证必须来自首次激活 IP。
- 设备不匹配、卡密冻结、卡密过期、次数用完会返回 `success=false`。

次数卡验证响应示例：

```json
{
  "success": true,
  "message": "验证成功",
  "kami_type": "times",
  "authorization_owner": "device",
  "user_bind_mode": "none",
  "bound_user_id": null,
  "expire_time": null,
  "times_total": 3,
  "times_remaining": 3
}
```

`POST /api/v1/sdk/consume`

次数卡核销接口。该接口同样使用 SDK 加密请求格式，业务系统应在用户实际使用一次服务后调用；`verify` 只做校验和绑定，不代表已消费。

解密后的业务字段：

```json
{
  "kami": "TIMES3",
  "uuid": "device-001",
  "fingerprint": "hardware-fingerprint",
  "user_id": 123,
  "amount": 1,
  "biz_id": "order-or-request-id"
}
```

响应重点字段：

```json
{
  "success": true,
  "message": "核销成功",
  "kami_type": "times",
  "amount": 1,
  "times_total": 3,
  "times_remaining": 2
}
```

## 4. SDK：解绑卡密设备

`POST /api/v1/sdk/unbind`

该接口使用现有 SDK 加密请求格式。解密后的业务字段：

```json
{
  "kami": "DAYBOUND",
  "uuid": "device-001",
  "fingerprint": "hardware-fingerprint"
}
```

解绑策略由应用配置控制：

| 字段 | 说明 |
| --- | --- |
| `allow_unbind` | 是否允许解绑 |
| `max_unbind_count` | 最大解绑次数，0 表示不允许 |
| `unbind_cooldown_hours` | 两次解绑之间的冷却小时数 |
| `unbind_deduct_hours` | 时间卡解绑时扣减小时数 |
| `unbind_deduct_times` | 次数卡解绑时扣减次数 |
| `ip_lock_enabled` | 开启后解绑也校验绑定 IP |

响应示例：

```json
{
  "success": true,
  "message": "解绑成功",
  "unbind_count": 1,
  "expire_time": "2026-07-13T10:00:00+08:00",
  "times_remaining": null
}
```

## 5. SDK：获取应用配置

`GET /api/v1/sdk/apps/{app_id}/config`

响应示例：

```json
{
  "success": true,
  "data": {
    "app_id": "app_core",
    "name": "Core App",
    "notice_enabled": true,
    "notice_title": "公告标题",
    "notice": "公告内容...",
    "notice_level": "important",
    "notice_popup": true,
    "version": "1.0.0",
    "version_info": "修复已知问题",
    "force_update": true,
    "update_url": "https://example.com/download",
    "update_url_type": "external",
    "download_button_text": "立即下载",
    "files": [
      {
        "name": "Core App",
        "url": "https://example.com/client.zip",
        "type": "direct",
        "note": "Windows 客户端"
      }
    ],
    "security": {
      "signature_required": true,
      "nonce_required": true,
      "timestamp_tolerance_seconds": 300,
      "ip_lock_enabled": true,
      "allow_unbind": true,
      "max_unbind_count": 1,
      "unbind_cooldown_hours": 24,
      "unbind_deduct_hours": 2,
      "unbind_deduct_times": 1
    }
  }
}
```

## 6. 管理端：接口独立配置

应用公告、版本、文件外链、验证安全策略和解绑策略已统一迁移到接口独立配置中维护。

- `GET /api/v1/admin/apps/{app_id}/interfaces`
- `PUT /api/v1/admin/apps/{app_id}/interfaces/{interface_id}`

对应接口：

- `sdk.app_config`：公告、版本、更新地址、文件外链
- `sdk.verify`：签名、nonce、时间戳容差、IP 风控
- `sdk.unbind`：解绑开关、解绑次数、冷却时间、扣减规则

旧的 `/api/v1/admin/apps/{app_id}/core-config` 入口已移除，避免同一配置被两个入口同时修改。

## 7. 管理端：卡密列表/批次/导出增强字段

以下接口已返回新增字段：

- `GET /api/v1/admin/kamis`
- `GET /api/v1/admin/kamis/batches`
- `GET /api/v1/admin/kamis/export`

新增字段：

| 字段 | 说明 |
| --- | --- |
| `time_value` / `time_unit` | 时间卡面额 |
| `times_total` / `times_remaining` | 次数卡总次数和剩余次数 |
| `authorization_owner` | 授权归属策略 |
| `user_bind_mode` | 用户绑定策略 |
| `code_prefix` / `code_length` / `charset` | 生成规则 |
| `bind_ip` | 首次绑定 IP |
| `unbind_count` | 已解绑次数 |
| `last_unbind_at` | 最近解绑时间 |
| `last_verify_at` | 最近验证时间 |
