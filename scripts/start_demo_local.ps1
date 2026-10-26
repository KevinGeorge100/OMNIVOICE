param(
    [int]$Port = 8000,
    [string]$EnvFile = "",
    [string]$LineId = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not $EnvFile) { $EnvFile = Join-Path $root ".env" }
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Private .env is missing. Pass -EnvFile with the existing private settings path."
}
$envFilePath = (Resolve-Path -LiteralPath $EnvFile).Path
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Local .venv Python is missing." }
$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflaredCommand) { throw "cloudflared is not installed or not on PATH." }
if ($Port -lt 1 -or $Port -gt 65535) { throw "Invalid local port." }

$listener = [System.Net.Sockets.TcpClient]::new()
try {
    $listener.Connect("127.0.0.1", $Port)
    throw "Local port is already in use. Stop the prior server before starting this demo mode."
} catch [System.Net.Sockets.SocketException] {
    # A refused loopback connection means the port is available.
} finally {
    $listener.Dispose()
}

$logBase = Join-Path ([System.IO.Path]::GetTempPath()) ("omnivoice-vobiz-demo-" + [guid]::NewGuid().ToString("N"))
$tunnelOut = "$logBase.tunnel.out"
$tunnelErr = "$logBase.tunnel.err"
$serverOut = "$logBase.server.out"
$serverErr = "$logBase.server.err"
$tunnel = $null
$server = $null
$oldPublicBase = [Environment]::GetEnvironmentVariable("OMNI_PUBLIC_BASE_URL", "Process")

function Test-Endpoint([string]$Address) {
    try {
        $response = Invoke-WebRequest -Uri $Address -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch { return $false }
}

try {
    $tunnel = Start-Process -FilePath $cloudflaredCommand.Source -ArgumentList @(
        "tunnel", "--url", "http://127.0.0.1:$Port", "--no-autoupdate", "--loglevel", "info"
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr
    $origin = $null
    for ($i = 0; $i -lt 60; $i++) {
        if ($tunnel.HasExited) { throw "Temporary tunnel exited before publishing a hostname." }
        Start-Sleep -Seconds 1
        $messages = @()
        if (Test-Path -LiteralPath $tunnelOut) { $messages += Get-Content -LiteralPath $tunnelOut -Raw }
        if (Test-Path -LiteralPath $tunnelErr) { $messages += Get-Content -LiteralPath $tunnelErr -Raw }
        $match = [regex]::Match(($messages -join "`n"), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) { $origin = $match.Value; break }
    }
    if (-not $origin) { throw "Temporary tunnel did not publish a hostname within 60 seconds." }
    $env:OMNI_PUBLIC_BASE_URL = $origin

    $server = Start-Process -FilePath $python -ArgumentList @(
        "-m", "omnivoice.cli", "serve", "--host", "127.0.0.1", "--port", "$Port",
        "--env-file", "`"$envFilePath`""
    ) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr

    $localReady = $false
    for ($i = 0; $i -lt 45; $i++) {
        if ($server.HasExited) { throw "Local voice engine exited during startup." }
        if ((Test-Endpoint "http://127.0.0.1:$Port/healthz") -and
            (Test-Endpoint "http://127.0.0.1:$Port/readyz")) {
            $localReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $localReady) { throw "Local health or readiness check failed." }

    Write-Host "Temporary public host: $(([uri]$origin).Host)"
    Write-Host "Private .env unchanged; current public origin is a process-only override."
    $checkArgs = @(
        "scripts/vobiz_demo_preflight.py", "--env-file", $envFilePath,
        "--public-base", $origin, "--local-base", "http://127.0.0.1:$Port"
    )
    if ($LineId) { $checkArgs += @("--line-id", $LineId) }
    & $python @checkArgs
    if ($LASTEXITCODE -ne 0) { throw "Vobiz demo preflight failed; no carrier dashboard was changed." }

    Write-Host "Local demo mode is running. Copy the protected Answer URL from the authenticated Console."
    Write-Host "A Quick Tunnel hostname changes on restart. Keep this launcher open; Ctrl+C stops both processes."
    while (-not $server.HasExited -and -not $tunnel.HasExited) { Start-Sleep -Seconds 2 }
    throw "Demo server or temporary tunnel exited. Re-run preflight before another call."
} finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
    [Environment]::SetEnvironmentVariable("OMNI_PUBLIC_BASE_URL", $oldPublicBase, "Process")
    Remove-Item -LiteralPath $tunnelOut, $tunnelErr, $serverOut, $serverErr -Force -ErrorAction SilentlyContinue
}
