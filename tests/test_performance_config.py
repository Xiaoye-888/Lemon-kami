import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_admin_entry_does_not_block_on_external_cdn_scripts():
    index = read_text("admin/index.html")

    assert "cdnjs.cloudflare.com" not in index
    assert "http://" not in index
    assert "https://" not in index
    assert "jsencrypt.min.js" not in index


def test_frontend_nginx_compresses_and_caches_static_assets():
    nginx = read_text("admin/nginx.conf")

    assert "gzip on;" in nginx
    assert "gzip_types" in nginx
    assert "application/javascript" in nginx
    assert "text/css" in nginx
    assert "location ^~ /assets/" in nginx
    assert 'Cache-Control "public, max-age=31536000, immutable"' in nginx
    assert 'Cache-Control "no-cache, no-store, must-revalidate"' in nginx
    assert "proxy_buffering on;" in nginx
    assert "proxy_read_timeout 30s;" in nginx


def test_admin_api_client_has_timeout_and_retry_resilience():
    request_source = read_text("admin/src/utils/request.js")
    policy_source = read_text("admin/src/utils/requestPolicy.js")

    assert "const REQUEST_TIMEOUT" in request_source
    assert "DEFAULT_REQUEST_TIMEOUT_MS" in request_source
    assert "DEFAULT_REQUEST_TIMEOUT_MS = 12000" in policy_source
    assert "const REQUEST_RETRIES" in request_source
    assert "function isRetryableRequestError" in policy_source
    assert "!error.response" in policy_source
    assert "return !error.response" not in policy_source
    assert "setTimeout(resolve, REQUEST_RETRY_DELAY)" in request_source
    assert "请求超时，请稍后重试" in request_source


def test_fastapi_runtime_uses_configurable_multiple_workers():
    dockerfile = read_text("Dockerfile")
    compose = read_text("docker-compose.prod.yml")

    assert "UVICORN_WORKERS=2" in dockerfile
    assert "--workers ${UVICORN_WORKERS:-2}" in dockerfile
    assert "UVICORN_WORKERS: ${UVICORN_WORKERS:-2}" in compose


def test_database_pool_and_container_memory_are_bounded_for_small_host():
    database = read_text("database.py")
    config = read_text("config.py")
    compose = read_text("docker-compose.prod.yml")

    assert '"pool_size": settings.DB_POOL_SIZE' in database
    assert '"max_overflow": settings.DB_MAX_OVERFLOW' in database
    assert '"pool_timeout": settings.DB_POOL_TIMEOUT' in database
    assert '"pool_recycle": settings.DB_POOL_RECYCLE' in database
    assert "DB_POOL_SIZE: int = 5" in config
    assert "DB_MAX_OVERFLOW: int = 5" in config
    assert "DB_POOL_TIMEOUT: int = 10" in config
    assert "DB_POOL_RECYCLE: int = 1800" in config
    assert "mem_limit: 768m" in compose
    assert "mem_limit: 128m" in compose


def test_database_heavy_dashboards_run_in_fastapi_threadpool():
    admin_routes = read_text("routes_admin.py")
    merchant_routes = read_text("routes_merchant.py")

    assert "async def get_dashboard(" not in admin_routes
    assert "def get_dashboard(" in admin_routes
    assert "async def get_merchant_dashboard(" not in merchant_routes
    assert "def get_merchant_dashboard(" in merchant_routes


def test_card_pages_parallelize_independent_initial_requests():
    cards = read_text("admin/src/views/Kamis.vue")
    batches = read_text("admin/src/views/KamiBatches.vue")
    merchant_cards = read_text("admin/src/views/MerchantCards.vue")

    assert "await Promise.all([loadBatches(), getKamis(normalizeKamiParams())])" in cards
    assert "await Promise.all([loadSpecBatches(), loadDetailKamis({ refreshSummary: false })])" in batches
    assert "const loadDetailKamis = async ({ refreshSummary = false } = {}) =>" in batches
    assert merchant_cards.count("await Promise.all([loadBatchStats(), loadCards()])") >= 3
    assert "goGenerateKamis({ refreshBatches: false })" in merchant_cards


