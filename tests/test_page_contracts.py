from pathlib import Path
import importlib.util
import re

from scripts import page_contracts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROUTER_SOURCE = PROJECT_ROOT / "admin/src/router/index.js"
PRODUCTION_QA_SOURCE = PROJECT_ROOT / "scripts/production_e2e_browser_qa.py"


def _read_contract_source(contract):
    source_path = PROJECT_ROOT / contract["source"]
    assert source_path.exists(), f"{contract['id']} source file is missing: {source_path}"
    return source_path.read_text(encoding="utf-8")


def _assert_tokens_in_order(source, tokens, contract_id, group_name):
    cursor = 0
    for token in tokens:
        index = source.find(token, cursor)
        assert index != -1, f"{contract_id}.{group_name} missing or misordered token: {token}"
        cursor = index + len(token)


def _load_production_qa_module():
    spec = importlib.util.spec_from_file_location("production_e2e_browser_qa", PRODUCTION_QA_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_route(route):
    route = route.split("?", 1)[0]
    route = re.sub(r"/<[^/]+>", "/:param", route)
    route = re.sub(r"/:[^/]+", "/:param", route)
    return route.rstrip("/") or "/"


def _component_routes_from_router():
    source = ROUTER_SOURCE.read_text(encoding="utf-8")
    route_map = {}
    sections = {
        "admin": source.split("const adminChildren = [", 1)[1].split("const merchantChildren = [", 1)[0],
        "merchant": source.split("const merchantChildren = [", 1)[1].split("const legacyAdminRedirects", 1)[0],
    }

    for role, section in sections.items():
        prefix = f"/{role}"
        for match in re.finditer(r"\{\s*path: '([^']+)',\s*name: '([^']+)'[^{}]*component:", section):
            path, name = match.groups()
            if name.startswith("AdminAccount"):
                full_path = f"/admin/account/{path}"
            elif name.startswith("MerchantAccount"):
                full_path = f"/merchant/account/{path}"
            else:
                full_path = f"{prefix}/{path}"
            route_map[_normalize_route(full_path)] = role

    public_routes = {
        "/login": "public",
        "/404": "public",
        "/docs/api": "public",
    }
    route_map.update(public_routes)
    return route_map


def _contract_route_map():
    return {
        _normalize_route(contract["route"]): contract["id"]
        for contract in page_contracts.PAGE_CONTRACTS
        if contract["id"].split(".", 1)[0] != "layout"
    }


def test_page_contract_registry_covers_primary_admin_and_merchant_surfaces():
    contract_ids = {contract["id"] for contract in page_contracts.PAGE_CONTRACTS}

    assert {
        "layout.admin.navigation",
        "layout.merchant.navigation",
        "merchant.dashboard",
        "merchant.recharge",
        "merchant.orders",
        "merchant.transactions",
        "merchant.apps",
        "merchant.notices",
        "merchant.versions",
        "merchant.batches.list",
        "merchant.batches.detail",
        "merchant.cards",
        "merchant.devices",
        "merchant.account.profile",
        "merchant.account.password",
        "admin.account.profile",
        "admin.account.password",
        "admin.batches.list",
        "admin.batches.detail",
        "admin.merchants",
        "admin.merchants.detail",
        "admin.merchants.scoped_batches",
        "admin.recharge_orders",
        "admin.devices",
        "admin.dashboard",
        "admin.commercial_overview",
        "admin.recharge_settings",
        "admin.issue_pricing",
        "admin.finance",
        "admin.audit_logs",
        "admin.ops",
        "admin.quota_transactions",
        "admin.apps.info",
        "admin.apps.notices",
        "admin.apps.versions",
        "admin.apps.interfaces",
        "admin.kamis.list",
        "admin.logs",
        "admin.users",
        "admin.end_users",
        "admin.interfaces.new",
        "admin.interfaces.list",
        "public.login",
        "public.docs.api",
        "public.not_found",
    }.issubset(contract_ids)

    for contract in page_contracts.PAGE_CONTRACTS:
        assert contract["role"] in {"admin", "merchant", "public", "shared"}
        assert contract["source"]
        assert contract["regions"], f"{contract['id']} must declare functional regions"


def test_vue_component_routes_have_page_contracts():
    router_routes = _component_routes_from_router()
    contract_routes = _contract_route_map()

    missing = {
        route: role
        for route, role in router_routes.items()
        if route not in contract_routes
    }

    assert missing == {}, f"router routes missing page contracts: {missing}"


def test_static_component_routes_are_in_production_browser_sweep():
    production_qa = _load_production_qa_module()
    route_groups = production_qa.browser_routes()
    browser_routes = {route for routes in route_groups.values() for route in routes}

    router_routes = _component_routes_from_router()
    dynamic_routes = {route for route in router_routes if ":param" in route}
    expected_static_routes = {
        route
        for route in router_routes
        if route not in dynamic_routes and route not in {"/404"}
    }
    expected_static_routes.add("/interface-docs")

    missing = sorted(expected_static_routes - browser_routes)
    assert missing == [], f"static routes missing from production browser sweep: {missing}"


def test_page_contracts_validate_regions_cards_tables_and_action_order():
    for contract in page_contracts.PAGE_CONTRACTS:
        source = _read_contract_source(contract)

        for region in contract.get("regions", []):
            assert region["selector_token"] in source, f"{contract['id']} missing region {region['id']}"

        _assert_tokens_in_order(
            source,
            [region["selector_token"] for region in contract.get("ordered_regions", [])],
            contract["id"],
            "ordered_regions",
        )

        for card_group in contract.get("card_groups", []):
            _assert_tokens_in_order(source, card_group["tokens"], contract["id"], card_group["id"])

        for table in contract.get("tables", []):
            _assert_tokens_in_order(source, table["columns"], contract["id"], table["id"])

        for action_group in contract.get("action_groups", []):
            _assert_tokens_in_order(source, action_group["tokens"], contract["id"], action_group["id"])

        for token in contract.get("forbidden_tokens", []):
            assert token not in source, f"{contract['id']} should not contain forbidden token: {token}"


def test_page_contracts_pin_role_permission_boundaries_to_existing_tests():
    existing_test_files = "\n".join(
        path.read_text(encoding="utf-8") for path in (PROJECT_ROOT / "tests").glob("test_*.py")
    )

    required_boundaries = {
        "merchant_self_owned_app",
        "merchant_authorized_app",
        "merchant_app_content_management",
        "merchant_authorized_batches_not_synced",
        "merchant_device_scope",
        "application_user_cannot_manage_quota",
        "admin_only_commercial_routes",
    }
    boundary_ids = {boundary["id"] for boundary in page_contracts.ROLE_PERMISSION_CONTRACTS}

    assert required_boundaries.issubset(boundary_ids)
    for boundary in page_contracts.ROLE_PERMISSION_CONTRACTS:
        assert boundary["allowed"]
        assert boundary["forbidden"]
        for test_name in boundary["tests"]:
            assert test_name in existing_test_files, f"{boundary['id']} is not pinned to test {test_name}"


def test_page_contract_visual_targets_are_registered_and_have_baselines():
    production_qa = (PROJECT_ROOT / "scripts/production_e2e_browser_qa.py").read_text(encoding="utf-8")

    expected_labels = {target["label"] for target in page_contracts.VISUAL_REGION_CONTRACTS}
    for label in expected_labels:
        assert label in production_qa, f"{label} is missing from production visual regression targets"

    for target in page_contracts.VISUAL_REGION_CONTRACTS:
        baseline = PROJECT_ROOT / "tests/visual_baselines" / target["baseline"]
        assert baseline.exists(), f"{target['label']} baseline missing: {baseline}"


def test_design_acceptance_rule_catalog_covers_every_user_reported_gap():
    required_rules = {
        "page_information_architecture",
        "functional_region_order",
        "card_metric_semantics",
        "button_order_and_density",
        "table_column_parity",
        "role_permission_boundaries",
        "data_semantics",
        "interaction_route_behavior",
        "browser_visual_regression",
    }
    catalog = {rule["id"]: rule for rule in page_contracts.DESIGN_ACCEPTANCE_RULES}

    assert required_rules.issubset(catalog)
    for rule_id in required_rules:
        rule = catalog[rule_id]
        assert rule["blocks_on_failure"] is True
        assert rule["verified_by"], f"{rule_id} must name at least one verification command or test"
        assert rule["scope"], f"{rule_id} must declare the checked page/function scope"
