# User Points System Design

## Goal

Add a normal end-user account system and a complete points system. Admins generate points kamis with custom face values. End users register, log in, redeem points kamis into their own balance, spend points through an idempotent consume API, and inspect their own transaction history.

## Scope

- End-user registration and login are separate from existing admin accounts.
- Points balance belongs to an end user, not to a kami.
- A `points` kami is a recharge voucher with a custom positive integer face value.
- Each points kami can be redeemed once.
- Every balance change creates a transaction row.
- Admins can see end-user counts, user lists, point accounts, all transactions, and can manually adjust balances.

## Data Model

- `end_users`: normal user credentials and profile fields.
- `user_point_accounts`: one points account per end user with balance, total recharge, and total consumption counters.
- `point_transactions`: immutable ledger rows for recharge, consume, and admin adjust operations.
- `kamis`: gains `points_amount`, `redeemed_by_user_id`, and `redeemed_at` columns.

## API Design

User APIs use `/api/v1/user`:

- `POST /register`
- `POST /login`
- `GET /me`
- `GET /points/balance`
- `POST /points/redeem`
- `POST /points/consume`
- `GET /points/transactions`

Admin APIs extend `/api/v1/admin`:

- `GET /end-users/stats`
- `GET /end-users`
- `PUT /end-users/{user_id}/status`
- `GET /points/accounts`
- `GET /points/transactions`
- `POST /points/adjust`

Existing `POST /api/v1/admin/kamis/batch` accepts `points_amount` when `kami_type=points`.

## Rules

- `points_amount` is required and must be greater than zero for points kamis.
- Redeem rejects missing, frozen, non-points, zero-face-value, or already redeemed kamis.
- Redeem marks the kami as active and records the redeeming user.
- Consume requires a positive amount and a caller-supplied `biz_id`.
- Reusing the same `biz_id` with the same amount returns the existing transaction without charging again.
- Reusing the same `biz_id` with a different amount is rejected.
- Balance changes and transaction writes happen in the same database transaction.
- Admin adjustments may be positive or negative, but cannot make balance negative.

## Frontend

Admin UI adds:

- End-user management page with total/new/active/disabled counts.
- Points page with point account list, transaction list, and manual adjustment dialog.
- Kami generation dialog shows custom face value input for points kamis.

## Testing

Service-level tests cover redeem, duplicate redeem, consume, idempotency, conflicting idempotency, and insufficient balance. Build verification covers backend import/compile and the Vue production build.
