# Architecture Decision Records (ADR)

This directory documents significant architectural decisions made for the OmniVoice telephony platform.

---

## What is an ADR?

An Architecture Decision Record (ADR) captures a single architectural decision along with its context, alternatives considered, and consequences. It serves as historical memory so future engineers and AI agents do not reopen decided topics or make conflicting changes without understanding historical trade-offs.

---

## ADR Template Format

When recording a human-approved architectural decision, create a new numbered markdown file in this directory (e.g. `docs/adr/ADR-001-sample.md`) using this template:

```markdown
# ADR-XXX: [Decision Title]

Status: [Proposed | Accepted | Deprecated | Superseded by ADR-YYY]
Date: YYYY-MM-DD
Deciders: [Names / Stakeholders]

## Context
What is the problem or architectural challenge we are facing?
What technical, operational, or business forces influence this decision?

## Decision
What is the specific change or architectural choice we are committing to?

## Alternatives Considered
1. [Alternative A]: Why was it not chosen?
2. [Alternative B]: Why was it not chosen?

## Consequences
### Positive
* What benefits, guarantees, or simplifications do we gain?

### Negative / Trade-offs
* What complexity, latency, cost, or limitations do we accept?

## Follow-up & Dependencies
What backlog items (`OV-XXX`) or milestones implement this decision?
```

---

## ADR Index

| ADR # | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| [ADR-001](ADR-001-turn-taking-stabilization.md) | State-Aware Turn-Taking and Continuation Coalescing | Accepted | 2026-09-21 |

> [!NOTE]
> Per OmniVoice engineering governance rules, AI agents **must not invent ADRs** for architectural decisions that human stakeholders have not explicitly approved.
