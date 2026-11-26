# DOCS.md — where things are and who owns them

Read with `docs/api-spec.md` (the contract) and `AGENTS.md` (the rules). The team guide PDFs are in `docs/team/`.

## Codebase map

| Path | What lives there | Owner |
|---|---|---|
| `config/` | settings (env-driven), root urls, wsgi/asgi, `celery.py` | B1 (Celery), each task fills its TODO(ID) in settings |
| `landchain/api_urls.py` | mounts every app's `urls.py` under `/api/v1/` | shared |
| `landchain/core/` | errors, ids, health (B1) · pagination, permissions, privacy (C1) · idempotency, ratelimit (D1) · request id + chain headers middleware (B6) | B / C / D |
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

Every endpoint is built; each view's docstring names its route, permission and spec section.
Local-only extra route: `GET /dev/vault/<token>` serves vault files when Supabase Storage isn't configured.

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

**Model field names** are exactly spec §7, with these additions: `Parcel.applicant_address/applicant_public_id`
(privacy needs the applicant), `ChainIdentity.submitted_at`, `TxIntent.success_message/submitted_at`,
`HistoryEvent.log_index`, `ChainTx.from_public_id/record_ids/tx_index`, `Notification.dedupe_key/relay/relay_extra/
relayed_at`, `IdempotencyRecord` (core). `PaymentReceipt` is keyed by its `intent`; `payment_id` is filled in by the
indexer when it sees the `PaymentRecorded` event with the same receipt hash.

**Chain writes** (`landchain/chain/service.py`):

```python
prepare(*, profile, contract, function, args, label, success, action=None, idempotency_key=None) -> TxIntent
write(*, signer, contract, function, args, label, success, by, target, note=None, request=None,
      action=None, idempotency_key=None) -> TxIntent          # signer: "registrar" | "id_officer" | "admin"
wait_for(intent, timeout=30) -> TxIntent                     # ?wait=true
confirm_indexed(up_to_block, result_for=None) -> int         # called by the indexer
```
Both raise `ChainRevert` (the contract's own sentence; HTTP status from spec §10.2) after writing a `RevertLog`.
Views answer with `landchain.chain.views.intent_response(request, intent, created=..., then=..., extra=...)`.

**Privacy** (`landchain/core/privacy.py`): `can_see_private(viewer, parcel)`, `private_parcel_q(viewer)`,
`shown_name(viewer, public_id, people=None)`, `person_ref(viewer, public_id, people=None)`,
`person_ref_for_address(viewer, address, people=None)`, `can_see_contact`, `can_see_receipt_numbers`,
`can_read_enquiry`, `can_see_officer_actions`. `PeopleIndex` caches lookups for one request.

**Helpers other apps call**: `registry.selectors.current_parcel(parcel_id, record_id=None)`, `open_transfer`,
`address_for_public_id`; `notifications.service.notify(kind, text, recipient_public_id|recipient_role, ...)`;
`documents.service.attach_for_record(record_id, applicant_address)`; `core.ratelimit.limit(request, group)`;
`core.idempotency.idempotent` (view decorator); `core.permissions.viewer(request)`.

**Error codes**: spec §10.1, raised through `landchain/core/errors.py` (`ApiError`, `Validation`, `Forbidden`,
`Private`, `NotFound`, `Conflict`, `ChainRevert`, `ChainUnavailable`, `SignerUnavailable`).

**Decisions taken while building** (spec §18): citizens sign with their own wallet (prepare + MetaMask, dev-sign on
Ganache); shared role wallets + `OfficerAction`; enquiries readable by the owner only; officer endpoints are async
unless `?wait=true`; `GET /identities/lookup` always answers 200 with `exists` (no 404), so existence doesn't leak
through status codes; enquiries are refused (409) on pending and rejected parcels because there is no owner yet.
