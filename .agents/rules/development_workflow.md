# OmniVoice — Development Workflow Rule

This rule governs the standard development lifecycle for all AI-assisted engineering and pair programming within the OmniVoice repository.

---

## 1. Engineering Lifecycle

```text
PRODUCT REQUIREMENT
        ↓
   BACKLOG ITEM
        ↓
DEFINITION OF READY
        ↓
  IMPLEMENTATION
        ↓
 AUTOMATED TESTS
        ↓
MANUAL / INTEGRATION VALIDATION
        ↓
      REVIEW
        ↓
DEFINITION OF DONE
        ↓
      MERGE
```

---

## 2. Phase Definitions

### Step 1: Backlog Item Alignment
* Work must never proceed on vague requests. Every task must trace to a documented backlog item (`OV-XXX` in `docs/BACKLOG.md`) or define one before writing code.
* Dependencies must be confirmed as satisfied.

### Step 2: Definition of Ready (DoR)
Before writing code, verify:
1. Is the goal clear and bounded?
2. Are the specific files and subsystems in scope identified?
3. Are the non-goals explicitly stated?
4. Are the acceptance criteria testable and objective?

### Step 3: Implementation
* Implement the minimum necessary changes to satisfy the acceptance criteria.
* Maintain clean git hygiene (adhere to `.agents/rules/git_hygiene.md`).
* Maintain theme conventions (adhere to `.agents/rules/theme_preference.md` — White/Light default).

### Step 4: Automated Testing
* Run unit and integration tests using `pytest tests/`.
* For frontend changes, run `npm run build` in `landing/` or Playwright checks in `tests/browser_check.py`.

### Step 5: Manual / Integration Validation
* Execute relevant scripts (e.g. `tests/model_check.py` or local curl/browser checks) to verify real behavior beyond unit mocks.

### Step 6: Review & Definition of Done Verification
* Audit changes against `docs/DEFINITION_OF_DONE.md`.
* Ensure no secrets, no regressions, and no unsupported marketing claims were introduced.

### Step 7: Completion & Merge
* Update `docs/PROJECT_STATUS.md` and `docs/BACKLOG.md` to reflect the completed state.
* Produce a structured Task Completion Report.

---

## 3. Strict Rule Against Scope Expansion

> [!CRITICAL]
> **Antigravity must not silently expand scope.**
> If an agent discovers an unrelated bug, missing feature, dead code, or refactoring opportunity while executing a task:
> 1. **DO NOT** automatically fix it.
> 2. **DO NOT** rewrite or refactor unrelated files.
> 3. **DO** report the discovery in the task report.
> 4. **DO** propose a new structured backlog item (`OV-XXX`) for future prioritization.
