param(
    [int]$Port = 8000,
    [string]$Database = "data/demo/omnivoice-demo.db"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) { throw "cloudflared is not installed or not on PATH." }
if (-not (Test-Path -LiteralPath $python)) { throw "Local .venv Python is missing." }
$databasePath = if ([System.IO.Path]::IsPathRooted($Database)) {
    [System.IO.Path]::GetFullPath($Database)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $root $Database))
}
if (-not (Test-Path -LiteralPath $databasePath)) {
    throw "Demo database missing. Run scripts/seed_demo.py first."
}
$listener = [System.Net.Sockets.TcpClient]::new()
try {
    $listener.Connect("127.0.0.1", $Port)
    throw "Port $Port is already in use. Stop the existing local server first."
} catch [System.Net.Sockets.SocketException] {
    # An unused port is expected.
} finally {
    $listener.Dispose()
}

$logBase = Join-Path ([System.IO.Path]::GetTempPath()) ("omnivoice-tunnel-" + [guid]::NewGuid().ToString("N"))
$stdoutPath = "$logBase.out"
$stderrPath = "$logBase.err"
$tunnel = $null
try {
    $tunnel = Start-Process -FilePath $cloudflared -ArgumentList @(
        "tunnel", "--url", "http://127.0.0.1:$Port", "--no-autoupdate", "--loglevel", "info"
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $origin = $null
    for ($i = 0; $i -lt 45; $i++) {
        if ($tunnel.HasExited) { throw "Cloudflare tunnel exited before receiving a public URL." }
        Start-Sleep -Seconds 1
        $output = @()
        if (Test-Path -LiteralPath $stdoutPath) { $output += Get-Content -LiteralPath $stdoutPath -Raw }
        if (Test-Path -LiteralPath $stderrPath) { $output += Get-Content -LiteralPath $stderrPath -Raw }
        $match = [regex]::Match(($output -join "`n"), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) { $origin = $match.Value; break }
    }
    if (-not $origin) { throw "Cloudflare tunnel URL was not reported within 45 seconds." }
    $env:OMNI_PUBLIC_BASE_URL = $origin
    $env:OMNI_DATABASE = $databasePath
    Write-Host "Temporary public origin: $origin"
    Write-Host "This origin is temporary. Configure the carrier dashboard manually with the protected URL from OmniVoice."
    Write-Host "Starting the local voice engine. Ctrl+C stops this launcher."
    Push-Location $root
    try { & $python -m omnivoice.cli serve --host 127.0.0.1 --port $Port }
    finally { Pop-Location }
} finally {
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
}
