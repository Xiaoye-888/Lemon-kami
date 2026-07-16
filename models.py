from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum
from sqlalchemy import UniqueConstraint

# 中国时区
CST = ZoneInfo("Asia/Shanghai")

def get_now():
    """获取当前中国时间（带时区）"""
    return datetime.now(CST)


def get_now_naive():
    """获取当前中国时间（naive，不带时区信息，用于存入数据库）"""
    return datetime.now(CST).replace(tzinfo=None)


class KamiType(str, Enum):
    hour = "hour"
    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"
    lifetime = "lifetime"
    points = "points"
    times = "times"  # 次数卡


class AdminRole(str, Enum):
    super_admin = "super_admin"
    admin = "admin"
    operator = "operator"
    auditor = "auditor"


class PointTransactionType(str, Enum):
    recharge = "recharge"
    consume = "consume"
    adjust = "adjust"


class AuthorizationOwnerType(str, Enum):
    user = "user"
    device = "device"


class AuthorizationOwnerMode(str, Enum):
    device = "device"
    user = "user"
    auto = "auto"


class UserBindMode(str, Enum):
    none = "none"
    auto = "auto"
    optional = "optional"
    required = "required"


class AuthorizationBenefitType(str, Enum):
    time = "time"
    times = "times"
    points = "points"


class AuthorizationTransactionType(str, Enum):
    redeem = "redeem"
    grant = "grant"
    consume = "consume"
    adjust = "adjust"
    expire = "expire"


class KamiStatus(str, Enum):
    unused = "unused"
    active = "active"
    frozen = "frozen"


class MachineBindMode(str, Enum):
    no_limit = "no_limit"
    one_card_one_device = "one_card_one_device"
    one_card_multi_device = "one_card_multi_device"


class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, description="用户名")
    password_hash: str = Field(description="密码哈希")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, description="手机号")
    is_admin: bool = Field(default=False, description="是否为超级管理员")
    role: AdminRole = Field(default=AdminRole.operator, index=True, description="RBAC role")
    status: int = Field(default=1, description="状态：1启用，0禁用")
    created_at: datetime = Field(default_factory=get_now_naive, description="创建时间")
    last_login: Optional[datetime] = Field(default=None, description="最后登录时间")
    failed_attempts: int = Field(default=0, description="连续失败次数")
    locked_until: Optional[datetime] = Field(default=None, description="锁定到期时间")


class EndUser(SQLModel, table=True):
    __tablename__ = "end_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: Optional[str] = Field(default=None, max_length=64, index=True, description="Owning app ID")
    username: str = Field(unique=True, index=True, description="End-user username")
    password_hash: str = Field(description="Password hash")
    email: Optional[str] = Field(default=None, index=True, description="Email")
    phone: Optional[str] = Field(default=None, description="Phone")
    status: int = Field(default=1, index=True, description="1 active, 0 disabled")
    created_at: datetime = Field(default_factory=get_now_naive, description="Created time")
    last_login: Optional[datetime] = Field(default=None, description="Last login time")


