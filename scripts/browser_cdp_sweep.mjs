import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const LOAD_TIMEOUT_MS = 30_000;
const CDP_TIMEOUT_MS = 15_000;
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

async function evaluateLayout(cdp, sessionId) {
  const expression = `(() => {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const body = document.body;
  const elements = Array.from(document.querySelectorAll('body *'));
  const rects = elements
    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 0 && rect.height > 0 && rect.bottom >= 0 && rect.top <= viewportHeight);
  const horizontalOverflow = document.documentElement.scrollWidth > viewportWidth + 2;
  const overwideCards = rects
    .filter(({ el, rect }) => /card|panel|el-card/.test(el.className || '') && rect.width > viewportWidth * 0.92)
    .slice(0, 5)
    .map(({ el, rect }) => ({ className: String(el.className), width: Math.round(rect.width) }));
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

      const url = joinUrl(payload.baseUrl, routeCase.route);
      await waitForLoad(cdp, sessionId, url, pageState);
      const layout = await evaluateLayout(cdp, sessionId);

      const screenshotName = `${routeCase.role}-${viewport.name}-${slugFor(routeCase.route)}.png`;
      const screenshotPath = path.join(payload.artifactDir, "screenshots", screenshotName);
      await captureScreenshot(cdp, sessionId, screenshotPath);

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
        toastText: layout.toastText ?? [],
      };
    } finally {
      removeListener();
    }
  });
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
    const version = await waitForJsonVersion(port, chrome);
    cdp = new CdpConnection(version.webSocketDebuggerUrl);
    await cdp.connect();

    const results = [];
    for (const viewport of payload.viewports || []) {
      for (const routeCase of routeCases(payload.routes || {})) {
        results.push(await sweepPage(cdp, payload, routeCase, viewport));
      }
    }
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
    await fs.rm(profileDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(sanitizeDiagnostics(error.message || error));
  process.exitCode = 1;
});
