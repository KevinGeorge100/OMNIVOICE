# Contributing to OmniVoice

OmniVoice is a telephony-first voice infrastructure project. Contributions should preserve live carrier streaming, the Speak / Listen / Idle interruption model, tenant isolation, and confirmation-gated writes. Start with the [README](README.md), [architecture](docs/ARCHITECTURE.md), [current status](docs/PROJECT_STATUS.md), and [backlog](docs/BACKLOG.md).

## Before changing code

1. Identify the backlog item and the exact behavior to change. Keep claims about latency, PSTN behavior, and provider support tied to measured evidence.
2. Work on a task branch from a clean `main`; the repository's [development workflow](.agents/rules/development_workflow.md) documents the branch and review conventions.
3. Never commit `.env`, API keys, carrier stream URLs, real call transcripts, customer knowledge, internal review material, or benchmark exports containing session-level data. See [git hygiene](.agents/rules/git_hygiene.md).
4. If you change carrier audio, VAD, STT/TTS streaming, or actions, include tests that exercise the relevant invariants. The [definition of done](docs/DEFINITION_OF_DONE.md) and repository validation skills explain the expected checks.

## Validate locally

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check omnivoice tests
.\.venv\Scripts\python.exe tests/browser_check.py
git diff --check
powershell -ExecutionPolicy Bypass -File .\scripts\verify-dod.ps1
```

The release gate also builds the separate Next.js product site. For documentation-only changes, review Markdown links, GitHub anchor names, Mermaid rendering, and factual claims. Describe any check you could not run in the pull request.

## Pull request evidence

Explain the trigger, the resulting behavior, the test evidence, and the limits of any measurement. Distinguish local synthetic tests, a live-gateway harness, real PSTN calls, and physical acoustic mouth-to-ear timing. The [PR template](.github/PULL_REQUEST_TEMPLATE.md) keeps that distinction visible to reviewers.

No public license has been selected for this repository yet. Do not assume a permission grant beyond what the repository owner publishes.