class UserPointAccount(SQLModel, table=True):
    __tablename__ = "user_point_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True, description="End-user ID")
    balance: int = Field(default=0, description="Current points balance")
    total_recharged: int = Field(default=0, description="Total recharged points")
    total_consumed: int = Field(default=0, description="Total consumed points")
    created_at: datetime = Field(default_factory=get_now_naive, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class PointTransaction(SQLModel, table=True):
    __tablename__ = "point_transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "app_id", "transaction_type", "biz_id", name="uk_point_tx_user_app_type_biz"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(unique=True, index=True, description="Public transaction ID")
    user_id: int = Field(index=True, description="End-user ID")
    app_id: Optional[str] = Field(default=None, max_length=64, index=True, description="App ID")
    kami_code: Optional[str] = Field(default=None, index=True, description="Redeemed kami code")
    transaction_type: PointTransactionType = Field(index=True, description="Transaction type")
    amount: int = Field(description="Signed points delta")
    balance_before: int = Field(description="Balance before transaction")
    balance_after: int = Field(description="Balance after transaction")
    biz_id: Optional[str] = Field(default=None, index=True, description="Caller business ID")
    remark: Optional[str] = Field(default=None, description="Remark")
    metadata_json: Optional[str] = Field(default=None, description="JSON metadata")
    operator: Optional[str] = Field(default=None, description="Admin operator")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")


class UserPointLot(SQLModel, table=True):
    __tablename__ = "user_point_lots"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, description="End-user ID")
    source_transaction_id: str = Field(unique=True, index=True, description="Source transaction ID")
    app_id: Optional[str] = Field(default=None, max_length=64, index=True, description="App ID")
    kami_code: Optional[str] = Field(default=None, index=True, description="Source kami code")
    points_total: int = Field(description="Total points in this lot")
    points_remaining: int = Field(default=0, index=True, description="Remaining points in this lot")
    expires_at: Optional[datetime] = Field(default=None, index=True, description="Expiration time")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class AuthorizationAccount(SQLModel, table=True):
    __tablename__ = "authorization_accounts"
    __table_args__ = (
        UniqueConstraint("app_id", "owner_type", "owner_key", name="uk_authorization_account_owner"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, index=True, description="App ID")
    owner_type: AuthorizationOwnerType = Field(index=True, description="Authorization owner type")
    owner_key: str = Field(default="", max_length=512, index=True, description="Stable owner identity key")
    user_id: Optional[int] = Field(default=None, index=True, description="End-user ID")
    username: Optional[str] = Field(default=None, max_length=64, index=True, description="End-user username")
    device_uuid: Optional[str] = Field(default=None, max_length=255, index=True, description="Device UUID")
    fingerprint: Optional[str] = Field(default=None, index=True, description="Device fingerprint")
    time_expires_at: Optional[datetime] = Field(default=None, index=True, description="Time authorization expiry")
    is_lifetime: bool = Field(default=False, description="Whether time authorization is permanent")
    times_balance: int = Field(default=0, description="Remaining times authorization")
    points_balance: int = Field(default=0, description="Remaining points authorization")
    status: int = Field(default=1, index=True, description="1 active, 0 disabled")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class AuthorizationLot(SQLModel, table=True):
    __tablename__ = "authorization_lots"

    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="authorization_accounts.id", index=True, description="Authorization account ID")
    source_kami_code: Optional[str] = Field(default=None, max_length=255, index=True, description="Source kami code")
    benefit_type: AuthorizationBenefitType = Field(index=True, description="Benefit type")
    amount_total: int = Field(description="Total amount in this lot")
    amount_remaining: int = Field(default=0, index=True, description="Remaining amount in this lot")
    starts_at: Optional[datetime] = Field(default=None, description="Time benefit start")
    expires_at: Optional[datetime] = Field(default=None, index=True, description="Lot expiration")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class AuthorizationTransaction(SQLModel, table=True):
    __tablename__ = "authorization_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "transaction_type", "biz_id", name="uk_authorization_tx_account_type_biz"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(unique=True, index=True, description="Public transaction ID")
    account_id: int = Field(foreign_key="authorization_accounts.id", index=True, description="Authorization account ID")
    source_kami_code: Optional[str] = Field(default=None, max_length=255, index=True, description="Source kami code")
    transaction_type: AuthorizationTransactionType = Field(index=True, description="Transaction type")
    benefit_type: AuthorizationBenefitType = Field(index=True, description="Benefit type")
    amount: int = Field(description="Signed benefit delta")
    balance_after: int = Field(description="Balance after transaction")
    biz_id: Optional[str] = Field(default=None, max_length=128, index=True, description="Business idempotency key")
    operator: Optional[str] = Field(default=None, max_length=255, description="Admin operator")
    metadata_json: Optional[str] = Field(default=None, description="JSON metadata")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")


