# Points System API

This document describes the user-bound points system added to Lemon Kami. Normal users do not need a standalone frontend page; business systems integrate through these APIs.

## Core Flow

1. Admin generates `points` kamis with custom face value and optional validity days.
2. End user registers or logs in through `/api/v1/user/*`.
3. End user redeems a points kami.
4. The system creates a point lot and a recharge transaction.
5. Business system calls the consume API with a unique `biz_id`.
6. Consumption deducts from available point lots by earliest expiration first.
7. Admin can query, export, or adjust points.

## Key Fields

- `kamis.points_amount`: custom points face value.
- `kamis.batch_no`: kami batch number; generated automatically if omitted.
- `kamis.points_valid_days`: validity days after redemption; `null` means permanent.
- `end_users.app_id`: optional owning application ID for app-level user management.
- `user_point_accounts.balance`: ledger balance.
- `user_point_lots.points_remaining`: remaining points in each recharge/adjust lot.
- `point_transactions.transaction_type`: `recharge`, `consume`, `adjust`.
- `point_transactions.biz_id`: business idempotency key.

## Authentication

End-user APIs use:

```http
Authorization: Bearer <end-user-jwt>
```

Admin APIs use:

```http
Authorization: Bearer <admin-jwt>
```

## End-User APIs

### Register

`POST /api/v1/user/register`

```json
{
  "app_id": "app_xxx",
  "username": "alice",
  "password": "secret123",
  "email": "alice@example.com",
  "phone": "13800000000"
}
```

`app_id` is optional. If provided, it must point to an enabled app. Returns a JWT token and user profile.

### Login

`POST /api/v1/user/login`

```json
{
  "username": "alice",
  "password": "secret123"
}
```

### Current User

`GET /api/v1/user/me`

### Query Balance

`GET /api/v1/user/points/balance`

```json
{
  "success": true,
  "data": {
    "user_id": 1,
    "balance": 155,
    "available_balance": 155,
    "ledger_balance": 200,
    "expired_unsettled": 45,
    "total_recharged": 200,
    "total_consumed": 45
  }
}
```

Notes:

- `balance` and `available_balance` are the currently usable points.
- `ledger_balance` is the account ledger balance.
- `expired_unsettled` is the sum of expired lots that have not been manually settled.

### Redeem Points Kami

`POST /api/v1/user/points/redeem`

```json
{
  "kami_code": "POINTS200"
}
```

```json
{
  "success": true,
  "message": "redeem success",
  "data": {
    "transaction_id": "pt_xxx",
    "amount": 200,
    "balance": 200
  }
}
```

Rules:

- Kami must exist.
- Kami type must be `points`.
- Kami status must be `unused`.
- Kami must not be frozen.
- Kami must have `points_amount > 0`.
- A redeemed points kami cannot be redeemed again.

### Consume Points

`POST /api/v1/user/points/consume`

```json
{
  "app_id": "app_xxx",
  "amount": 45,
  "biz_id": "order-20260712-0001",
  "remark": "purchase feature",
  "metadata": {
    "sku": "feature-a"
  }
}
```

`app_id` is optional. If omitted, the user's registered `app_id` is used when available.

```json
{
  "success": true,
  "message": "consume success",
  "data": {
    "transaction_id": "pt_xxx",
    "amount": 45,
    "balance": 155,
    "idempotent": false
  }
}
```

Idempotency:

- Same `biz_id` and same `amount` returns the original transaction and does not deduct again.
- Same `biz_id` with a different `amount` returns `biz_id_conflict`.

Deduction order:

- Non-expired lots are sorted by earliest `expires_at`.
- Permanent lots are consumed after expiring lots.

### Query My Point Lots

`GET /api/v1/user/points/lots?only_available=true`

Returns current user's point lots, remaining points, and expiration time.

### Query My Transactions

`GET /api/v1/user/points/transactions?page=1&page_size=20`

Returns recharge, consume, and adjustment transactions for the current user.

## Admin APIs

### Generate Points Kami

`POST /api/v1/admin/kamis/batch`

Query params:

