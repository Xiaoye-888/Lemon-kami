import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const LOAD_TIMEOUT_MS = 30_000;
const CDP_TIMEOUT_MS = 15_000;
// Keep this below Python's 300s subprocess timeout so JS exits through cleanup first.
const BROWSER_SWEEP_TIMEOUT_MS = 270_000;
const SENSITIVE_PATTERNS = [
  /\bKAMI-[A-Za-z0-9]{8,}\b/g,
  /\bfingerprint-[A-Za-z0-9]{8,}\b/gi,
  /\bauthorization\s*:\s*bearer\s+[^\s&"'`]+/gi,
  /\bbearer\s+[^\s&"'`]+/gi,
  /([?&](?:auth|auth_token|token|password|access_token|refresh_token|session|session_id|sessionid|cookie)=)[^&#\s"'`]+/gi,
  /\b(?:auth|auth_token|token|password|cookie|session|session_id|sessionid|access_token|refresh_token)\s*[:=]\s*[^\s&"'`]+/gi,
  /\b(?:auth|auth_token|token|password|cookie|session|session_id|sessionid|access_token|refresh_token)\s+[^\s&"'`]+/gi,
  /localStorage\.setItem\(\s*["'](?:token|role|userInfo)["']\s*,\s*[^)]*\)/gi,
];

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
  ].filter(Boolean);
  return candidates.find((candidate) => existsSync(candidate));
}

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = address.port;
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withOverallDeadline(work) {
  let timeoutId;
  const deadline = new Promise((_, reject) => {
    timeoutId = setTimeout(() => {
      reject(new Error(`Browser CDP sweep exceeded internal deadline of ${BROWSER_SWEEP_TIMEOUT_MS}ms`));
    }, BROWSER_SWEEP_TIMEOUT_MS);
  });

  try {
    return await Promise.race([work, deadline]);
  } finally {
    clearTimeout(timeoutId);
  }
}

function maskMiddle(value, keep = 3) {
  const text = String(value);
  if (text.length <= keep * 2) {
    return "***";
  }
  return `${text.slice(0, keep)}***${text.slice(-keep)}`;
}

function sanitizeDiagnostics(value) {
  let text = String(value ?? "");
  text = text.replace(SENSITIVE_PATTERNS[0], (match) => maskMiddle(match));
  text = text.replace(SENSITIVE_PATTERNS[1], (match) => maskMiddle(match));
  for (const pattern of SENSITIVE_PATTERNS.slice(2)) {
    text = text.replace(pattern, "<redacted>");
  }
  return text;
}

async function terminateChrome(chromeProcess) {
  if (chromeProcess.exitCode !== null) {
    return;
  }
  const exited = new Promise((resolve) => {
    chromeProcess.once("exit", () => resolve());
  });
  chromeProcess.kill();
  await Promise.race([exited, sleep(3_000)]);
}

async function killChromeProcessesForProfile(profileDir) {
  if (process.platform !== "win32") {
    return;
  }
  const script = `
$profile = [Environment]::GetEnvironmentVariable('LEMON_CDP_PROFILE_DIR', 'Process')
if ([string]::IsNullOrWhiteSpace($profile)) { exit 0 }
Get-CimInstance Win32_Process -Filter "name = 'chrome.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine.Contains($profile) } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
`;
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
    {
      encoding: "utf8",
      env: { ...process.env, LEMON_CDP_PROFILE_DIR: profileDir },
      timeout: 15_000,
      windowsHide: true,
    },
  );
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Failed to stop Chrome profile processes; stderr=${result.stderr || ""}`);
  }
  await sleep(500);
}

async function cleanupProfileDir(profileDir) {
  let lastError;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      await fs.rm(profileDir, { recursive: true, force: true });
      return;
    } catch (error) {
      lastError = error;
      await sleep(250 * (attempt + 1));
    }
  }
  throw lastError;
}

async function waitForJsonVersion(port, chromeProcess) {
  const endpoint = `http://127.0.0.1:${port}/json/version`;
  const startedAt = Date.now();
  while (Date.now() - startedAt < LOAD_TIMEOUT_MS) {
    if (chromeProcess.exitCode !== null) {
      throw new Error(`Chrome exited before DevTools was ready with code ${chromeProcess.exitCode}`);
    }
    try {
      const response = await fetch(endpoint);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Chrome is still starting.
    }
    await sleep(200);
  }
  throw new Error("Timed out waiting for Chrome DevTools endpoint");
}

class CdpConnection {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = [];
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.webSocketUrl);
      this.ws.addEventListener("open", () => resolve());
      this.ws.addEventListener("error", () => reject(new Error("Unable to connect to Chrome DevTools WebSocket")));
      this.ws.addEventListener("message", (event) => this.handleMessage(event.data));
      this.ws.addEventListener("close", () => {
        for (const { reject: rejectPending, timer } of this.pending.values()) {
          clearTimeout(timer);
          rejectPending(new Error("Chrome DevTools WebSocket closed"));
        }
        this.pending.clear();
      });
    });
  }

  handleMessage(data) {
    const message = JSON.parse(data);
    if (message.id && this.pending.has(message.id)) {
      const pending = this.pending.get(message.id);
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      if (message.error) {
        pending.reject(new Error(sanitizeDiagnostics(`${message.error.message || "CDP error"} ${message.error.data || ""}`.trim())));
      } else {
        pending.resolve(message.result || {});
      }
      return;
    }
    for (const listener of this.listeners) {
      listener(message);
    }
  }

  send(method, params = {}, sessionId = undefined) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) {
      payload.sessionId = sessionId;
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out running CDP command ${method}`));
      }, CDP_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(JSON.stringify(payload));
    });
  }

  onEvent(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((current) => current !== listener);
    };
  }

  close() {
    this.ws?.close();
  }
}

function joinUrl(baseUrl, route) {
  return new URL(route, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`).toString();
}

