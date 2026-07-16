"""Baseline SQLModel schema.

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16
"""

from alembic import op
from sqlmodel import SQLModel

import models  # noqa: F401 - register SQLModel table metadata


revision = "20260716_0001"
down_revision = None
branch_labels = None
depends_on = None


CORE_TABLES = (
    "admin_users",
    "apps",
    "kamis",
    "kami_batches",
    "kami_device_bindings",
    "kami_consume_transactions",
    "devices",
    "event_logs",
    "app_authorizations",
    "api_interfaces",
    "app_interface_configs",
    "end_users",
    "user_point_accounts",
    "user_point_lots",
    "point_transactions",
    "authorization_accounts",
    "authorization_lots",
    "authorization_transactions",
)

CORE_CONSTRAINTS = (
    "uk_kami_batch_app_batch",
    "uk_kami_device_fingerprint",
    "uk_kami_consume_app_kami_biz",
    "uk_app_interface_config",
    "uk_point_tx_user_app_type_biz",
    "uk_authorization_account_owner",
    "uk_authorization_tx_account_type_biz",
)


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    for table in reversed(SQLModel.metadata.sorted_tables):
        op.drop_table(table.name)
