# landchain-backend

Django REST API for **LandChain**, a Ghana land registry on Ethereum. It replaces the browser-only state in
`landchain-web` and is the only thing the frontend talks to: Supabase Auth, an event indexer over the
four contracts in `landchain-contracts`, a document vault, enquiries and every chain write.

> **Status: built.** All 58 endpoints in `docs/api-spec.md` are implemented. 82 unit tests run anywhere with
> Postgres + PostGIS; 8 acceptance tests from spec §17 run against a seeded Ganache chain.

## Start here
1. `docs/team/`: the main guide and your Person A–D guide (PDF).
2. `docs/api-spec.md`: the contract: endpoints, bodies, models, errors.
3. `AGENTS.md`: rules for you and your coding agent. `DOCS.md`: codebase map, owners and the agreed interfaces.

## Run locally (with the demo chain)

You need the three repos side by side: `landchain-contracts`, `landchain-web`, `landchain-backend`.

```bash
# terminal 1, in landchain-contracts
npm run chain:fresh                       # Ganache on 127.0.0.1:7545. Leave it running.
# terminal 2, in landchain-contracts
npm run setup:local                       # deploy + seed the demo register

# terminal 2, in landchain-backend
cp .env.example .env                      # local defaults work; Supabase values come from the A1 owner
docker compose up -d db redis             # or your own Postgres with PostGIS + Redis
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py sync_contracts --from ../landchain-contracts/shared   # ABIs + addresses
python manage.py seed_demo_users          # the 8 demo people, linked to their Ganache addresses
python manage.py run_indexer --once       # index the chain into Postgres
python manage.py runserver                # http://localhost:8000/api/v1/health
```

Then keep the read side fresh and send officer transactions, either:

- **Workers (as in production):** `docker compose --profile workers up` (Celery `worker`, `signer` with one
  queue per role wallet at concurrency 1, and `beat` running the indexer every 2 s), or locally
  `celery -A config worker -Q default`, `celery -A config worker -Q signer.registrar,signer.id_officer,signer.admin
  --concurrency 1 -n signer@%h` and `celery -A config beat`.
- **No workers (quick demo):** set `CELERY_TASK_ALWAYS_EAGER=true` in `.env`. Officer actions are then signed
  inline and `?wait=true` runs the indexer itself. Run `python manage.py run_indexer` in another terminal so
  citizen transactions and the map stay fresh.

**Signing in locally.** With `DEBUG=true` and `DEV_AUTH=true`, send `X-Dev-User: ama@demo.landchain.local` (any
demo email) instead of a Supabase token. With Supabase configured, `seed_demo_users` creates real Supabase users
with `DEMO_PASSWORD`, and the login page lists them from `GET /api/v1/dev/demo-accounts`.

**Signer wallets.** On Ganache with no `*_SIGNER_KEY` set, officer transactions are sent from the unlocked
accounts that hold the role on chain (account 0 registrar/admin, account 1 identity officer). On Sepolia, set the
three keys (never commit them). Check them with `python manage.py check_signers` or `GET /api/v1/admin/signers`.

**Documents.** With `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, files go to the private `parcel-documents`
bucket and open through 60-second signed URLs. Without them, files are kept in `VAULT_LOCAL_DIR` and served through
60-second signed links at `/api/v1/dev/vault/<token>`.

After `npm run chain:fresh` + `setup:local`, the indexer notices the new chain and re-indexes on its own (or call
`POST /api/v1/admin/indexer/resync`).

OpenAPI: `GET /api/v1/schema/` (YAML) and Swagger UI at `/api/v1/docs/`.

## Test
```bash
ruff check . && python manage.py check && pytest -q
```
`tests/test_acceptance.py` (spec §17) needs Ganache with the contracts deployed and seeded; it is skipped when the
chain isn't reachable, so CI runs the rest. The acceptance tests create a fresh wallet each run, so they can be
re-run on the same chain.

Postman: import everything in `postman/` (see `postman/README.md`).

## Branches
- `main`: development. Every task is a `feature/<TASK-ID>-name` branch from `main`, merged by PR.
- `production`: protected. Only the release owner merges `main` → `production`; that deploys.
