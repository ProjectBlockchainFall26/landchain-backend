# DOCS.md — where things are and who owns them

Read with `docs/api-spec.md` (the contract) and `AGENTS.md` (the rules). The team guide PDFs are in `docs/team/`.

## Codebase map

| Path | What lives there | Owner |
|---|---|---|
| `config/` | settings (env-driven), root urls, wsgi/asgi, `celery.py` | B1 (Celery), each task fills its TODO(ID) in settings |
| `landchain/api_urls.py` | mounts every app's `urls.py` under `/api/v1/` | shared |
| `landchain/core/` | errors, ids, health (B1) · pagination, permissions, privacy (C1) · idempotency, ratelimit (D1) · chain headers middleware (B6) · `stubs.py` (delete when unused) | B / C / D |
| `landchain/accounts/` | Profile, WalletNonce, Supabase JWT auth, `/me`, wallet linking, officer admin | Person A |
| `landchain/notifications/` | Notification models, inbox endpoints, `notify()` helper, email/SMS relay | Person A |
| `landchain/enquiries/` | Enquiry model, send/inbox/mark endpoints | Person A |
| `landchain/demo/` | `seed_demo_users`, `/dev/demo-accounts` | Person A |
| `landchain/chain/` | web3 client, contract loader, encoding, simulate, TxIntent/OfficerAction/RevertLog, `service.py` (prepare/write), signer tasks, intent endpoints, `/config`, `/chain/status`, admin chain tools | Person B |
| `landchain/indexer/` | cursor/block/event/tx models, runner + handlers, `run_indexer`, reorg + resync, `/activity`, side effects | Person C |
| `landchain/registry/` | projection models + parcel reads + `geo.py` (C) · `views_identity.py` (B8) · `views_applications.py`, `views_transfers.py`, `views_review.py` (D) | C (models) |
| `landchain/fees/` | `schedule.py`, fee endpoints, PaymentReceipt, payments (D) · Payment projection + receipt view (C) | D / C |
| `landchain/documents/` | Document model, Supabase Storage client, upload/url/check, cleanup | Person D |
| `contracts/` | ABIs + deployments copied by `sync_contracts` | B2 |
| `scripts/supabase/` | one-off SQL for the Supabase project | A1 |
| `postman/` | collection + environments | D1 keeps tests in sync; everyone updates their requests |
| `docs/` | `api-spec.md` (contract), `api-spec.html`, `team/` PDFs | shared |
| `tests/` | cross-app tests (route smoke test; acceptance suite in J3) | shared |

Every endpoint already has a stub view that returns 501. Its docstring names the task, owner and spec section.
Every `models.py` lists the tables to build (spec section 7) as comments.

## Tasks and dependency order

Stage = dependency order, not time: anything whose dependencies are done can start. Issues on GitHub hold the details.

| Task | Title | Owner | Depends on | Stage |
|---|---|---|---|---|
| A1 | Supabase project setup (schema, extensions, Auth, Storage) | Accounts, Auth & Inbox | – | 0 |
| A2 | Profile model + Supabase JWT authentication (+ local dev login) | Accounts, Auth & Inbox | A1, J1 | 1 |
| A3 | `GET /me` and `PATCH /me` | Accounts, Auth & Inbox | A2, C1 | 2 |
| A4 | Wallet linking with Sign-In with Ethereum | Accounts, Auth & Inbox | A2, B2 | 2 |
| A5 | Officer management (admin) | Accounts, Auth & Inbox | A2, C1 | 2 |
| A6 | Demo users: `seed_demo_users` + `/dev/demo-accounts` | Accounts, Auth & Inbox | A2, A5 | 3 |
| A7 | Notifications: models, inbox endpoints and email/SMS relay | Accounts, Auth & Inbox | A2, B1 | 2 |
| A8 | Enquiries: send, owner inbox, mark read/answered | Accounts, Auth & Inbox | A7, C2, D1 | 3 |
| B1 | Error format, ID helpers, health check, Celery + Redis | Chain Layer | J1 | 1 |
| B2 | web3 client, contract loader and encoding rules | Chain Layer | J1 | 1 |
| B3 | TxIntent, OfficerAction, RevertLog + simulation | Chain Layer | B2, A2, B1 | 2 |
| B4 | `chain.prepare()` / `chain.write()` + signer queues | Chain Layer | B3, D1 | 3 |
| B5 | Intent endpoints + intent watcher | Chain Layer | B4 | 4 |
| B6 | `GET /config`, `GET /chain/status` + chain freshness headers | Chain Layer | B2, C2 | 2 |
| B7 | Admin chain tools: role wallets and signer health | Chain Layer | B4, C1 | 4 |
| B8 | Identity endpoints (submit, list, lookup, verify, reject) | Chain Layer | B4, C2, C1 | 4 |
| C1 | Pagination, permission classes and privacy rules | Indexer & Read Side | J1 | 1 |
| C2 | Indexer + projection models (PostGIS) and migrations | Indexer & Read Side | A1, J1 | 1 |
| C3 | `run_indexer`: follow contract events into Postgres | Indexer & Read Side | C2, B2, B1 | 2 |
| C4 | Reorg / fresh-chain handling + `POST /admin/indexer/resync` | Indexer & Read Side | C3, C1 | 3 |
| C5 | Parcel and map reads (+ `/stats`, `/me/parcels`) | Indexer & Read Side | C2, C1 | 2 |
| C6 | Geometry: `geo.py` + `POST /parcels/boundary-check` | Indexer & Read Side | C2 | 2 |
| C7 | Activity log `GET /activity` | Indexer & Read Side | C3, B3, C1 | 3 |
| C8 | Indexer side effects: notifications, document attach, confirm intents | Indexer & Read Side | C3, A7, D2, B3 | 3 |
| C9 | Statement of costs `GET /parcels/{parcel_id}/receipt` | Indexer & Read Side | C5, D4, C3 | 5 |
| D1 | Idempotency keys, rate limits, OpenAPI docs and Postman tests | Workflows, Files & Fees | B1 | 2 |
| D2 | Document vault (Supabase Storage) | Workflows, Files & Fees | A1, A2, C1 | 2 |
| D3 | Fee schedule and estimates | Workflows, Files & Fees | J1 | 1 |
| D4 | Payments: record and list fees | Workflows, Files & Fees | B4, C2, C1, D3 | 4 |
| D5 | Applications: submit, list, review, approve, reject | Workflows, Files & Fees | B4, C2, C6, D2, D3 | 4 |
| D6 | Transfers: request, cancel, review, approve, reject | Workflows, Files & Fees | B4, C2, B8, D4 | 5 |
| D7 | Review queue and nav badge counts | Workflows, Files & Fees | C2, C1 | 2 |
| J1 | Interface freeze: model fields, service signatures, error codes | All | – | 0 |
| J2 | First end-to-end flow: submit and approve an application (B + C + D) | All | B5, C3, D5, D4 | 5 |
| J3 | Acceptance tests from spec §17 + full Postman run | All | J2, A8, B7, C8, C9, D6, D7, A6 | 6 |
| J4 | Frontend integration with landchain-web | All | J3 | 7 |

## Interfaces (filled in by J1)

TODO(J1): paste the agreed model field names, the `chain.service.prepare/write` signatures, the
`core.privacy` signatures and the error code list here.
