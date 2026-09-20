$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required.' }
    & '.\.venv\Scripts\python.exe' -m pip install -c requirements.lock -e '.[dev,semantic]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& '.\.venv\Scripts\python.exe' -m omnivoice.cli init
& '.\.venv\Scripts\python.exe' -m omnivoice.cli serve