function routeWithContext(routeCase, payload) {
  let route = routeCase.route;
  if (
    routeCase.role === "merchant" &&
    routeCase.route === "/merchant/batches" &&
    payload.context?.merchantBatchAppId
  ) {
    const separator = route.includes("?") ? "&" : "?";
    route = `${route}${separator}app_id=${encodeURIComponent(payload.context.merchantBatchAppId)}`;
  }
  return route;
}

function slugFor(route) {
  const slug = route.replace(/^\/$/, "root").replace(/^\//, "").replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return slug || "root";
}

function localStorageScript(role, session) {
  if (!role) {
    return `
try {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  localStorage.removeItem("userInfo");
} catch (error) {
  console.error("Unable to clear browser QA auth state", error);
}
`;
  }
  const safeSession = session || {};
  const token = safeSession.token ?? "";
  const userInfo = safeSession.userInfo ?? safeSession.user_info ?? {};
  const userInfoText = typeof userInfo === "string" ? userInfo : JSON.stringify(userInfo);
  return `
try {
  localStorage.setItem("token", ${JSON.stringify(String(token))});
  localStorage.setItem("role", ${JSON.stringify(role)});
  localStorage.setItem("userInfo", ${JSON.stringify(userInfoText)});
} catch (error) {
  console.error("Unable to seed browser QA auth state", error);
}
`;
}

function getEventSessionId(message) {
  return message.sessionId;
}

async function withNewPage(cdp, routeCase, callback) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  try {
    return await callback(sessionId);
  } finally {
    try {
      await cdp.send("Target.closeTarget", { targetId });
    } catch {
      // The page may already be gone after a navigation crash.
    }
  }
}

async function waitForLoad(cdp, sessionId, routeUrl, pageState) {
  let loaded = false;
  const loadPromise = new Promise((resolve) => {
    pageState.resolveLoad = () => {
      loaded = true;
      resolve();
    };
  });
  const navigation = await cdp.send("Page.navigate", { url: routeUrl }, sessionId);
  if (navigation.errorText) {
    pageState.networkFailures.push({ errorText: navigation.errorText, url: routeUrl });
  }
  await Promise.race([loadPromise, sleep(LOAD_TIMEOUT_MS)]);
  if (!loaded) {
    pageState.networkFailures.push({ errorText: "Timed out waiting for page load", url: routeUrl });
  }
  await sleep(900);
}

