# AGENTS.md — landchain-backend

Rules for every coding agent (Claude Code, Codex, Cursor, Copilot) and every human on this repo.

## What this repo is
The Django REST backend for LandChain (Ghana land registry on Ethereum). The full contract is
`docs/api-spec.md`: every endpoint, request/response body, model and error message is defined there.
Match it exactly. If the spec and the code disagree, the spec wins; raise an issue to change the spec.

## Setup & commands
- Install: `pip install -r requirements-dev.txt` (or use Docker: `docker compose up`)
- Env: `cp .env.example .env` (ask the team for Supabase and signer values)
- Run: `python manage.py runserver` · Test: `pytest -q` · Lint: `ruff check .` · Checks: `python manage.py check`
- Local chain: run Ganache from `landchain-contracts` (`npm run chain`, port 7545), then `python manage.py sync_contracts`

## Workflow rules
- Work only on a branch named `feature/<TASK-ID>-short-name` (e.g. `feature/A3-me-endpoint`) created from `main`.
  Never commit to `main` or `production`.
- One task (GitHub issue) = one branch = one PR into `main`. Title starts with the task ID.
- Commit format: `<TASK-ID> <type>: <summary>` with type feat | fix | refactor | test | docs | chore.
- Run `ruff check .` and `pytest -q` before every commit. Add tests for new logic.

## Ownership
- Each Django app has an owner (see DOCS.md). Only the owner creates that app's migrations.
- Need something from another person's app? Call their function/selector; don't edit their files. If it
  doesn't exist yet, leave `# TODO(<their task ID>)` and tell them.

## Conventions
- All routes live under `/api/v1/` and are wired in each app's `urls.py`. Stubs return 501 until built.
- JSON keys snake_case; money as decimal strings + integer pesewas; timestamps ISO 8601 UTC (spec section 4).
- Errors always use the shape in spec section 4 via `landchain/core/errors.py`. Never return raw exceptions.
- Every chain write goes through `landchain/chain/service.py` (`prepare` / `write`). Never call web3 directly from a view.
- Privacy decisions only through `landchain/core/privacy.py`.
- Projection tables (spec 7.2) are written only by the indexer.

## Never
- Never read, print or commit `.env`, private keys, the Supabase service-role key or JWT secret.
- Never put personal data on chain (names, files, phone, email).
- Never change CI, AGENTS.md, CLAUDE.md or DOCS.md unless the issue asks for it.
- Never delete another person's TODO.

## Context
See @DOCS.md for the codebase map, owners and agreed interfaces.
