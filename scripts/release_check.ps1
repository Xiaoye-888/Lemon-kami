param(
    [switch]$Smoke,
    [string]$ApiBase = "http://127.0.0.1:8001",
    [string]$FrontendBase = "http://127.0.0.1:3001"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Write-Step($Message) {
    Write-Output ""
    Write-Output "==> $Message"
}

function Invoke-Checked($Command, $WorkingDirectory = $root) {
    Push-Location $WorkingDirectory
    try {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $Command"
        }
    } finally {
        Pop-Location
    }
}

function Remove-GeneratedCaches {
    $targets = @()
    Get-ChildItem -Path $root -Recurse -Force -Directory -Filter "__pycache__" | Where-Object {
        $_.FullName -notmatch "\\.venv\\" -and $_.FullName -notmatch "\\admin\\node_modules\\"
    } | ForEach-Object { $targets += $_.FullName }

    $javaTarget = Join-Path $root "sdk\java_sdk\target"
    if (Test-Path -LiteralPath $javaTarget) {
        $targets += (Resolve-Path -LiteralPath $javaTarget).Path
    }

    foreach ($target in ($targets | Sort-Object -Unique)) {
        $resolved = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove outside workspace: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-Output "cleaned $resolved"
    }
}

function Assert-Contains($Path, $Expected) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Missing required file: $Path"
    }
    $content = Get-Content -LiteralPath $Path -Raw
    if ($content -notmatch [regex]::Escape($Expected)) {
        throw "$Path does not contain required pattern: $Expected"
    }
}

function Invoke-ReleaseBoundaryStaticChecks {
    $rootDockerIgnore = Join-Path $root ".dockerignore"
    $adminDockerIgnore = Join-Path $root "admin\.dockerignore"

    foreach ($pattern in @(".env", "*.db", "logs", "backups", ".venv", ".engramory-memory", "admin")) {
        Assert-Contains $rootDockerIgnore $pattern
    }
    foreach ($pattern in @(".env", "node_modules", "dist")) {
        Assert-Contains $adminDockerIgnore $pattern
    }

    $directRequestImports = Get-ChildItem -Path (Join-Path $root "admin\src\views") -Filter "*.vue" -File |
        Select-String -Pattern "\.\./utils/request|@/utils/request" |
        ForEach-Object { "$($_.Path):$($_.LineNumber)" }
    if ($directRequestImports) {
        $directRequestImports | ForEach-Object { Write-Output $_ }
        throw "views do not import request directly"
    }

    $staleFrontendFiles = @(
        "admin\src\components\HelloWorld.vue",
        "admin\src\views\Logs.vue",
        "admin\src\style.css",
        "admin\src\assets\vite.svg",
        "admin\src\assets\vue.svg",
        "admin\src\assets\hero.png",
        "admin\public\icons.svg"
    )
    foreach ($relativePath in $staleFrontendFiles) {
        $fullPath = Join-Path $root $relativePath
        if (Test-Path -LiteralPath $fullPath) {
            throw "unused Vite/legacy frontend files removed: $relativePath"
        }
    }

    $readme = Get-Content -LiteralPath (Join-Path $root "README.md") -Raw
    if ($readme -notmatch "981388" -or $readme -match "d18880848565") {
        throw "README contact check failed"
    }

    $specChecks = @(
        @{ Path = "models.py"; Pattern = "class KamiSpec" },
        @{ Path = "database.py"; Pattern = "kami_specs" },
        @{ Path = "routes_admin.py"; Pattern = "/kami-specs" },
        @{ Path = "routes_admin.py"; Pattern = "spec_id" },
        @{ Path = "admin\src\api\kami.js"; Pattern = "getKamiSpecs" },
        @{ Path = "admin\src\api\kami.js"; Pattern = "deleteKamiSpec" },
        @{ Path = "admin\src\api\kami.js"; Pattern = "generateKamisForSpec" },
        @{ Path = "admin\src\utils\kamiSpecGrouping.js"; Pattern = "groupKamiSpecsByBenefit" },
        @{ Path = "admin\src\views\KamiBatches.vue"; Pattern = "新建规格" },
        @{ Path = "admin\src\views\KamiBatches.vue"; Pattern = "绑定策略版本" },
        @{ Path = "admin\src\views\KamiBatches.vue"; Pattern = "删除规格" },
        @{ Path = "KAMI_CORE_API.md"; Pattern = "卡密规格管理" }
    )
    foreach ($check in $specChecks) {
        Assert-Contains (Join-Path $root $check.Path) $check.Pattern
    }

    Write-Output "release boundary static checks ok"
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///./lemon_kami_dev.db"
}
if (-not $env:REDIS_URL) {
    $env:REDIS_URL = "memory://local"
}