async function waitForRouteContent(cdp, sessionId, route) {
  if (!route.endsWith("/batches") && route !== "/merchant/apps") {
    return { ready: true, skipped: true };
  }

  const deadline = Date.now() + 15_000;
  let lastState = { ready: false, reason: "not checked" };
  while (Date.now() < deadline) {
    const routeLiteral = JSON.stringify(route);
    const expression = `(() => {
  const route = ${routeLiteral};
  const viewportHeight = window.innerHeight;
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= viewportHeight && style.display !== 'none' && style.visibility !== 'hidden';
  };
  const text = document.body.innerText || '';
  const loadingMasks = Array.from(document.querySelectorAll('.el-loading-mask, .el-loading-spinner')).filter(visible);
  const specRowActions = Array.from(document.querySelectorAll('.spec-section .row-actions')).filter(visible);
  const specLinks = Array.from(document.querySelectorAll('.spec-section .batch-title-link')).filter(visible);
  const merchantAppRowActions = Array.from(document.querySelectorAll('.merchant-apps .row-actions')).filter(visible);
  const hasMerchantBatchAppContext = route === '/merchant/batches' && window.location.pathname.includes('/merchant/batches') && window.location.search.includes('app_id=');
  const hasUnboundMerchantAppSelection = hasMerchantBatchAppContext && text.includes('\\u8bf7\\u5148\\u9009\\u62e9\\u5e94\\u7528');
  const hasStableEmpty = !hasMerchantBatchAppContext && (text.includes('\\u6682\\u65e0\\u6570\\u636e') || text.includes('\\u8bf7\\u5148\\u9009\\u62e9\\u5e94\\u7528'));
  const hasSelectedMerchantEmpty = hasMerchantBatchAppContext && text.includes('\\u6682\\u65e0\\u6570\\u636e') && !hasUnboundMerchantAppSelection;
  const isMerchantAppsRoute = route === '/merchant/apps' && window.location.pathname.includes('/merchant/apps');
  const hasMerchantAppsEmpty = isMerchantAppsRoute && text.includes('\\u6682\\u65e0\\u6570\\u636e');
  const ready = loadingMasks.length === 0 && (
    isMerchantAppsRoute
      ? (merchantAppRowActions.length > 0 || hasMerchantAppsEmpty)
      : (!hasUnboundMerchantAppSelection && (specRowActions.length > 0 || specLinks.length > 0 || hasStableEmpty || hasSelectedMerchantEmpty))
  );
  return {
    ready,
    route,
    loadingMasks: loadingMasks.length,
    specRowActions: specRowActions.length,
    specLinks: specLinks.length,
    merchantAppRowActions: merchantAppRowActions.length,
    hasStableEmpty,
    hasMerchantBatchAppContext,
    hasUnboundMerchantAppSelection,
    reason: hasUnboundMerchantAppSelection
      ? 'waiting for merchant batch app selection'
      : (ready ? 'ready' : (isMerchantAppsRoute ? 'waiting for merchant apps table content' : 'waiting for batch table content')),
  };
})()`;
    const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
    lastState = result.result?.value || { ready: false, reason: "unable to read route content state" };
    if (lastState.ready) {
      return lastState;
    }
    await sleep(350);
  }
  return { ...lastState, timedOut: true };
}