class App(SQLModel, table=True):
    __tablename__ = "apps"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, unique=True, index=True, description="应用唯一标识")
    name: str = Field(description="应用名称")
    app_secret: str = Field(description="用于签名验证的密钥")
    rsa_public_key: str = Field(description="平台RSA公钥")
    rsa_private_key: str = Field(description="平台RSA私钥")
    status: int = Field(default=1, description="启停状态：1启用，0禁用")
    created_by: Optional[str] = Field(default=None, description="创建人用户名")
    created_at: datetime = Field(default_factory=get_now_naive, description="创建时间")
    notice_enabled: bool = Field(default=False, description="Whether SDK clients should show notice")
    notice_title: Optional[str] = Field(default=None, max_length=128, description="Notice title")
    notice: Optional[str] = Field(default=None, description="App notice shown to SDK clients")
    notice_level: str = Field(default="normal", max_length=32, description="Notice level")
    notice_popup: bool = Field(default=False, description="Whether SDK clients should show notice popup")
    version: Optional[str] = Field(default=None, max_length=64, description="Latest app version")
    version_info: Optional[str] = Field(default=None, description="Version/update notes")
    force_update: bool = Field(default=False, description="Whether SDK clients must update")
    update_url: Optional[str] = Field(default=None, description="App update URL")
    update_url_type: Optional[str] = Field(default="direct", max_length=32, description="Update URL type")
    download_url: Optional[str] = Field(default=None, description="Optional app file/download URL")
    download_note: Optional[str] = Field(default=None, description="Optional download note")
    download_button_text: Optional[str] = Field(default="立即下载", max_length=64, description="Download button label")
    signature_required: bool = Field(default=True, description="Require signed SDK requests")
    nonce_required: bool = Field(default=True, description="Require nonce replay protection")
    timestamp_tolerance_seconds: int = Field(default=300, description="SDK timestamp tolerance")
    allow_unbind: bool = Field(default=False, description="Allow users to unbind devices")
    max_unbind_count: int = Field(default=0, description="Maximum unbind count, 0 means disabled")
    unbind_cooldown_hours: int = Field(default=24, description="Hours between unbind operations")
    unbind_deduct_hours: int = Field(default=0, description="Hours deducted from time cards on unbind")
    unbind_deduct_times: int = Field(default=0, description="Times deducted from times cards on unbind")
    ip_lock_enabled: bool = Field(default=False, description="Bind kami to first activation IP")
    api_call_count: int = Field(default=0, description="SDK verify call counter")

    # 关系
    kamis: List["Kami"] = Relationship(
        back_populates="app",
        sa_relationship_kwargs={"passive_deletes": True},
    )
    devices: List["Device"] = Relationship(
        back_populates="app",
        sa_relationship_kwargs={"passive_deletes": True},
    )


class Kami(SQLModel, table=True):
    __tablename__ = "kamis"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="所属应用ID")
    kami_code: str = Field(unique=True, index=True, description="卡密代码")
    kami_type: KamiType = Field(description="卡密类型")
    status: KamiStatus = Field(default=KamiStatus.unused, description="卡密状态")
    bind_uuid: Optional[str] = Field(default=None, description="绑定的设备UUID")
    activate_time: Optional[datetime] = Field(default=None, description="激活时间")
    expire_time: Optional[datetime] = Field(default=None, description="到期时间")
    points_amount: Optional[int] = Field(default=None, description="Points face value")
    batch_no: Optional[str] = Field(default=None, max_length=64, index=True, description="Kami batch number")
    points_valid_days: Optional[int] = Field(default=None, description="Points validity days after redeem")
    redeemed_by_user_id: Optional[int] = Field(default=None, index=True, description="Redeeming end-user ID")
    redeemed_at: Optional[datetime] = Field(default=None, description="Redeemed time")
    time_value: Optional[int] = Field(default=None, description="Time-card duration value")
    time_unit: Optional[str] = Field(default=None, max_length=32, description="Time-card duration unit")
    times_total: Optional[int] = Field(default=None, description="Total allowed uses for times cards")
    times_remaining: Optional[int] = Field(default=None, index=True, description="Remaining uses for times cards")
    code_prefix: Optional[str] = Field(default=None, max_length=32, description="Generation prefix")
    code_length: Optional[int] = Field(default=None, description="Random suffix length")
    charset: Optional[str] = Field(default=None, max_length=32, description="Generation charset")
    bind_ip: Optional[str] = Field(default=None, description="Bound activation IP")
    unbind_count: int = Field(default=0, description="Device unbind count")
    last_unbind_at: Optional[datetime] = Field(default=None, description="Last unbind time")
    last_verify_at: Optional[datetime] = Field(default=None, description="Last successful verify time")
    machine_bind_mode: MachineBindMode = Field(
        default=MachineBindMode.one_card_one_device,
        index=True,
        description="Machine binding mode",
    )
    max_bind_devices: int = Field(default=1, description="Max bound devices, 0 means unlimited")
    authorization_owner: AuthorizationOwnerMode = Field(
        default=AuthorizationOwnerMode.device,
        index=True,
        description="Authorization owner strategy",
    )
    user_bind_mode: UserBindMode = Field(
        default=UserBindMode.none,
        index=True,
        description="User binding policy",
    )
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")

    # 关系
    app: Optional[App] = Relationship(back_populates="kamis")
    event_logs: List["EventLog"] = Relationship(
        back_populates="kami",
        sa_relationship_kwargs={"passive_deletes": True},
    )


