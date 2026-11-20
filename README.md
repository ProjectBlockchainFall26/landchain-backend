# landchain-backend

Django REST API for **LandChain**, a Ghana land registry on Ethereum. It replaces the browser-only state in
`landchain-web` and is the only thing the frontend talks to: Supabase Auth, an event indexer over the
four contracts in `landchain-contracts`, a document vault, enquiries and every chain write.

> **Status: scaffold.** Every route from the spec exists and returns `501 NOT_IMPLEMENTED` until its task is
> built. Tasks are GitHub issues labelled `person:A` … `person:D`.

## Start here
1. `docs/team/` — main guide and your Person A–D guide (PDF).
2. `docs/api-spec.md` — the contract: endpoints, bodies, models, errors.
3. `AGENTS.md` — rules for you and your coding agent. `DOCS.md` — codebase map and owners.

## Run locally
```bash
cp .env.example .env              # fill Supabase + signer values (ask the A1 owner)
docker compose up                 # db (postgis), redis, api on http://localhost:8000
# or without Docker:
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py runserver
```
Local chain: in `landchain-contracts` run `npm run chain` (Ganache, port 7545) and `npm run setup:all`.

Check a route: `curl -i http://localhost:8000/api/v1/health` → `501` until task B1 is done.

## Test
```bash
ruff check . && python manage.py check && pytest -q
```
Postman: import everything in `postman/` (see `postman/README.md`).

## Branches
- `main` — development. Every task is a `feature/<TASK-ID>-name` branch from `main`, merged by PR.
- `production` — protected. Only the release owner merges `main` → `production`; that deploys.