async function evaluateLayout(cdp, sessionId) {
  const expression = `(() => {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const body = document.body;
  const rectFor = (el) => {
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    return {
      left: Math.round(rect.left),
      top: Math.round(rect.top),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      right: Math.round(rect.right),
      bottom: Math.round(rect.bottom),
    };
  };
  const elements = Array.from(document.querySelectorAll('body *'));
  const rects = elements
    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= viewportHeight);
  const horizontalOverflow = document.documentElement.scrollWidth > viewportWidth + 2;
  const overwideCards = rects
    .filter(({ el, rect }) => /card|panel|el-card/.test(el.className || '') && rect.width > viewportWidth * 0.92)
    .slice(0, 5)
    .map(({ el, rect }) => ({ className: String(el.className), width: Math.round(rect.width) }));
  const actionGroups = Array.from(document.querySelectorAll('.row-actions, .table-actions, .action-group, [data-qa-action-group]'))
    .map((group) => {
      const groupRect = group.getBoundingClientRect();
      if (groupRect.width <= 0 || groupRect.height <= 0 || groupRect.bottom < 0 || groupRect.top > viewportHeight) {
        return null;
      }
      const items = Array.from(group.querySelectorAll('button, a, [role="button"], .el-button'))
        .map((el) => ({ el, rect: el.getBoundingClientRect(), text: (el.innerText || el.textContent || '').trim() }))
        .filter(({ rect }) => rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= viewportHeight);
      if (items.length < 2) {
        return null;
      }
      const sortedItems = [...items].sort((left, right) => left.rect.left - right.rect.left);
      const totalItemWidth = sortedItems.reduce((sum, item) => sum + item.rect.width, 0);
      const gaps = sortedItems.slice(1).map((item, index) => Math.max(0, item.rect.left - sortedItems[index].rect.right));
      const maxGap = gaps.length ? Math.max(...gaps) : 0;
      const topValues = sortedItems.map((item) => Math.round(item.rect.top));
      const minTop = Math.min(...topValues);
      const maxTop = Math.max(...topValues);
      const maxTopDelta = maxTop - minTop;
      const leftPadding = Math.max(0, sortedItems[0].rect.left - groupRect.left);
      const rightPadding = Math.max(0, groupRect.right - sortedItems[sortedItems.length - 1].rect.right);
      return {
        selector: String(group.className || group.getAttribute('data-qa-action-group') || group.tagName).trim().slice(0, 80),
        button_count: sortedItems.length,
        left: Math.round(groupRect.left),
        top: Math.round(groupRect.top),
        width: Math.round(groupRect.width),
        height: Math.round(groupRect.height),
        group_width: Math.round(groupRect.width),
        content_width: Math.round(totalItemWidth),
        max_gap: Math.round(maxGap),
        max_top_delta: Math.round(maxTopDelta),
        wrapped: maxTopDelta > 10,
        left_padding: Math.round(leftPadding),
        right_padding: Math.round(rightPadding),
        spread_ratio: Number((groupRect.width / Math.max(totalItemWidth, 1)).toFixed(2)),
        buttons: sortedItems.slice(0, 6).map((item) => item.text).filter(Boolean),
      };
    })
    .filter(Boolean)
    .slice(0, 8);
  const controlCounts = new Map();
  Array.from(document.querySelectorAll('button, .el-button, .el-select, .el-input, .el-date-editor, [role="button"]'))
    .map((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0 || rect.bottom < 0 || rect.top > viewportHeight) {
        return null;
      }
      const label = (
        el.getAttribute('aria-label') ||
        el.getAttribute('placeholder') ||
        el.getAttribute('title') ||
        (el.innerText || el.textContent || '')
      ).trim().replace(/\s+/g, ' ');
      if (!label || label.length > 80) {
        return null;
      }
      return label;
    })
    .filter(Boolean)
    .forEach((label) => {
      controlCounts.set(label, (controlCounts.get(label) || 0) + 1);
    });
  const duplicatedControls = Array.from(controlCounts.entries())
    .filter(([, count]) => count >= 2)
    .slice(0, 8)
    .map(([label, count]) => ({ label, count }));
  const headerBottom = (() => {
    const fixedHeader = document.querySelector('.el-header, header, .app-header, .layout-header');
    if (!fixedHeader) return 0;
    const rect = fixedHeader.getBoundingClientRect();
    return rect.bottom > 0 ? rect.bottom : 0;
  })();
  const headerOcclusions = Array.from(document.querySelectorAll('h1, h2, h3, .yz-panel-title, .page-title, .panel-title'))
    .map((el) => {
      const rect = el.getBoundingClientRect();
      const text = (el.innerText || el.textContent || '').trim();
      if (!text || rect.width <= 0 || rect.height <= 0 || rect.bottom <= 0 || rect.top > viewportHeight) {
        return null;
      }
      const probeX = Math.max(1, Math.min(rect.left + Math.min(rect.width / 2, 24), viewportWidth - 2));
      const probeY = Math.max(1, Math.min(rect.top + 2, viewportHeight - 2));
      const topElement = document.elementFromPoint(probeX, probeY);
      const occluded = topElement && topElement !== el && !el.contains(topElement);
      if (rect.top <= headerBottom + 8 && (occluded || rect.bottom <= headerBottom + 24)) {
        return { text: text.slice(0, 80), top: Math.round(rect.top) };
      }
      return null;
    })
    .filter(Boolean)
    .slice(0, 6);
  const tableHeaders = Array.from(document.querySelectorAll('.yz-clean-table thead tr, .el-table__header-wrapper thead tr'))
    .map((row) => Array.from(row.querySelectorAll('th .cell, th')).map((cell) => (cell.innerText || cell.textContent || '').trim()).filter(Boolean))
    .filter((row) => row.length > 0);
  const tableColumnMismatches = [];
  if (window.location.pathname.includes('/merchant/batches')) {
    const expectedHeaders = ['规格', '类型', '策略数', '批次', '总数/已用/剩余', '状态', '用途备注', '操作'];
    const firstTableHeaders = tableHeaders[0] || [];
    const missing = expectedHeaders.filter((label) => !firstTableHeaders.includes(label));
    const extra = firstTableHeaders.filter((label) => !expectedHeaders.includes(label));
    if (missing.length || extra.length) {
      tableColumnMismatches.push({
        baselineRoute: '/admin/kamis/batches',
        missing,
        extra,
      });
    }
  }
  const detailPanelMismatches = [];
  if (window.location.pathname.includes('/merchant/batches')) {
    const cardsPanel = document.querySelector('.cards-panel');
    if (cardsPanel) {
      const panelText = (cardsPanel.innerText || cardsPanel.textContent || '').replace(/\s+/g, ' ');
      const panelLabels = Array.from(cardsPanel.querySelectorAll('button, .el-button, input, [placeholder], [title], .el-select, .el-input'))
        .map((el) => (
          el.getAttribute('placeholder') ||
          el.getAttribute('title') ||
          el.getAttribute('aria-label') ||
          el.innerText ||
          el.textContent ||
          ''
        ).trim())
        .filter(Boolean)
        .join(' ');
      const detailText = [panelText, panelLabels].filter(Boolean).join(' ');
      const detailHeaders = Array.from(cardsPanel.querySelectorAll('thead tr th .cell, thead tr th'))
        .map((cell) => (cell.innerText || cell.textContent || '').trim())
        .filter(Boolean);
      const missing = [];
      for (const label of ['导出', '删除选中', '全部批次', '全部状态', '搜索卡密/用户']) {
        if (!detailText.includes(label)) {
          missing.push(label);
        }
      }
      if (!detailText.includes('规格卡密列表') && !detailText.includes('批次卡密列表')) {
        missing.push('卡密面板标题');
      }
      if (!cardsPanel.querySelector('.el-table-column--selection, thead .el-checkbox, .el-checkbox__input')) {
        missing.push('选择列');
      }
      for (const label of ['卡密', '批次', '状态', '绑定关系', '设备策略', '创建时间', '使用用户', '备注']) {
        if (!detailHeaders.includes(label)) {
          missing.push(label);
        }
      }
      if (missing.length) {
        detailPanelMismatches.push({
          baselineRoute: '/admin/kamis/batches',
          missing: Array.from(new Set(missing)),
        });
      }
    }
  }
  const detailSummaryCard = document.querySelector('.batch-detail-shell .summary-metric-card');
  const detailSummaryRect = rectFor(detailSummaryCard);
  const merchantBatchSpecRowActions = window.location.pathname.includes('/merchant/batches')
    ? document.querySelector('.spec-section .row-actions')
    : null;
  const merchantBatchSpecRowActionsRect = rectFor(merchantBatchSpecRowActions);
  const merchantBatchBatchRowActions = window.location.pathname.includes('/merchant/batches')
    ? document.querySelector('.batches-panel .icon-actions')
    : null;
  const merchantBatchBatchRowActionsRect = rectFor(merchantBatchBatchRowActions);
  const merchantBatchDrawerVisible = window.location.pathname.includes('/merchant/batches') && Array.from(document.querySelectorAll('.el-drawer'))
    .some((el) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    });
  const merchantBatchUrlHasBatchNo = window.location.pathname.includes('/merchant/batches') && new URLSearchParams(window.location.search).has('batch_no');
  const merchantBatchDetailAttempted = merchantBatchDrawerVisible || merchantBatchUrlHasBatchNo;
  const merchantBatchDetailOpenedAsDrawer = merchantBatchDetailAttempted ? merchantBatchDrawerVisible : null;
  const merchantBatchDetailUrlHasBatchNo = merchantBatchDetailAttempted ? merchantBatchUrlHasBatchNo : null;
  const merchantBatchDiagnostics = window.location.pathname.includes('/merchant/batches')
    ? {
      href: window.location.href,
      search: window.location.search,
      selectedAppText: (document.querySelector('.yz-filter-strip .el-select .el-select__selected-item, .yz-filter-strip .el-select .el-input__inner')?.innerText || document.querySelector('.yz-filter-strip .el-select input')?.value || '').trim(),
      appOptionCount: document.querySelectorAll('.el-select-dropdown__item').length,
      specRowActionCount: document.querySelectorAll('.spec-section .row-actions').length,
      specLinkCount: document.querySelectorAll('.spec-section .batch-title-link').length,
      emptyText: Array.from(document.querySelectorAll('.el-empty__description')).map((el) => (el.innerText || el.textContent || '').trim()).filter(Boolean).join(' | '),
    }
    : null;
  const detailSummaryMismatches = [];
  if (window.location.pathname.includes('/merchant/batches') && detailSummaryCard) {
    const expectedLabels = ['总数', '未使用', '已使用'];
    const metricItems = Array.from(detailSummaryCard.querySelectorAll('.metric-item'));
    const labels = metricItems
      .map((item) => {
        const label = item.querySelector('span');
        return (label?.innerText || label?.textContent || '').trim();
      })
      .filter(Boolean);
    const missing = expectedLabels.filter((label) => !labels.includes(label));
    const unexpected = labels.filter((label) => !expectedLabels.includes(label));
    if (metricItems.length !== 3 || missing.length || unexpected.length) {
      detailSummaryMismatches.push({
        baselineRoute: '/admin/kamis/batches',
        expected: expectedLabels,
        labels,
        metricCount: metricItems.length,
        missing,
        unexpected,
      });
    }
  }
  const splitWorkbenchDetected = Boolean(document.querySelector('.spec-workbench, .detail-panel'));
  const visibleArea = rects.reduce((sum, { rect }) => {
    const w = Math.max(0, Math.min(rect.right, viewportWidth) - Math.max(rect.left, 0));
    const h = Math.max(0, Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0));
    return sum + Math.min(w * h, viewportWidth * viewportHeight);
  }, 0);
  const largeBlankRatio = Math.max(0, 1 - Math.min(1, visibleArea / (viewportWidth * viewportHeight * 1.8)));
  return {
    title: document.title,
    bodyTextLength: (body.innerText || '').trim().length,
    bodyTextSample: (body.innerText || '').trim().slice(0, 300),
    horizontalOverflow,
    overwideCards,
    action_groups: actionGroups,
    duplicatedControls,
    headerOcclusions,
    tableColumnMismatches,
    detailPanelMismatches,
    detailSummaryMismatches,
    detailSummaryRect,
    merchantBatchSpecRowActionsRect,
    merchantBatchBatchRowActionsRect,
    merchantBatchDetailOpenedAsDrawer,
    merchantBatchDetailUrlHasBatchNo,
    merchantBatchDiagnostics,
    splitWorkbenchDetected,
    largeBlankRatio: Number(largeBlankRatio.toFixed(2)),
    toastText: Array.from(document.querySelectorAll('.el-message, .el-notification')).map((el) => el.innerText.trim()).filter(Boolean),
  };
})()`;
  const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  return result.result?.value || {};
}