class KamiBatch(SQLModel, table=True):
    __tablename__ = "kami_batches"
    __table_args__ = (
        UniqueConstraint("app_id", "batch_no", name="uk_kami_batch_app_batch"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="App ID")
    batch_no: str = Field(max_length=64, index=True, description="Batch number")
    kami_type: KamiType = Field(index=True, description="Kami type")
    points_amount: Optional[int] = Field(default=None, description="Points face value")
    points_valid_days: Optional[int] = Field(default=None, description="Points validity days after redeem")
    time_value: Optional[int] = Field(default=None, description="Time-card duration value")
    time_unit: Optional[str] = Field(default=None, max_length=32, description="Time-card duration unit")
    times_total: Optional[int] = Field(default=None, description="Total allowed uses for times cards")
    code_prefix: Optional[str] = Field(default=None, max_length=32, description="Generation prefix")
    code_length: int = Field(default=16, description="Random suffix length")
    charset: str = Field(default="upper_numeric", max_length=32, description="Generation charset")
    machine_bind_mode: MachineBindMode = Field(
        default=MachineBindMode.one_card_one_device,
        index=True,
        description="Machine binding mode",
    )
    max_bind_devices: int = Field(default=1, description="Max bound devices, 0 means unlimited")
    authorization_owner: AuthorizationOwnerMode = Field(
        default=AuthorizationOwnerMode.device,
        index=True,
        description="Authorization owner strategy",
    )
    user_bind_mode: UserBindMode = Field(
        default=UserBindMode.none,
        index=True,
        description="User binding policy",
    )
    status: int = Field(default=1, index=True, description="1 enabled, 0 disabled")
    remark: Optional[str] = Field(default=None, description="Admin remark")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class KamiDeviceBinding(SQLModel, table=True):
    __tablename__ = "kami_device_bindings"
    __table_args__ = (
        UniqueConstraint("kami_code", "fingerprint", name="uk_kami_device_fingerprint"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="所属应用ID")
    kami_code: str = Field(foreign_key="kamis.kami_code", index=True, description="卡密代码")
    device_uuid: str = Field(index=True, description="设备UUID")
    fingerprint: str = Field(index=True, description="设备指纹")
    bind_ip: Optional[str] = Field(default=None, description="绑定IP")
    first_bind_at: datetime = Field(default_factory=get_now_naive, description="首次绑定时间")
    last_verify_at: datetime = Field(default_factory=get_now_naive, description="最近验证时间")


class KamiConsumeTransaction(SQLModel, table=True):
    __tablename__ = "kami_consume_transactions"
    __table_args__ = (
        UniqueConstraint("app_id", "kami_code", "biz_id", name="uk_kami_consume_app_kami_biz"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    consume_id: str = Field(unique=True, index=True, max_length=64, description="Public consume transaction ID")
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="App ID")
    kami_code: str = Field(foreign_key="kamis.kami_code", index=True, description="Kami code")
    biz_id: str = Field(max_length=128, index=True, description="Caller idempotency key")
    amount: int = Field(description="Consumed times amount")
    times_total: Optional[int] = Field(default=None, description="Times card total")
    times_remaining: Optional[int] = Field(default=None, index=True, description="Remaining times after consume")
    device_uuid: Optional[str] = Field(default=None, max_length=255, index=True, description="Device UUID")
    fingerprint: Optional[str] = Field(default=None, index=True, description="Device fingerprint")
    ip_address: Optional[str] = Field(default=None, max_length=255, description="Client IP")
    payload_json: Optional[str] = Field(default=None, description="Stable response payload JSON")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="Created time")


class Device(SQLModel, table=True):
    __tablename__ = "devices"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="所属应用ID")
    uuid: str = Field(index=True, description="设备UUID")
    fingerprint: str = Field(description="硬件特征码")
    last_ip: Optional[str] = Field(default=None, description="最后登录IP")
    risk_level: int = Field(default=0, description="风险等级：0正常，1警告，2黑名单")

    # 关系
    app: Optional[App] = Relationship(back_populates="devices")


class EventLog(SQLModel, table=True):
    __tablename__ = "event_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: Optional[str] = Field(default=None, max_length=64, index=True, description="所属应用ID（管理员登录为None）")
    kami_code: Optional[str] = Field(default=None, foreign_key="kamis.kami_code", index=True, description="关联卡密")
    event_type: str = Field(index=True, description="事件类型：login/activate/verify/heartbeat/admin_login")
    ip_address: Optional[str] = Field(default=None, description="IP地址")
    device_uuid: Optional[str] = Field(default=None, description="设备UUID")
    user_agent: Optional[str] = Field(default=None, description="User-Agent")
    payload: Optional[str] = Field(default=None, description="扩展业务数据(JSON字符串)")
    status: int = Field(default=1, description="状态：1成功，0失败")
    message: Optional[str] = Field(default=None, description="消息描述")
    created_at: datetime = Field(default_factory=get_now_naive, index=True, description="创建时间")

    # 关系
    kami: Optional[Kami] = Relationship(
        back_populates="event_logs",
        sa_relationship_kwargs={"lazy": "noload"},
    )


class AppAuthorization(SQLModel, table=True):
    """应用授权表：记录谁被授权管理哪个应用"""
    __tablename__ = "app_authorizations"

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="应用ID")
    username: str = Field(index=True, description="被授权的用户名")
    granted_by: str = Field(description="授权人用户名")
    created_at: datetime = Field(default_factory=get_now_naive, description="授权时间")


