# OmniVoice — Development Workflow Rule

This rule governs the standard development lifecycle for all AI-assisted engineering and pair programming within the OmniVoice repository.

---

## 1. Engineering Lifecycle

```text
REQUIREMENT
    ↓
OV BACKLOG
    ↓
TASK BRANCH
    ↓
PLAN
    ↓
IMPLEMENT
    ↓
TEST
    ↓
RELEASE GATE (scripts/verify-dod.ps1)
    ↓
CODERABBIT REVIEW (cr review --uncommitted)
    ↓
TRIAGE FINDINGS
    ↓
FIX VALID IN-SCOPE FINDINGS
    ↓
RELEASE GATE AGAIN IF CODE CHANGED
    ↓
COMPLETION REPORT
    ↓
HUMAN APPROVAL
    ↓
COMMIT
    ↓
FAST-FORWARD MAIN
    ↓
PUSH
    ↓
DELETE TASK BRANCH
```

---

## 2. Phase Definitions

### Step 1: Requirement & Backlog Alignment
* Work must never proceed on vague requests. Every task must trace to a documented backlog item (`OV-XXX` in `docs/BACKLOG.md`) or define one before writing code.
* Dependencies must be confirmed as satisfied.

### Step 2: Task Branch Setup
* Branch off an up-to-date, clean `main` (`task/<OV-ID>-description`). Never work directly on `main`.

### Step 3: Planning
* Confirm Definition of Ready: clear boundaries, identified files in scope, explicit non-goals, and objective testable criteria.
* Create or update implementation plan before non-trivial changes.

### Step 4: Implementation
* Implement the minimum necessary changes to satisfy the acceptance criteria.
* Maintain clean git hygiene (adhere to `.agents/rules/git_hygiene.md`).
* Maintain theme conventions (adhere to `.agents/rules/theme_preference.md` — White/Light default).
* Maintain strict architectural honesty (no synthetic claims, no scope expansion).

### Step 5: Testing
* Run unit, streaming, and integration tests (`pytest tests/`).
* Run frontend tests (`npm run build` in `landing/` and Playwright E2E in `tests/browser_check.py`).

### Step 6: Release Gate
* Execute deterministic release gate: `powershell -ExecutionPolicy Bypass -File scripts/verify-dod.ps1`.
* All 6 gates must pass: Pytest, Ruff (`omnivoice` and `tests`), Next.js build, Browser E2E, Git hygiene, and Whitespace integrity.

### Step 7: Independent Review (CodeRabbit)
* Run CodeRabbit CLI (`cr review --uncommitted`) on the uncommitted diff.
* CodeRabbit serves as an independent reviewer and must never automatically edit, commit, or merge code.

### Step 8: Triage & Fix
* Triage all findings into: `VALID — IN SCOPE`, `VALID — NEW BACKLOG CANDIDATE`, `FALSE POSITIVE / NOT APPLICABLE`, or `INFORMATIONAL`.
* Fix only valid in-scope items. If changes are made, re-execute `scripts/verify-dod.ps1`.

### Step 9: Completion Report & Review
* Audit changes against `docs/DEFINITION_OF_DONE.md`.
* Produce structured Task Completion Report per `.agents/rules/task_execution.md`.
* Wait for explicit human approval before staging, committing, or merging.

### Step 10: Commit, Merge & Cleanup
* Following human approval: commit to task branch, fast-forward merge to `main`, push to remote, and delete the task branch.
* Update `docs/PROJECT_STATUS.md` and `docs/BACKLOG.md` to reflect the completed state.

---

## 3. Strict Rule Against Scope Expansion

> [!CRITICAL]
> **Antigravity must not silently expand scope.**
> If an agent discovers an unrelated bug, missing feature, dead code, or refactoring opportunity while executing a task:
> 1. **DO NOT** automatically fix it.
> 2. **DO NOT** rewrite or refactor unrelated files.
> 3. **DO** report the discovery in the task report.
> 4. **DO** propose a new structured backlog item (`OV-XXX`) for future prioritization.
