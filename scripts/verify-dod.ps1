<#
.SYNOPSIS
    OmniVoice Release Gate & Definition of Done (DoD) Verification Script.
.DESCRIPTION
    Executes deterministic pre-completion engineering checks:
    1. Pytest suite
    2. Ruff static analysis (omnivoice & tests)
    3. Next.js production build (landing/)
    4. Browser E2E verification (tests/browser_check.py)
    5. Git hygiene & privacy inspection (tracked file verification)
    6. Git whitespace verification (git diff --check)
#>

$ErrorActionPreference = "Stop"

# 1. Resolve repository root regardless of current working directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..").Path
Set-Location -LiteralPath $RepoRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "OMNIVOICE DETERMINISTIC RELEASE GATE" -ForegroundColor Cyan
Write-Host "Repository Root: $RepoRoot" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvRuff = Join-Path $RepoRoot ".venv\Scripts\ruff.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment Python not found at: $VenvPython"
    exit 1
}

# --- GATE 1: Pytest Test Suite ---
Write-Host "`n[1/6] Running Pytest Suite..." -ForegroundColor Yellow
& $VenvPython -m pytest tests/
if ($LASTEXITCODE -ne 0) {
    Write-Error "GATE 1 FAILED: Pytest test suite reported failures."
    exit $LASTEXITCODE
}
Write-Host "[1/6] Pytest Suite: PASSED" -ForegroundColor Green

# --- GATE 2: Ruff Static Analysis ---
Write-Host "`n[2/6] Running Ruff Static Analysis (omnivoice & tests)..." -ForegroundColor Yellow
if (Test-Path $VenvRuff) {
    & $VenvRuff check omnivoice tests
} else {
    & $VenvPython -m ruff check omnivoice tests
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "GATE 2 FAILED: Ruff lint checks reported violations."
    exit $LASTEXITCODE
}
Write-Host "[2/6] Ruff Static Analysis: PASSED" -ForegroundColor Green

# --- GATE 3: Next.js Production Build ---
Write-Host "`n[3/6] Running Next.js Production Build in landing/..." -ForegroundColor Yellow
$LandingDir = Join-Path $RepoRoot "landing"
Push-Location -LiteralPath $LandingDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Error "GATE 3 FAILED: Next.js production build failed."
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
Write-Host "[3/6] Next.js Production Build: PASSED" -ForegroundColor Green

# --- GATE 4: Browser E2E Check ---
Write-Host "`n[4/6] Running Browser E2E Check (tests/browser_check.py)..." -ForegroundColor Yellow
& $VenvPython tests/browser_check.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "GATE 4 FAILED: Browser E2E check failed."
    exit $LASTEXITCODE
}
Write-Host "[4/6] Browser E2E Check: PASSED" -ForegroundColor Green

# --- GATE 5: Git Hygiene & Privacy Verification ---
Write-Host "`n[5/6] Inspecting Git Hygiene & Sensitive File Tracking..." -ForegroundColor Yellow

# 5a. Detect any tracked files that match .gitignore rules (sensitive/personal/cache)
$IgnoredTracked = & git ls-files -i -c --exclude-standard
if ($LASTEXITCODE -ne 0) {
    Write-Error "GATE 5 FAILED: Unable to query tracked git files."
    exit $LASTEXITCODE
}
if ($IgnoredTracked) {
    Write-Error "GATE 5 FAILED: The following tracked files match .gitignore exclusions:`n$IgnoredTracked"
    exit 1
}

# 5b. Verify sensitive pattern hygiene from git_hygiene.md against all tracked files
$TrackedFiles = & git ls-files
$SensitiveViolations = @()
$SensitiveRegex = '(?i)(\.env($|\.local|\.production|\.development)|docs/.*(review|budget|persona|vision|notes|private)|(^|/)(notes|personal)/)'

foreach ($file in $TrackedFiles) {
    if ($file -eq ".env.example") {
        continue
    }
    if ($file -match $SensitiveRegex) {
        $SensitiveViolations += $file
    }
}

if ($SensitiveViolations.Count -gt 0) {
    Write-Error "GATE 5 FAILED: Protected/internal files are tracked in git:`n$($SensitiveViolations -join "`n")"
    exit 1
}
Write-Host "[5/6] Git Hygiene & Privacy: PASSED (0 sensitive files tracked)" -ForegroundColor Green

# --- GATE 6: Whitespace Integrity ---
Write-Host "`n[6/6] Checking Git Diff Whitespace Integrity..." -ForegroundColor Yellow
& git diff --check
if ($LASTEXITCODE -ne 0) {
    Write-Error "GATE 6 FAILED: Whitespace errors detected in git diff."
    exit $LASTEXITCODE
}
Write-Host "[6/6] Whitespace Integrity: PASSED" -ForegroundColor Green

# --- SUMMARY ---
Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "OMNIVOICE RELEASE GATE: PASS" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
exit 0
