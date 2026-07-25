param(
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [switch]$DryRun,
    [switch]$AllowDifferentBranch
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Write-Step($Message) {
    Write-Output ""
    Write-Output "==> $Message"
}

function ConvertTo-ProxyUri($ProxyServer) {
    if ([string]::IsNullOrWhiteSpace($ProxyServer)) {
        throw "Windows system proxy is enabled, but ProxyServer is empty."
    }

    $entries = @{}
    $fallback = $null

    foreach ($part in ($ProxyServer -split ";")) {
        $trimmed = $part.Trim()
        if (-not $trimmed) {
            continue
        }

        if ($trimmed -match "^([^=]+)=(.+)$") {
            $entries[$Matches[1].Trim().ToLowerInvariant()] = $Matches[2].Trim()
        } elseif (-not $fallback) {
            $fallback = $trimmed
        }
    }

    $target = $null
    $source = $null
    foreach ($key in @("https", "http", "socks", "socks5")) {
        if ($entries.ContainsKey($key)) {
            $target = $entries[$key]
            $source = $key
            break
        }
    }

    if (-not $target) {
        $target = $fallback
        $source = "http"
    }

    if (-not $target) {
        throw "Could not parse Windows ProxyServer: $ProxyServer"
    }

    if ($target -match "^[a-zA-Z][a-zA-Z0-9+.-]*://") {
        return $target
    }

    if ($source -match "^socks") {
        return "socks5://$target"
    }

    return "http://$target"
}

function Format-ProxyForDisplay($ProxyUri) {
    try {
        $uri = [uri]$ProxyUri
        $port = if ($uri.Port -gt 0) { ":$($uri.Port)" } else { "" }
        if ($uri.UserInfo) {
            return "$($uri.Scheme)://<redacted>@$($uri.Host)$port"
        }
        return "$($uri.Scheme)://$($uri.Host)$port"
    } catch {
        return "<unparseable proxy uri>"
    }
}

function Invoke-GitChecked($Arguments) {
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Write-Step "Reading Windows system proxy"
$settingsPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
$settings = Get-ItemProperty -Path $settingsPath

if ([int]$settings.ProxyEnable -ne 1) {
    throw "Windows system proxy is disabled. Enable your proxy app system proxy first."
}

$proxyUri = ConvertTo-ProxyUri $settings.ProxyServer
$proxy = [uri]$proxyUri
if ($proxy.Port -le 0) {
    throw "Proxy URI has no port: $(Format-ProxyForDisplay $proxyUri)"
}

Write-Step "Checking proxy port"
$isOpen = Test-NetConnection $proxy.Host -Port $proxy.Port -InformationLevel Quiet
if (-not $isOpen) {
    throw "Proxy port is not reachable: $(Format-ProxyForDisplay $proxyUri)"
}
Write-Output "Proxy is reachable: $(Format-ProxyForDisplay $proxyUri)"

Write-Step "Updating global Git proxy"
& git config --global http.proxy $proxyUri
if ($LASTEXITCODE -ne 0) {
    throw "git config --global http.proxy failed with exit code $LASTEXITCODE"
}
& git config --global https.proxy $proxyUri
if ($LASTEXITCODE -ne 0) {
    throw "git config --global https.proxy failed with exit code $LASTEXITCODE"
}
Write-Output "Git proxy updated: $(Format-ProxyForDisplay $proxyUri)"

Write-Step "Checking target branch"
$currentBranch = (& git rev-parse --abbrev-ref HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not read current Git branch."
}

if (-not $AllowDifferentBranch -and $currentBranch -ne $Branch) {
    throw "Current branch is '$currentBranch', but this script is configured to push '$Branch'. Checkout '$Branch' or pass -AllowDifferentBranch."
}

Write-Step "Verifying GitHub access"
Invoke-GitChecked @("ls-remote", "--heads", $Remote, $Branch)

if ($DryRun) {
    Write-Step "Running dry-run push"
    & git push --dry-run $Remote $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git push --dry-run failed with exit code $LASTEXITCODE"
    }
    Write-Output "Dry-run push completed."
} else {
    Write-Step "Pushing to GitHub"
    & git push $Remote $Branch
    if ($LASTEXITCODE -ne 0) {
        throw "git push failed with exit code $LASTEXITCODE"
    }
    Write-Output "Push completed. GitHub Actions should deploy after the push reaches main."
}
