---
name: release-gate
description: >-
  Executes the deterministic OmniVoice Definition of Done release gate script (scripts/verify-dod.ps1) to validate pytest, ruff, Next.js build, browser E2E, git hygiene, and whitespace before completing any task.
---

# OmniVoice Release Gate Validation Skill

Provides a single, standardized, deterministic pre-completion validation procedure for engineering tasks within the OmniVoice repository.

---

## 1. Purpose & Scope

The Release Gate enforces the criteria documented in `docs/DEFINITION_OF_DONE.md` through an automated script: `scripts/verify-dod.ps1`.

Whenever an engineering task reaches its final verification phase (prior to generating completion reports or requesting human review), Antigravity must execute this gate to ensure zero regressions across all repository subsystems.

> [!CRITICAL]
> **Read-Only Verification Only**: This skill and its underlying script NEVER automatically stage, commit, or push code. Human approval remains mandatory before committing or merging changes.

---

## 2. Gate Verification Sequence

The release gate executes 6 deterministic checks in fail-fast mode:

1. **Pytest Test Suite**: Runs `pytest tests/` via virtual environment Python (`.venv/Scripts/python.exe`), verifying all unit, streaming, and API test cases pass.
2. **Ruff Static Analysis**: Runs `ruff check omnivoice tests`, ensuring all backend code and test harnesses adhere to formatting and linting rules with zero errors.
3. **Next.js Production Build**: Runs `npm run build` in `landing/`, validating TypeScript compilation, React 19 typing, and static page generation.
4. **Browser E2E Testing**: Runs `python tests/browser_check.py` using headless Microsoft Edge, validating console authentication, enterprise creation, FAQ addition, carrier modal URLs, and layout responsiveness.
5. **Git Hygiene & Privacy**: Verifies that no sensitive files (e.g. `.env`, internal reviews, budget sheets, personal notes) defined by `.agents/rules/git_hygiene.md` and `.gitignore` are tracked by git.
6. **Whitespace & Diff Integrity**: Runs `git diff --check` to ensure no trailing whitespace, mixed line endings, or conflict markers are introduced.

---

## 3. Execution Procedure

To execute the release gate, run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-dod.ps1
```

### 3.1 Expected Success Output

```text
==================================================
OMNIVOICE DETERMINISTIC RELEASE GATE
==================================================

[1/6] Running Pytest Suite...
[1/6] Pytest Suite: PASSED

[2/6] Running Ruff Static Analysis (omnivoice & tests)...
[2/6] Ruff Static Analysis: PASSED

[3/6] Running Next.js Production Build in landing/...
[3/6] Next.js Production Build: PASSED

[4/6] Running Browser E2E Check (tests/browser_check.py)...
[4/6] Browser E2E Check: PASSED

[5/6] Inspecting Git Hygiene & Sensitive File Tracking...
[5/6] Git Hygiene & Privacy: PASSED (0 sensitive files tracked)

[6/6] Checking Git Diff Whitespace Integrity...
[6/6] Whitespace Integrity: PASSED

==================================================
OMNIVOICE RELEASE GATE: PASS
==================================================
```

### 3.2 Failure Handling Protocol

If any gate fails:
1. **Do NOT silently fix unrelated code**: If failure stems from preexisting product code outside the task scope, report the failure immediately in the task completion report.
2. **Fix In-Scope Defects**: If failure stems from code introduced or modified during the current task, resolve the defect and re-execute the release gate.
3. **Require Zero Warnings / Errors**: The release gate must exit with code `0` before presenting the completion report to the user.