def test_sync_route_module_callables_do_not_run_on_async_event_loop():
    offenders = []

    for route_path in sorted(ROOT.glob("routes_*.py")):
        tree = ast.parse(route_path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            has_async_io = any(
                isinstance(child, (ast.Await, ast.AsyncFor, ast.AsyncWith))
                for child in ast.walk(node)
            )
            if not has_async_io:
                offenders.append(f"{route_path.name}:{node.lineno}:{node.name}")

    assert offenders == []


def test_paginated_endpoints_count_rows_in_sql_instead_of_loading_all_models():
    paths = [
        "routes_admin.py",
        "routes_commercial.py",
        "routes_docs.py",
        "routes_merchant.py",
        "routes_user.py",
        "commercial_service.py",
    ]
    offenders = []

    def is_materialized_query(node):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "all"
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Attribute)
            and node.func.value.func.attr == "exec"
        )

    for path in paths:
        tree = ast.parse(read_text(path).lstrip("\ufeff"))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for function in functions:
            materialized_names = set()
            for node in ast.walk(function):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if is_materialized_query(value):
                        materialized_names.update(
                            target.id for target in targets if isinstance(target, ast.Name)
                        )

            for node in ast.walk(function):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "len"
                    and node.args
                ):
                    continue
                argument = node.args[0]
                direct_materialization = is_materialized_query(argument)
                named_count_materialization = (
                    isinstance(argument, ast.Name)
                    and argument.id in materialized_names
                    and (
                        argument.id.startswith("count")
                        or argument.id.endswith("_count")
                        or "total" in argument.id
                    )
                )
                if direct_materialization or named_count_materialization:
                    offenders.append(f"{path}:{node.lineno}")

    assert offenders == []


def test_device_page_does_not_materialize_all_event_history():
    admin_routes = read_text("routes_admin.py")

    assert "def _latest_device_event_logs(" in admin_routes
    assert "func.max(EventLog.id).label(\"event_id\")" in admin_routes
    assert "select(EventLog.app_id, EventLog.device_uuid, EventLog.ip_address).distinct()" in admin_routes
    assert "logs = session.exec(log_statement.order_by(EventLog.created_at.desc())).all()" not in admin_routes


def test_destructive_paths_do_not_materialize_event_log_history():
    admin_routes = read_text("routes_admin.py")
    merchant_routes = read_text("routes_merchant.py")

    assert "event_logs = session.exec(select(EventLog)" not in admin_routes
    assert "event_logs = session.exec(select(EventLog)" not in merchant_routes
    assert "related_logs = session.exec(select(EventLog)" not in merchant_routes
    assert "kami_logs = session.exec(" not in admin_routes
    assert "payload_logs = session.exec(" not in admin_routes
    assert "EVENT_LOG_DELETE_BATCH_SIZE" in admin_routes


def test_points_pagination_does_not_load_full_tables_for_totals():
    admin_routes = read_text("routes_admin.py")
    user_routes = read_text("routes_user.py")

    assert "all_accounts = session.exec(select(UserPointAccount)).all()" not in admin_routes
    assert "all_items = session.exec(base).all()" not in user_routes
    assert "select(func.count(UserPointAccount.id))" in admin_routes
    assert "select(func.count(AuthorizationTransaction.id))" in user_routes


def test_sdk_consume_idempotency_lookup_is_bounded_and_column_only():
    sdk_routes = read_text("routes_sdk.py")

    assert "select(EventLog.payload)" in sdk_routes
    assert ".limit(CONSUME_IDEMPOTENCY_LOOKUP_LIMIT)" in sdk_routes
    assert "events = session.exec(" not in sdk_routes


def test_finance_dashboards_aggregate_in_sql_instead_of_loading_history():
    finance_service = read_text("finance_service.py")
    commercial_routes = read_text("routes_commercial.py")

    assert "session.exec(select(RechargeOrder)).all()" not in finance_service
    assert "session.exec(select(UserQuotaTransaction)).all()" not in finance_service
    assert "orders = session.exec(select(RechargeOrder)).all()" not in commercial_routes
    assert "func.sum(" in finance_service
    assert ".group_by(RechargeOrder.user_id, RechargeOrder.username)" in finance_service


def test_admin_spec_card_list_uses_database_pagination():
    admin_routes = read_text("routes_admin.py")

    assert "all_items = session.exec(statement.order_by(Kami.id.desc())).all()" not in admin_routes
    assert "select(func.count()).select_from(statement.order_by(None).subquery())" in admin_routes


def test_batch_stats_use_compact_composite_key_filter():
    query_service = read_text("kami_query_service.py")

    assert "tuple_(Kami.app_id, Kami.batch_no).in_(batch_pairs)" in query_service
    assert "pair_conditions = [" not in query_service


def test_card_summaries_aggregate_latest_consume_time_in_sql():
    admin_routes = read_text("routes_admin.py")

    assert "def _latest_event_at_by_kami(" in admin_routes
    assert "select(EventLog.kami_code, func.max(EventLog.created_at))" in admin_routes
    assert admin_routes.count("_latest_event_at_by_kami(") >= 3
    assert "consume_logs = session.exec(" not in admin_routes