async function captureScreenshot(cdp, sessionId, screenshotPath) {
  const { data } = await cdp.send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
  await fs.writeFile(screenshotPath, Buffer.from(data, "base64"));
}

async function openFirstBatchDetail(cdp, sessionId) {
  const expression = `(() => {
  const candidates = Array.from(document.querySelectorAll('button.batch-title-link, .batch-title-link'))
    .filter((el) => {
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
  const target = candidates[0];
  if (!target) {
    return false;
  }
  target.click();
  return true;
})()`;
  const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (!result.result?.value) {
    return null;
  }
  await sleep(1200);
  return evaluateLayout(cdp, sessionId);
}

async function sweepPage(cdp, payload, routeCase, viewport) {
  return withNewPage(cdp, routeCase, async (sessionId) => {
    const pageState = {
      consoleErrors: [],
      exceptions: [],
      networkFailures: [],
      httpErrors: [],
      requestUrls: new Map(),
      status: null,
      resolveLoad: null,
    };
    const listener = (message) => {
      if (getEventSessionId(message) !== sessionId) {
        return;
      }
      if (message.method === "Runtime.consoleAPICalled" && message.params?.type === "error") {
        pageState.consoleErrors.push(message.params.args?.map((arg) => arg.value ?? arg.description ?? "").join(" ") || "console.error");
      }
      if (message.method === "Runtime.exceptionThrown") {
        pageState.exceptions.push(message.params?.exceptionDetails?.text || "Runtime exception");
      }
      if (message.method === "Network.requestWillBeSent") {
        pageState.requestUrls.set(message.params?.requestId, message.params?.request?.url);
      }
      if (message.method === "Network.loadingFailed") {
        pageState.networkFailures.push({
          url: pageState.requestUrls.get(message.params?.requestId) || message.params?.requestId,
          errorText: message.params?.errorText || "Network loading failed",
        });
      }
      if (message.method === "Network.responseReceived") {
        const response = message.params?.response;
        if (message.params?.type === "Document") {
          pageState.status = response?.status ?? pageState.status;
        }
        if (response?.status >= 400) {
          pageState.httpErrors.push({ status: response.status, url: response.url });
        }
      }
      if (message.method === "Page.loadEventFired") {
        pageState.resolveLoad?.();
      }
    };
    const removeListener = cdp.onEvent(listener);
    try {
      await cdp.send("Runtime.enable", {}, sessionId);
      await cdp.send("Page.enable", {}, sessionId);
      await cdp.send("Network.enable", {}, sessionId);
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: viewport.width,
        height: viewport.height,
        deviceScaleFactor: 1,
        mobile: viewport.width < 600,
      }, sessionId);

      const script = localStorageScript(routeCase.authRole, payload.sessions?.[routeCase.authRole]);
      await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: script }, sessionId);

      const url = joinUrl(payload.baseUrl, routeWithContext(routeCase, payload));
      await waitForLoad(cdp, sessionId, url, pageState);
      const contentState = await waitForRouteContent(cdp, sessionId, routeCase.route);
      if (!contentState.ready && !contentState.skipped) {
        pageState.networkFailures.push({
          errorText: `Timed out waiting for route content: ${contentState.reason || "unknown"}`,
          url,
        });
      }
      let layout = await evaluateLayout(cdp, sessionId);

      const screenshotName = `${routeCase.role}-${viewport.name}-${slugFor(routeCase.route)}.png`;
      const screenshotPath = path.join(payload.artifactDir, "screenshots", screenshotName);
      await captureScreenshot(cdp, sessionId, screenshotPath);

      let detailScreenshotPath = null;
      if (routeCase.route.endsWith("/batches")) {
        const detailLayout = await openFirstBatchDetail(cdp, sessionId);
        if (detailLayout) {
          layout = {
            ...layout,
            detailPanelMismatches: [
              ...(layout.detailPanelMismatches || []),
              ...(detailLayout.detailPanelMismatches || []),
            ],
            detailSummaryMismatches: [
              ...(layout.detailSummaryMismatches || []),
              ...(detailLayout.detailSummaryMismatches || []),
            ],
            detailSummaryRect: detailLayout.detailSummaryRect || layout.detailSummaryRect || null,
            merchantBatchBatchRowActionsRect: detailLayout.merchantBatchBatchRowActionsRect || layout.merchantBatchBatchRowActionsRect || null,
            merchantBatchDetailOpenedAsDrawer: detailLayout.merchantBatchDetailOpenedAsDrawer ?? layout.merchantBatchDetailOpenedAsDrawer ?? null,
            merchantBatchDetailUrlHasBatchNo: detailLayout.merchantBatchDetailUrlHasBatchNo ?? layout.merchantBatchDetailUrlHasBatchNo ?? null,
          };
          const detailScreenshotName = `${routeCase.role}-${viewport.name}-${slugFor(routeCase.route)}-detail.png`;
          detailScreenshotPath = path.join(payload.artifactDir, "screenshots", detailScreenshotName);
          await captureScreenshot(cdp, sessionId, detailScreenshotPath);
        }
      }

      return {
        role: routeCase.role,
        route: routeCase.route,
        viewport: viewport.name,
        url,
        status: pageState.status ?? 200,
        screenshot: screenshotPath,
        console_errors: pageState.consoleErrors,
        exceptions: pageState.exceptions,
        network_failures: pageState.networkFailures,
        http_errors: pageState.httpErrors,
        bodyTextLength: layout.bodyTextLength ?? 0,
        bodyTextSample: layout.bodyTextSample ?? "",
        layout,
        detailScreenshot: detailScreenshotPath,
        toastText: layout.toastText ?? [],
      };
    } finally {
      removeListener();
    }
  });
}

