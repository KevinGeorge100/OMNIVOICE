$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' -m omnivoice.preflight
if ($LASTEXITCODE -ne 0) { throw 'Review preflight found items needing attention. See messages above.' }