- `app_id`: application ID.
- `kami_type=points`.
- `count`: number of kamis, 1 to 1000.
- `points_amount`: custom face value, required for points kamis.
- `batch_no`: optional batch number; auto-generated if omitted.
- `points_valid_days`: optional validity days after redemption; omitted means permanent.
- `token`: admin JWT.

Example:

```http
POST /api/v1/admin/kamis/batch?app_id=app_xxx&kami_type=points&count=10&points_amount=100&batch_no=batch_20260712&points_valid_days=30&token=admin-jwt
```

Response includes `batch_no`, `points_amount`, `points_valid_days`, and generated codes.

### Kami List

`GET /api/v1/admin/kamis?app_id=app_xxx&page=1&page_size=20`

Optional filters:

- `status`: `unused`, `active`, or `frozen`.
- `batch_no`: show cards from a single batch.

Each item includes:

- `points_amount`
- `batch_no`
- `points_valid_days`
- `redeemed_by_user_id`
- `redeemed_at`

### Kami Batch Summary

`GET /api/v1/admin/kamis/batches?app_id=app_xxx`

Returns per-batch totals:

- `total_count`
- `unused_count`
- `active_count`
- `frozen_count`
- `redeemed_count`

### Export Kamis

`GET /api/v1/admin/kamis/export?app_id=app_xxx`

Optional filters:

- `status`
- `kami_type`
- `batch_no`

Returns CSV.

### Delete Selected Kamis

`POST /api/v1/admin/kamis/delete`

```json
{
  "app_id": "app_xxx",
  "batch_no": "batch_20260712",
  "kami_codes": ["KAMI-1", "KAMI-2"]
}
```

Rules:

- `batch_no` is optional, but recommended when deleting from a batch detail view.
- Only unused or never-bound frozen kamis are deleted.
- Active, redeemed, or device-bound kamis are skipped and returned in `data.skipped`.

### End-User Stats

`GET /api/v1/admin/end-users/stats?app_id=app_xxx`

Optional filters:

- `app_id`: returns stats for users registered under the app or legacy users with point transactions in the app.

Returns total users, new users today, active users, disabled users, users with balance, and total balance.

### End-User List

`GET /api/v1/admin/end-users?page=1&page_size=20&app_id=app_xxx`

Optional filters:

- `keyword`
- `app_id`
- `status`

### Export End Users

`GET /api/v1/admin/end-users/export`

Optional filters:

- `keyword`
- `app_id`
- `status`

Returns CSV.

### Update End-User Status

`PUT /api/v1/admin/end-users/{user_id}/status?status=0`

Use `status=1` to enable and `status=0` to disable.

### Reset End-User Password

`PUT /api/v1/admin/end-users/{user_id}/password`

```json
{
  "password": "newSecret123"
}
```

### Point Accounts

`GET /api/v1/admin/points/accounts?page=1&page_size=20`

### Point Lots

`GET /api/v1/admin/points/lots?page=1&page_size=20`

Optional filters:

- `user_id`
- `only_available=true`

### Point Transactions

`GET /api/v1/admin/points/transactions?page=1&page_size=20`

Optional filters:

- `user_id`
- `transaction_type`: `recharge`, `consume`, or `adjust`

### Export Point Transactions

`GET /api/v1/admin/points/transactions/export`

Optional filters:

- `user_id`
- `transaction_type`

Returns CSV.

### Admin Adjustment

`POST /api/v1/admin/points/adjust`

```json
{
  "user_id": 1,
  "amount": 50,
  "biz_id": "manual-adjust-1",
  "remark": "support compensation",
  "metadata": {
    "ticket": "T-1001"
  }
}
```

Use a negative `amount` to deduct points. The system rejects adjustments that would make the balance negative.

## Error Codes

Point service errors are returned in FastAPI `detail`:

```json
{
  "detail": {
    "code": "insufficient_balance",
    "message": "Insufficient points balance"
  }
}
```

Common codes:

- `kami_not_found`
- `not_points_kami`
- `kami_frozen`
- `already_redeemed`
- `invalid_points_amount`
- `invalid_amount`
- `missing_biz_id`
- `biz_id_conflict`
- `insufficient_balance`