function hasRetryableNetworkFailure(result) {
  return Boolean(
    (result.network_failures || []).length ||
    (result.http_errors || []).some((error) => Number(error.status) >= 500)
  );
}

async function sweepPageWithRetry(cdp, payload, routeCase, viewport) {
  let lastResult = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    lastResult = await sweepPage(cdp, payload, routeCase, viewport);
    lastResult.retry_attempts = attempt;
    if (!hasRetryableNetworkFailure(lastResult)) {
      return lastResult;
    }
    await sleep(700 * (attempt + 1));
  }
  return lastResult;
}

function routeCases(routes) {
  const cases = [];
  for (const route of routes.public || []) {
    cases.push({ role: "public", authRole: null, route });
  }
  for (const route of routes.admin || []) {
    cases.push({ role: "admin", authRole: "admin", route });
  }
  for (const route of routes.merchant || []) {
    cases.push({ role: "merchant", authRole: "merchant", route });
  }
  return cases;
}

async function main() {
  if (typeof WebSocket !== "function") {
    console.error("Node global WebSocket is unavailable. Use Node 22+ or another runtime with built-in WebSocket support.");
    process.exitCode = 1;
    return;
  }
  if (typeof fetch !== "function") {
    console.error("Node global fetch is unavailable. Use Node 18+ or another runtime with built-in fetch support.");
    process.exitCode = 1;
    return;
  }

  const rawInput = await readStdin();
  const payload = JSON.parse(rawInput);
  const chromePath = findChrome();
  if (!chromePath) {
    console.error("Unable to find Chrome. Set CHROME_PATH to a Chrome executable.");
    process.exitCode = 1;
    return;
  }

  const port = await reservePort();
  const profileDir = await fs.mkdtemp(path.join(os.tmpdir(), "lemon-kami-cdp-"));
  await fs.mkdir(path.join(payload.artifactDir, "screenshots"), { recursive: true });

  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-extensions",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  let chromeStderr = "";
  chrome.stderr.on("data", (chunk) => {
    chromeStderr += chunk.toString("utf8");
  });

  let cdp;
  try {
    const sweepWork = (async () => {
      const version = await waitForJsonVersion(port, chrome);
      cdp = new CdpConnection(version.webSocketDebuggerUrl);
      await cdp.connect();

      const results = [];
      for (const viewport of payload.viewports || []) {
        for (const routeCase of routeCases(payload.routes || {})) {
          results.push(await sweepPageWithRetry(cdp, payload, routeCase, viewport));
        }
      }
      return results;
    })();
    const results = await withOverallDeadline(sweepWork);
    process.stdout.write(JSON.stringify(results, null, 2));
  } catch (error) {
    console.error(sanitizeDiagnostics(error.message || error));
    if (chromeStderr.trim()) {
      console.error(sanitizeDiagnostics(chromeStderr.trim()).slice(-4000));
    }
    process.exitCode = 1;
  } finally {
    cdp?.close();
    await terminateChrome(chrome);
    try {
      await killChromeProcessesForProfile(profileDir);
      await cleanupProfileDir(profileDir);
    } catch (error) {
      console.error(sanitizeDiagnostics(error.message || error));
      process.exitCode = 1;
    }
  }
}

main().catch((error) => {
  console.error(sanitizeDiagnostics(error.message || error));
  process.exitCode = 1;
});
