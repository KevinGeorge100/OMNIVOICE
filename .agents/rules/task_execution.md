# OmniVoice — Task Execution Protocol

This rule defines the mandatory input format and completion report standard for all future AI-assisted engineering tasks in OmniVoice.

---

## 1. Expected Task Specification Format

Every engineering task assigned to Antigravity should structure requirements using this framework:

```markdown
TASK ID: OV-XXX
GOAL: Concise statement of what must be achieved
CONTEXT: Relevant background, previous attempts, and system state
CURRENT BEHAVIOUR: What the system currently does (factual reality)
REQUIRED BEHAVIOUR: What the system must do upon completion
FILES / SUBSYSTEMS IN SCOPE: Explicit list of files or modules to modify
NON-GOALS: Explicit list of things that must NOT be done
CONSTRAINTS: Technical, security, or architectural guardrails (e.g., read-only, no new dependencies)
ACCEPTANCE CRITERIA: Numbered, testable criteria for success
TEST REQUIREMENTS: What automated tests must be written or executed
VALIDATION COMMANDS: Specific shell/test commands to run
DEFINITION OF DONE: References docs/DEFINITION_OF_DONE.md
```

---

## 2. Mandatory Task Completion Report

Upon completing any task, Antigravity **must** produce a structured completion report containing these 10 sections:

1. **Summary**: High-level explanation of what was achieved.
2. **Files Changed**: Table of files created, modified, or deleted with justification.
3. **Behaviour Changed**: Clear before/after description of system behavior.
4. **Tests Added**: Specific test functions or test files implemented.
5. **Tests Executed**: Exact command lines run in the shell.
6. **Test Results**: Exact output counts (e.g., `26 passed in 4.06s`).
7. **Manual Validation Performed**: Specific manual tests, script runs, or browser checks conducted.
8. **Remaining Risks**: Known edge cases, untested failure paths, or technical risks left unaddressed.
9. **Newly Discovered Backlog Candidates**: Unrelated bugs or refactoring opportunities found during work, formatted as proposed `OV-XXX` items.
10. **Git Diff Summary**: Output of `git diff --stat` confirming minimal footprint.