try {
    Write-Step "Python compile"
    Invoke-Checked "& `"$python`" -m py_compile main.py routes_sdk.py routes_admin.py routes_user.py models.py authorization_service.py database.py interface_catalog.py routes_docs.py sdk.py check_apps.py sdk\python_sdk\lemon_kami.py"

    Write-Step "Login AES compatibility"
    @'
import base64
import os
from crypto import CryptoHelper

payload = {"username": "admin", "password": "admin123"}
for size in (16, 24, 32):
    key = base64.b64encode(os.urandom(size)).decode("utf-8")
    encrypted = CryptoHelper.aes_encrypt(payload, key)
    decrypted = CryptoHelper.aes_decrypt(encrypted["encrypted_data"], key, encrypted["iv"])
    if decrypted != payload:
        raise SystemExit(f"login AES roundtrip failed for {size}-byte key")
print("login AES compatibility ok")
'@ | & $python -

    Write-Step "Release boundary static checks"
    Invoke-ReleaseBoundaryStaticChecks

    Write-Step "Frontend build"
    Invoke-Checked "npm run build" (Join-Path $root "admin")

    Write-Step "Java SDK package"
    $mvn = Get-Command mvn -ErrorAction SilentlyContinue
    if ($mvn) {
        Invoke-Checked "mvn -q -DskipTests package" (Join-Path $root "sdk\java_sdk")
    } else {
        Write-Output "mvn not found; skipped Java package check"
    }

    Write-Step "SDK zip stale-entry scan"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $legacyPatterns = @(
        ("you" + "zi"),
        ("You" + "zi"),
        ("YOU" + "ZI"),
        "1\.js",
        ("com/" + "you" + "zi")
    )
    $errors = @()
    Get-ChildItem -Path (Join-Path $root "sdk") -Filter "*.zip" -Recurse | ForEach-Object {
        $zipPath = $_.FullName
        $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
        try {
            foreach ($entry in $zip.Entries) {
                foreach ($pattern in $legacyPatterns) {
                    if ($entry.FullName -match $pattern) {
                        $errors += "${zipPath}:$($entry.FullName)"
                    }
                }
            }
        } finally {
            $zip.Dispose()
        }
    }
    if ($errors.Count -gt 0) {
        $errors | ForEach-Object { Write-Output $_ }
        throw "SDK zip stale-entry scan failed"
    }
    Write-Output "SDK zip scan ok"

    Write-Step "Required route check"
    @'
from main import app
routes = {getattr(r, "path", "") for r in app.routes}
required = {
    "/",
    "/health",
    "/api/sdk/download",
    "/api/v1/admin/dashboard",
    "/api/v1/docs/interfaces",
    "/api/v1/sdk/verify",
    "/api/v1/sdk/consume",
    "/api/v1/sdk/apps/{app_id}/config",
}
missing = sorted(required - routes)
if missing:
    raise SystemExit("missing routes: " + ", ".join(missing))
print("required routes ok")
'@ | & $python -

    if ($Smoke) {
        Write-Step "Local smoke checks"
        $checks = @(
            @{ Name = "api_root"; Url = "$ApiBase/" },
            @{ Name = "health"; Url = "$ApiBase/health" },
            @{ Name = "public_interface_docs"; Url = "$ApiBase/api/v1/docs/interfaces" },
            @{ Name = "sdk_download_python"; Url = "$ApiBase/api/sdk/download?type=python" },
            @{ Name = "sdk_download_javascript"; Url = "$ApiBase/api/sdk/download?type=javascript" },
            @{ Name = "sdk_download_java"; Url = "$ApiBase/api/sdk/download?type=java" },
            @{ Name = "frontend_home"; Url = "$FrontendBase/" },
            @{ Name = "frontend_proxy_docs"; Url = "$FrontendBase/api/v1/docs/interfaces" },
            @{ Name = "frontend_lemon_sdk"; Url = "$FrontendBase/sdk/lemon-kami.js" }
        )

        foreach ($check in $checks) {
            $response = Invoke-WebRequest -Uri $check.Url -UseBasicParsing -TimeoutSec 8
            $status = [int]$response.StatusCode
            if ($status -ne 200) {
                throw "$($check.Name) returned $status"
            }
            if ($check.Name -like "sdk_download_*") {
                $contentDisposition = $response.Headers["Content-Disposition"]
                if ($contentDisposition -notmatch "lemon-kami") {
                    throw "bad content-disposition for $($check.Name): $contentDisposition"
                }
            }
            Write-Output "$($check.Name) $status"
        }
    }

    Write-Step "Cleanup"
    Remove-GeneratedCaches
    Write-Output ""
    Write-Output "release check ok"
} finally {
    Remove-GeneratedCaches
}