class ApiInterface(SQLModel, table=True):
    __tablename__ = "api_interfaces"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="Interface display name")
    interface_key: str = Field(unique=True, index=True, max_length=128, description="Stable interface key")
    method: str = Field(default="POST", max_length=16, description="HTTP method")
    path: str = Field(index=True, description="Interface path")
    category: Optional[str] = Field(default="core", max_length=64, index=True, description="Interface category")
    description: Optional[str] = Field(default=None, description="Interface description")
    auth_mode: Optional[str] = Field(default="bearer", max_length=64, description="Authentication mode")
    content_type: Optional[str] = Field(default="application/json", max_length=128, description="Request content type")
    status: int = Field(default=1, index=True, description="1 enabled, 0 disabled")
    request_headers_json: Optional[str] = Field(default=None, description="JSON request header schema")
    request_params_json: Optional[str] = Field(default=None, description="JSON request parameter schema")
    response_params_json: Optional[str] = Field(default=None, description="JSON response parameter schema")
    success_example_json: Optional[str] = Field(default=None, description="JSON success response example")
    error_example_json: Optional[str] = Field(default=None, description="JSON error response example")
    response_example_json: Optional[str] = Field(default=None, description="JSON response example")
    doc_markdown: Optional[str] = Field(default=None, description="Markdown API documentation")
    remark: Optional[str] = Field(default=None, description="Admin remark")
    sort_order: int = Field(default=0, index=True, description="Display sort order")
    is_builtin: bool = Field(default=False, index=True, description="Whether this is a built-in interface")
    created_at: datetime = Field(default_factory=get_now_naive, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")


class AppInterfaceConfig(SQLModel, table=True):
    __tablename__ = "app_interface_configs"
    __table_args__ = (
        UniqueConstraint("app_id", "interface_id", name="uk_app_interface_config"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="App ID")
    interface_id: int = Field(foreign_key="api_interfaces.id", index=True, description="API interface ID")
    enabled: bool = Field(default=False, index=True, description="Whether interface is enabled for app")
    quota_limit: Optional[int] = Field(default=None, description="Optional call quota")
    expires_at: Optional[datetime] = Field(default=None, index=True, description="Optional expiration time")
    config_json: Optional[str] = Field(default=None, description="JSON per-app interface config")
    remark: Optional[str] = Field(default=None, description="Admin remark")
    created_at: datetime = Field(default_factory=get_now_naive, description="Created time")
    updated_at: datetime = Field(default_factory=get_now_naive, description="Updated time")
