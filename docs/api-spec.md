> Source: LandChain Django API Spec (generated 20 Nov 2026). The original page is `docs/api-spec.html`.
> This file is the contract for the backend. Change it only through a PR that all owners approve.

LandChain Ghana · Django REST backend · API v1

# LandChain Django API Spec

Full specification for the Django backend behind the `landchain-web` UI and the `landchain-contracts` Solidity contracts. It covers every feature the current web app has, the request and response body of every endpoint, Supabase authentication, and how the API talks to the blockchain. I derived it from the code at `landchain-web@ce033f8` (`src/lib/landchain/*`, every route) and the four contracts in `landchain-contracts/contracts`. It is written so another engineer or an AI agent can build the backend from this page alone.

Generated 20 Nov 2026. Stack assumed: Django 5.1 + Django REST Framework, Supabase (Auth, Postgres with PostGIS, Storage), web3.py v7, Celery + Redis, Ganache (chain id 1337) locally and Sepolia (11155111) later.

## 1. What the backend does

Today the web app has no backend. It reads the contracts straight from the browser (scanning every event every 3 seconds), signs with MetaMask or Ganache's unlocked accounts, and keeps all off-chain data in the browser: names in `localStorage`, document files in IndexedDB (`vault.ts`), enquiries in `localStorage` (`enquiries.ts`), and reverted calls in `localStorage`. The backend replaces all of that and becomes the only thing the UI talks to.

It has six jobs:

1. **Authentication and accounts.** Supabase Auth signs people in. Django verifies the Supabase JWT on every request, keeps a profile per user (name, contact, linked wallet, roles) and links one wallet per person with a signed message (Sign-In with Ethereum).
2. **All blockchain interaction through the API.** Reads come from Django's own Postgres index of the chain. Writes go through the API: officer actions are signed by role wallets the backend holds; citizen actions are prepared by the API as unsigned transactions, signed in the citizen's wallet, and tracked by the API until they are mined.
3. **Event indexer.** A worker follows the four contracts' events from the deployment's `startBlock` into Postgres, so the UI stops scanning the chain. It builds parcels, applications, transfers, payments, history, the activity log and notifications.
4. **Document vault.** Files (site plan, indenture, search report, consent) go to a private Supabase Storage bucket keyed by their SHA-256 fingerprint. Only Lands Commission officers and the parcel's owners can open them. Anyone can check a copy against the on-chain fingerprint.
5. **Enquiry inbox.** A visitor sends a message about a parcel; the backend relays it to the owner by email or SMS without revealing who the owner is.
6. **Privacy enforcement.** The rules in `privacy.ts` move to the server. The API never returns a name, document, fee or contact detail to someone who may not see it.

**The contracts stay the source of truth.** Every business rule is a `require` in Solidity. The backend pre-checks the same rules so it can answer quickly with a clear message, and it simulates every transaction with `eth_call` before sending, so a refusal comes back with the contract's own sentence and no gas is spent. Never put a rule only in Django that the contract does not also enforce, and never put personal data on chain (no names, file names, card numbers, phone numbers, emails).

**Out of scope** (cut on 19 Nov 2026, keep them out unless the team decides otherwise): marketplace, escrow, test cedis, disputes, surveyor/lawyer/judge roles, subdivision, leases, mortgages, inheritance, key recovery.

## 2. Architecture

```
  Browser (TanStack Start app)
   │  supabase-js: sign in, refresh token ─────────────► Supabase Auth
   │  fetch /api/v1/*  Authorization: Bearer <Supabase access token>
   │  MetaMask: eth_sendTransaction(tx prepared by the API)  ──────────┐
   ▼                                                                    │
  Django + DRF  (api.landchain…)                                        │
   ├─ auth: verifies Supabase JWT (JWKS), loads Profile                 │
   ├─ apps: accounts · identity · parcels · applications · fees ·       │
   │        transfers · documents · enquiries · notifications · chain   │
   ├─ web3.py ── eth_call / estimateGas / build tx ──────────────────► RPC (Ganache :7545 / Sepolia)
   │                                                                    ▲
   ├─ Supabase Postgres (+PostGIS)  schema "landchain"                  │
   ├─ Supabase Storage  bucket "parcel-documents" (private)             │
   └─ Redis ◄─► Celery workers                                          │
        ├─ indexer      follows contract events → Postgres ─────────────┤
        ├─ signer       one queue per role wallet, signs + sends ───────┤
        ├─ tx-watcher   receipts for citizen-submitted hashes ──────────┘
        └─ notifier     email / SMS relay (enquiries, decisions)
```

| Piece | Choice | Why |
| --- | --- | --- |
| Web framework | Django 5.1, DRF 3.15, drf-spectacular for OpenAPI | Team doc (Doc 1) names Django. OpenAPI schema at `/api/v1/schema/` lets the frontend generate types. |
| Auth | Supabase Auth (email + password, magic link, phone OTP). Django only verifies tokens. | No password handling in Django. Same token works for Supabase Storage and Realtime if needed. |
| Database | Supabase Postgres, PostGIS extension enabled, Django tables in a non-exposed schema `landchain` | PostGIS does the boundary overlap check (PROJECT\_CONTEXT P2 item). A separate schema keeps tables away from Supabase's auto-generated PostgREST API. |
| Files | Supabase Storage private bucket, accessed with the service-role key from Django only | Replaces IndexedDB vault. Signed URLs expire in 60 seconds. |
| Chain library | web3.py 7.x, eth-account | Python equivalent of web3.js v4 used by the frontend. ABIs come from `landchain-contracts/shared/abi/*.json`. |
| Jobs | Celery 5 + Redis (or Supabase-hosted Redis alternative such as Upstash) | Indexer loop, serialized signing per role wallet, notification relay. |
| Geometry | PostGIS + shapely + pyproj | Area in acres and overlap checks on the server. |

## 3. Feature inventory (from the UI)

Every screen in `src/routes` and what it needs from the backend. The endpoint names link to section 9.

| Screen (route) | Who | What it does today | Endpoints it will use |
| --- | --- | --- | --- |
| Sign in (`/login`) | Everyone | Connect MetaMask, or pick a seeded Ganache demo account, or continue as public visitor | Supabase sign-in; `GET /me`; `POST /auth/wallet/nonce`, `POST /auth/wallet/verify`; `GET /dev/demo-accounts` (local only) |
| Land Map (`/`) | Everyone | Map of all non-rejected parcels, status filters, search by parcel ID / owner public ID / token #, selected-parcel card, "Register snapshot" stats | `GET /parcels?format=geojson`, `GET /parcels/search`, `GET /stats` |
| Identity (`/identity`) | Citizen | Enter name (kept off chain) and Ghana Card number (hashed in browser), choose citizen / non-citizen, submit to `IdentityRegistry.submitProfile` | `PATCH /me`, `POST /identity/submit` (prepare), `GET /me` |
| Register Land (`/register`) | Verified citizen | Draw boundary (≥3 pillars), live area + plots count + overlap check, parcel ID (suggested next id), interest, allodial holder, region, plan number, GhanaPostGPS, upload 3 required + 1 optional documents (SHA-256), submit application | `GET /parcels/next-id`, `POST /parcels/boundary-check`, `POST /documents`, `POST /applications` (prepare), `GET /chain/intents/{id}` |
| My Parcels (`/parcels`) | Citizen | Parcels currently owned, total acres, title view per parcel | `GET /me/parcels`, `GET /parcels/{parcel_id}` |
| Title record (`/title/$parcelId`) | Everyone (privacy-filtered) | Status banner; Registration (application decision, plan no., GPS, interest); Ownership (current owner, owner history, open transfer, Transfer / Cancel buttons, Enquire); Documents (open file, check a copy); Fees; Enquiries inbox (owner); On-chain history; GPS boundary in DMS; Smart contract record ids | `GET /parcels/{id}`, `GET /parcels/{id}/history`, `GET /documents/{sha256}/url`, `POST /parcels/{id}/documents/check`, `GET /parcels/{id}/payments`, `GET /me/enquiries?parcel_id=`, `POST /parcels/{id}/enquiries`, `GET /identities/lookup`, `POST /transfers`, `POST /transfers/{id}/cancel` |
| Receipt (`/receipt/$parcelId`) | Owner, officers | Statement of costs: official fees in cedis + gas used × gas price for every transaction on the parcel, owner-signed share, printable | `GET /parcels/{id}/receipt` |
| Review Queue (`/review`) | Officers | Identity requests (identity officer: verify / reject); Land registrations (registrar: open documents, record fees, approve / reject with reason); Ownership transfers (registrar: record transfer fee, approve / reject) | `GET /review/queue`, `POST /identities/{public_id}/verify|reject`, `POST /parcels/{id}/payments`, `POST /applications/{id}/approve|reject`, `POST /transfers/{id}/approve|reject` |
| Verify (`/verify`) | Public | Look up a title by parcel ID; table of all registered titles with status, owner public ID, size, owners-so-far count | `GET /parcels?status=registered,transfer_pending,pending`, `GET /parcels/{id}` |
| Activity Log (`/activity`) | Everyone | Every contract call including reverted ones; filter by parcel, person, contract, status | `GET /activity` |
| Assumptions (`/assumptions`) | Everyone | Static list of 12 assumptions | None (static). Optional `GET /config` for chain name. |
| Shell: account menu, notifications bell, chain status | Signed in | Switch demo account, connect MetaMask, notifications for me and my role, chain error banner, pending-count badge | `GET /me/notifications`, `POST /me/notifications/read`, `GET /chain/status`, `GET /review/counts` |

## 4. API conventions

- **Base URL:** `{API_URL}/api/v1`. Frontend env var `VITE_API_URL` (e.g. `http://127.0.0.1:8000`). All paths below are relative to `/api/v1`. Trailing slashes optional (`APPEND_SLASH=False`, routers with `trailing_slash="/?"`).
- **Format:** JSON in and out, `Content-Type: application/json`, UTF-8. Uploads are `multipart/form-data`. Keys are `snake_case`.
- **Auth header:** `Authorization: Bearer <supabase_access_token>`. Endpoints marked Public work without it; with it, they return more fields when privacy allows.
- **IDs** keep the formats the UI already shows:
  - Parcel ID `GA-BRK-0015` (regex `^[A-Z]{2}-[A-Z]{3}-\d{4}$`). A rejected application frees its parcel ID, so one parcel ID may have several on-chain records; the API always resolves a parcel ID to the **latest** record. `record_id` (integer, TitleRegistry index + 1) is also returned.
  - Application `APP-{appId}`, transfer `TRF-{transferId}`, payment `PAY-{paymentId}`: the on-chain ids with a prefix. Path parameters accept `APP-7` or `7`.
  - Title number `GLT #{tokenId}`, returned as integer `title_no`.
  - Public ID `GH-7d4e894d`: `"GH-" + first 4 bytes of keccak256(address)`, the same as `IdentityRegistry.publicIdOf`.
  - Backend-only objects (intents, documents, enquiries, notifications) use prefixed ULIDs: `txi_01JD…`, `doc_01JD…`, `enq_01JD…`, `ntf_01JD…`.
- **Timestamps:** ISO 8601 UTC strings (`"2026-11-19T13:47:15Z"`). The frontend currently uses epoch milliseconds; convert with `Date.parse`. Block timestamps come from the chain (seconds) and are converted.
- **Money:** cedis as a decimal string with 2 places, plus integer pesewas: `"amount_ghs": "1178.00", "amount_pesewas": 117800`. Never floats.
- **Area:** `"acres": "1.24"` (string, 2 places) and `"acres_x100": 124` as stored on chain.
- **Coordinates:** `[lat, lng]` arrays in decimal degrees (floats, 6 decimals). On chain they are int32 micro-degrees; the API returns both when relevant.
- **Hashes and addresses:** lowercase `0x`-prefixed hex. Addresses are accepted in any case and stored lowercase.
- **Pagination:** list endpoints take `?page=1&page_size=50` (max 200) and return `{"count", "next", "previous", "results"}`. The activity log and notifications also accept `?before=<iso>` for infinite scroll.
- **Filtering:** comma-separated values for enums (`?status=pending,registered`).
- **Idempotency:** every `POST` that sends a transaction or records money accepts `Idempotency-Key: <uuid>`. Same key + same user within 24 h returns the first response instead of sending twice. The UI should send one per button click.
- **Chain freshness:** every read response carries headers `X-Chain-Id`, `X-Indexed-Block` and `X-Chain-Head` so the UI can show "indexed up to block N".
- **Errors:** one shape everywhere (section 10):

  ```
  {
    "error": {
      "code": "CHAIN_REVERT",
      "message": "Only the owner can transfer this title",
      "revert_reason": "Only the owner can transfer this title",
      "field_errors": null,
      "request_id": "req_01JD2ZQ7…"
    }
  }
  ```
- **Rate limits** (django-ratelimit, by user, or by IP when anonymous): enquiries 5/hour/IP and 20/day/IP; document check 30/min; prepare endpoints 20/min/user; wallet nonce 10/min/IP. Exceeding returns `429 RATE_LIMITED` with `Retry-After`.
- **CORS:** allow the frontend origins (`http://localhost:5173`, the deployed URL) with credentials off (bearer tokens, no cookies).

## 5. Auth with Supabase

Supabase Auth owns sign-up, sign-in, passwords, OTPs, sessions and token refresh. Django never sees a password. The browser uses `@supabase/supabase-js`; Django checks the access token on each request and maps the Supabase user (`sub`) to a `Profile` row.

### 5.1 Identity layers

| Layer | What it proves | Where it lives |
| --- | --- | --- |
| Supabase user | This person controls this email or phone | `auth.users` (Supabase), id = JWT `sub` |
| Linked wallet | This person controls this Ethereum address (signed a SIWE message) | `landchain.profile.wallet_address`, unique |
| On-chain identity | An identity officer verified the Ghana Card hash for this address | `IdentityRegistry.profileOf(address)`, mirrored in `landchain.chain_identity` |
| Officer role | This person works for the Lands Commission as registrar / identity officer / admin | `landchain.profile.roles` (source of truth), mirrored into Supabase `app_metadata.landchain_roles` so it is in the JWT |

Citizens need all of the first three to register land. Officers need a Supabase user and an officer role; they do **not** need their own wallet, because the backend signs with the role wallet (section 6.2).

### 5.2 Sign-in flows the UI should offer

1. **Email + password** or **email magic link**: `supabase.auth.signInWithPassword` / `signInWithOtp({ email })`.
2. **Phone OTP** (Ghana numbers, e.g. `+233 24 000 0000`): `signInWithOtp({ phone })` with an SMS provider configured in Supabase (Twilio, MessageBird or Vonage).
3. **Public visitor**: no sign-in. The UI calls public endpoints without a token.
4. **Demo accounts (local chain only)**: the management command `seed_demo_users` creates the 8 seeded people as Supabase users (`ama@demo.landchain.local` etc., password from `DEMO_PASSWORD`) already linked to their Ganache addresses. The login page lists them from `GET /dev/demo-accounts` and signs in with password. This keeps the "no wallet needed" demo.

After any sign-in, the UI calls `GET /me`. If `wallet_address` is null and the user is a citizen, it shows "Connect your wallet" and runs the SIWE flow (5.4).

Supabase also has native "Sign in with Web3" for Ethereum wallets. You can use it instead of the Django SIWE endpoints; then read the address from the user's `web3` identity and skip `/auth/wallet/*`. The Django flow below is recommended because it lets people sign in by email or phone first and link a wallet later, and lets officers have no wallet. Check the current Supabase docs for the claim layout before choosing it.

### 5.3 Verifying the Supabase JWT in Django

Supabase access tokens are JWTs. Newer projects sign them with asymmetric keys published at a JWKS endpoint; older projects use a shared HS256 secret. Support both.

| Claim | Example | Use |
| --- | --- | --- |
| `sub` | `"8d0f6c1e-5b3a-4f7e-9a51-2c1d0e7b9f33"` | Supabase user id → `Profile.supabase_user_id` |
| `aud` | `"authenticated"` | Must equal `SUPABASE_JWT_AUDIENCE` |
| `iss` | `"https://<ref>.supabase.co/auth/v1"` | Must equal `SUPABASE_URL + "/auth/v1"` |
| `exp`, `iat` | Unix seconds | Reject expired (60 s leeway) |
| `role` | `"authenticated"` | Reject `anon` and `service_role` tokens on user endpoints |
| `email`, `phone` | `"efua@example.com"` | Copied to the profile for relay notifications |
| `app_metadata.landchain_roles` | `["registrar"]` | Hint only. Django checks `Profile.roles`, which admins edit through the API. |
| `user_metadata` | `{"full_name": "Efua Mensah"}` | Initial name on first login. User-editable, so never trust it for permissions. |
| `aal` | `"aal1"` / `"aal2"` | Officer write endpoints may require `aal2` (MFA) when `REQUIRE_OFFICER_MFA=true` |
| `session_id` | uuid | Logged with officer actions |

```
# landchain/accounts/auth.py
import jwt, time
from jwt import PyJWKClient
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import Profile

_jwks = PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=600)

class SupabaseUser:
    """request.user for DRF. is_authenticated is True; .profile is the Profile row."""
    is_authenticated = True
    def __init__(self, profile, claims):
        self.profile, self.claims = profile, claims
        self.pk = profile.pk

class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    www_authenticate_realm = "api"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header.lower().startswith("bearer "):
            return None                      # anonymous: public endpoints still work
        token = header[7:].strip()
        try:
            alg = jwt.get_unverified_header(token).get("alg")
            if alg == "HS256":               # legacy projects
                key = settings.SUPABASE_JWT_SECRET
            else:                            # ES256 / RS256 signing keys
                key = _jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=[alg],
                audience=settings.SUPABASE_JWT_AUDIENCE,      # "authenticated"
                issuer=f"{settings.SUPABASE_URL}/auth/v1",
                leeway=60,
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed({"code": "TOKEN_EXPIRED", "message": "Your session expired. Sign in again."})
        except jwt.PyJWTError:
            raise exceptions.AuthenticationFailed({"code": "TOKEN_INVALID", "message": "Sign in again."})
        if claims.get("role") != "authenticated":
            raise exceptions.AuthenticationFailed({"code": "TOKEN_INVALID", "message": "Sign in again."})

        profile, created = Profile.objects.get_or_create(
            supabase_user_id=claims["sub"],
            defaults={"email": claims.get("email") or None, "phone": claims.get("phone") or None,
                      "full_name": (claims.get("user_metadata") or {}).get("full_name", "")},
        )
        if not created and (profile.email != claims.get("email") or profile.phone != claims.get("phone")):
            profile.email, profile.phone = claims.get("email") or None, claims.get("phone") or None
            profile.save(update_fields=["email", "phone", "updated_at"])
        return SupabaseUser(profile, claims), token

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
```

```
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["landchain.accounts.auth.SupabaseJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],   # each view sets its own
    "EXCEPTION_HANDLER": "landchain.core.errors.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "landchain.core.pagination.Pagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
```

Frontend side: one helper adds the token.

```
// src/lib/landchain/api.ts
const { data: { session } } = await supabase.auth.getSession();
const res = await fetch(`${API_URL}/api/v1${path}`, {
  ...init,
  headers: { "Content-Type": "application/json", ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}), ...init.headers },
});
```

### 5.4 Wallet linking (Sign-In with Ethereum, EIP-4361)

One wallet per person, one person per wallet ("wallet = identity", assumption 5). Linking proves control of the address. Once the profile has submitted an on-chain identity, the wallet can't be changed through the API (that is key recovery, future work).

1. `POST /auth/wallet/nonce` with the address. Django stores a random nonce (10 min TTL) and returns the exact EIP-4361 message to sign.
2. The UI calls MetaMask `personal_sign` with that message.
3. `POST /auth/wallet/verify` with the message and signature. Django checks the nonce, domain, chain id, expiry and recovers the signer with `eth_account.Account.recover_message(encode_defunct(text=message), signature=sig)`. If it matches, the address is linked and the nonce burned.

Rules: the address must not be linked to another profile (`409 WALLET_IN_USE`); it must not hold an officer role on chain (`LandAccessControl.isOfficer`), because officer addresses can't submit profiles (`409 WALLET_IS_OFFICER`); on Sepolia the UI must switch MetaMask to chain 11155111 first.

### 5.5 Roles and permissions

| Permission class | Who passes | Notes |
| --- | --- | --- |
| `Public` | Anyone, token optional | Response filtered by privacy rules |
| `IsSignedIn` | Valid Supabase token |  |
| `HasWallet` | Signed in and `wallet_address` linked | Needed for any citizen chain action |
| `IsVerifiedCitizen` | Has wallet, not an officer, on-chain identity status = verified | Register land, request a transfer |
| `IsOfficer` | `roles` contains `registrar` or `id_officer` | Sees all names, documents, fees; review queue |
| `IsIdentityOfficer` | `id_officer` in roles | Verify / reject identity |
| `IsRegistrar` | `registrar` in roles | Record fees, approve / reject registrations and transfers |
| `IsAdmin` | `admin` in roles | Manage officers, resync indexer, view signer balances |

`kind` for the UI is derived: `"officer"` if any officer role, otherwise `"citizen"`; anonymous callers are `"public"`. UI role labels map as: `registrar` → "Registrar", `id_officer` → "Identity officer", none → "Citizen".

| Action | Public | Citizen (no wallet) | Citizen (wallet, unverified) | Verified citizen | Identity officer | Registrar |
| --- | --- | --- | --- | --- | --- | --- |
| Read map, titles, history, activity | ✓ (filtered) | ✓ | ✓ | ✓ | ✓ (all names) | ✓ (all names) |
| Submit identity |  |  | ✓ |  |  |  |
| Register land |  |  |  | ✓ |  |  |
| Request / cancel transfer of own title |  |  |  | ✓ (owner) |  |  |
| Open documents |  | own parcels | own parcels | own parcels | ✓ | ✓ |
| See fees, receipt page |  | own parcels | own parcels | own parcels | ✓ | ✓ |
| Send enquiry | ✓ | ✓ | ✓ | ✓ (not own) |  |  |
| Verify / reject identity |  |  |  |  | ✓ |  |
| Record fees, approve / reject registration or transfer |  |  |  |  |  | ✓ |

"Own parcels" means the caller's public ID is the parcel's current owner, the applicant, or anywhere in its owner history (`canSeePrivate`).

### 5.6 Supabase project setup checklist

1. Auth → Providers: enable Email (confirm email on in production, off for local demo), Phone (SMS provider), optionally Web3.
2. Auth → URL configuration: Site URL = frontend URL; redirect URLs include `http://localhost:5173/**`.
3. Database → Extensions: enable `postgis` and `pgcrypto`.
4. Create schema: `create schema landchain;`. Point Django at it with `OPTIONS: {"options": "-c search_path=landchain,public"}`. Do **not** add `landchain` to API → Exposed schemas, so the anon key cannot read Django tables through PostgREST.
5. Connection: use the direct connection (port 5432) or session pooler for Django and Celery. If you use the transaction pooler (port 6543), set `DISABLE_SERVER_SIDE_CURSORS = True` and `CONN_MAX_AGE = 0`.
6. Storage: create private bucket `parcel-documents` (file size limit 20 MB, allowed MIME types `application/pdf, image/jpeg, image/png`) and `identity-evidence` if decision 18.2 adds card photos. No storage policies for `anon` or `authenticated`: only the service role (Django) touches them.
7. Keys: the browser gets `SUPABASE_URL` + the anon/publishable key. Django gets the service-role/secret key (Storage and Admin API) and the JWT secret if the project uses HS256. Never ship the service-role key to the browser.
8. Officer roles: after `POST /admin/officers` changes `Profile.roles`, Django calls the Admin API `auth.admin.update_user_by_id(uid, {"app_metadata": {"landchain_roles": [...]}})` so new tokens carry the hint. Existing tokens keep the old hint until refresh; Django checks the database anyway.

## 6. Blockchain integration

### 6.1 Contracts

Solidity 0.8.20, OpenZeppelin 5.0.2, deployed in this order by `migrations/1_deploy_land_system.js`, which then calls `titles.setFeeLedger(fees)` and grants `REGISTRAR_ROLE` (Ganache account 0) and `ID_OFFICER_ROLE` (account 1). ABIs: `landchain-contracts/shared/abi/*.json`; addresses: `shared/deployments.local.json` (keyed by chain id, with `startBlock`). Local addresses (deterministic Ganache):

| Contract | Local address (1337) | Writes | Reads the backend uses | Events |
| --- | --- | --- | --- | --- |
| `LandAccessControl` | `0xe78A0F7E598Cc8b0Bb87894B0F60dD2a88d6a8Ab` | `grantRole(role, account)`, `revokeRole` (admin only) | `rolesOf(addr) → (registrar, idOfficer)`, `isOfficer`, `hasRole`, `getRoleMember(role, i)`, `getRoleMemberCount`, `REGISTRAR_ROLE()`, `ID_OFFICER_ROLE()` | `RoleGranted`, `RoleRevoked`, `RoleAdminChanged` |
| `IdentityRegistry` | `0x5b1869D9A4C187F2EAa108f3062412ecf0526b24` | `submitProfile(bytes32 cardHash, bool citizen)` (citizen), `verifyProfile(address)`, `rejectProfile(address)` (ID officer) | `profileOf(addr) → (status, citizen, cardHash, updatedAt)`, `isVerified`, `isCitizen`, `members()`, `memberCount`, `cardOwner(bytes32)`, `publicIdOf` | `ProfileSubmitted(who, cardHash, citizen)`, `ProfileVerified(who, by)`, `ProfileRejected(who, by)` |
| `TitleRegistry` (ERC-721 "LandChain Ghana Title", `GLT`) | `0xCfEB869F69431e42cdB54A4F4f105C19C080A601` | `submitApplication(ApplicationInput)`, `requestTransfer(recordId, to)`, `cancelTransfer(transferId)` (citizen); `approveApplication(appId)`, `rejectApplication(appId, reason)`, `approveTransfer(transferId)`, `rejectTransfer(transferId, reason)` (registrar); `setFeeLedger` (admin, once) | `parcelCount`, `getParcel(recordId)`, `getBoundary`, `getDocs`, `ownerHistory`, `recordOfParcelId(string)`, `applicationCount`, `getApplication`, `transferCount`, `getTransfer`, `openTransferOf(recordId)`, `recordOfToken`, `titleCount`, ERC-721 views | `ApplicationSubmitted(appId, recordId, parcelId, applicant, pillars)`, `ApplicationApproved(appId, recordId, by)`, `ApplicationRejected(appId, recordId, by, reason)`, `TitleMinted(recordId, tokenId, owner)`, `TransferRequested(transferId, recordId, from, to)`, `TransferApproved(transferId, recordId, from, to, by)`, `TransferRejected(transferId, recordId, by, reason)`, `TransferCancelled(transferId, recordId)`, ERC-721 `Transfer` |
| `FeeLedger` | `0x254dffcd3277C0b1660F6d42EFbB754edaBAbC2B` | `recordPayment(recordId, kind, amountPesewas, receiptHash) → paymentId` (registrar) | `paymentCount`, `getPayment(id)`, `paymentsOf(recordId)`, `isPaid(recordId, kind)`, `transferFeePaid(transferId)`, `receiptUsed(bytes32)` | `PaymentRecorded(paymentId, recordId, kind, amountPesewas, receiptHash, by)` |

Key contract behaviour the API must reflect:

- `transferFrom` / `safeTransferFrom` always revert ("Titles move only through a registrar-approved transfer"). Never expose them.
- Pending ≠ minted: an application creates a record with `tokenId = 0`; the NFT is minted on `approveApplication`.
- Approval of a registration needs `FeeLedger.isPaid(recordId, StampDuty)` and `isPaid(recordId, FirstRegistration)`. Official search is recorded but not required.
- Approval of a transfer needs `transferFeePaid(transferId)`; the transfer fee can only be recorded while a transfer is open (`openTransferOf(recordId) ≠ 0`) and is bound to that transfer.
- A receipt hash can never be reused (`receiptUsed`), and non-transfer fee kinds can be recorded only once per record.
- Rejecting an application frees its parcel ID and boundary for a corrected application (new record id).
- `Payment.payer` is the parcel's owner when the fee was recorded.
- `TitleRegistry` is 20.6 KB of the 24 KB limit: any new on-chain feature belongs in a new contract.

### 6.2 Who signs what

| Mode | Used for | How |
| --- | --- | --- |
| `backend:registrar` | `recordPayment`, `approveApplication`, `rejectApplication`, `approveTransfer`, `rejectTransfer` | Django signs with `REGISTRAR_SIGNER_KEY` (env var locally, KMS / Vault in production). The officer's Supabase user is recorded in `OfficerAction`. |
| `backend:id_officer` | `verifyProfile`, `rejectProfile` | `ID_OFFICER_SIGNER_KEY` |
| `backend:admin` | `grantRole`, `revokeRole` | `ADMIN_SIGNER_KEY` (holds `DEFAULT_ADMIN_ROLE`; locally Ganache account 0) |
| `wallet` | `submitProfile`, `submitApplication`, `requestTransfer`, `cancelTransfer` | Contracts check `msg.sender` (owner / applicant / profile), so the citizen's own wallet must send. The API prepares the unsigned transaction; MetaMask sends it with `eth_sendTransaction`; the UI reports the hash back (6.3). |
| `dev_unlocked` | Same citizen calls, local demo only | When `CHAIN_ID=1337` and `CHAIN_ALLOW_UNLOCKED_SIGNING=true`, and the profile's address is one of Ganache's `eth_accounts`, the API can send it directly (`POST /chain/intents/{id}/dev-sign`). Refused on any other chain. |

**Attribution.** On chain, `decidedBy` / `recordedBy` / `by` will be the shared role wallet, not the individual officer. The backend's `OfficerAction` table is the record of which person pressed the button. Show "Lands Commission registrar" from the chain and the officer's name from `OfficerAction` to officers only.

**Nonces and ordering.** One Celery queue per signer (`signer.registrar`, `signer.id_officer`, `signer.admin`) with concurrency 1. The worker reads `eth_getTransactionCount(addr, "pending")` under a Postgres advisory lock keyed by the signer address, signs, sends, stores the hash. On "nonce too low" it re-reads and retries once. On Sepolia, use EIP-1559 fees (`maxFeePerGas = 2 × baseFee + priorityFee`) and rebroadcast with +12.5% after 3 minutes unmined.

**Gas.** Every call: `eth_call` first (gets the revert reason, spends nothing), then `estimate_gas × 1.2` (the frontend uses the same 20% margin so mint/transfer never runs out). Signer balances are checked by `GET /admin/signers`; alert below 0.05 ETH on Sepolia.

### 6.3 Transaction intents (the write lifecycle)

Every chain write, whoever signs, is a `TxIntent` row. The UI polls `GET /chain/intents/{id}` (or passes `?wait=true` to officer endpoints) and refreshes its data when the status is `confirmed`.

```
             prepare (citizen)                         officer endpoint
                   │                                         │
                   ▼                                         ▼
        awaiting_signature ──(UI posts hash)──► submitted ◄── queued ──(signer sends)
                   │                               │
             expires (15 min)               receipt status 1 ──► mined ──(N confirmations + indexed)──► confirmed
                   ▼                               │
                expired                     receipt status 0 ──► reverted (revert_reason)
                                            dropped / replaced ─► failed
   simulation refused at prepare/queue time ──► 422 response + Tx row with status "Reverted" (no intent kept)
```

| Status | Meaning |
| --- | --- |
| `awaiting_signature` | Citizen tx prepared, waiting for MetaMask. `tx` field holds the unsigned transaction. |
| `queued` | Officer tx accepted, waiting for its signer worker. |
| `submitted` | Hash known, not yet mined. |
| `mined` | Receipt with status 1 in block N. |
| `confirmed` | Block N has `CHAIN_CONFIRMATIONS` confirmations (0 on Ganache, 2 on Sepolia) **and** the indexer has processed block N, so reads already show the change. |
| `reverted` | Mined with status 0 (rare, since we simulate first: state changed between simulate and mine). |
| `failed` | Dropped, replaced, or the RPC refused the raw transaction. `error` explains. |
| `expired` | Prepared but never signed within 15 minutes. |

When an intent is reported as submitted, the backend checks the transaction it finds on chain: `to`, `input` and `from` must equal what it prepared (`422 TX_MISMATCH` otherwise). That stops someone linking an unrelated hash to an intent.

### 6.4 Encoding rules (must match the frontend and contracts exactly)

| Value | Rule | Python |
| --- | --- | --- |
| Public ID | `"GH-"` + first 4 bytes (8 hex chars) of keccak256 of the 20 address bytes | `"GH-" + Web3.keccak(hexstr=addr).hex().removeprefix("0x")[:8]` |
| Ghana Card hash | keccak256 of UTF-8 `"landchain-card:" + card.strip().upper()` with all whitespace removed. Card format `^GHA-\d{9}-\d$`. | `Web3.keccak(text="landchain-card:" + re.sub(r"\s+", "", card.strip().upper())).hex()` |
| Receipt hash | keccak256 of UTF-8 `receipt_no.strip().upper()` | `Web3.keccak(text=receipt_no.strip().upper())` |
| Document fingerprint | SHA-256 of the file bytes, as `bytes32` hex `0x…` (64 hex chars) | `"0x" + hashlib.sha256(data).hexdigest()` |
| Coordinates | int32 micro-degrees, `round(deg × 1e6)`; Ghana box lat 4,500,000…11,200,000, lng −3,300,000…1,300,000; 3 to 32 pillars; `lats` and `lngs` same length | `round(lat * 1_000_000)` |
| Area | `acresX100 = max(1, round(area_acres × 100))`, uint32, > 0. Frontend formula: shoelace area on a local projection around Berekuso (5.7505, −0.2275), 110,540 m/° lat, 111,320·cos(lat) m/° lng, 4046.8564 m²/acre. Use the same formula so the area shown before submit equals the stored one (or switch both sides to pyproj geodesic area). | see `geo.areaAcres` |
| Amount | uint64 pesewas, `round(ghs × 100)`, > 0 | `int((Decimal(ghs) * 100).quantize(Decimal(1)))` |
| Parcel ID | 11 chars `AA-AAA-0000` (two capitals, dash, three capitals, dash, four digits) | `re.fullmatch(r"[A-Z]{2}-[A-Z]{3}-\d{4}", pid)` |
| GhanaPostGPS | Optional; UI format `^[A-Z]{2}-\d{3,4}-\d{4}$`, uppercased (not checked on chain) |  |
| Timestamps | uint64 seconds on chain → ISO in API |  |

Enum indices (on chain ↔ API string):

| Enum | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| `IdentityRegistry.Status` → `identity` | `none` | `pending` | `verified` | `rejected` |
| `TitleRegistry.Interest` → `interest` | `Allodial` | `Customary freehold` | `Common-law freehold` | `Leasehold` |
| `TitleRegistry.Status` → `status` | `pending` | `registered` | `transfer_pending` | `rejected` |
| `TitleRegistry.Decision` → `decision` | `waiting` | `approved` | `rejected` | `cancelled` |
| `FeeLedger.Kind` → `kind` | `Official search` | `Stamp duty` | `First registration` | `Transfer` |

Document types used by the UI (free-text `docType` on chain): `Site plan`\*, `Indenture`\*, `Search report`\*, `Consent / concurrence` (\* required by the UI; the contract does not require any).

### 6.5 Event indexer

Replaces `chain/snapshot.ts`. A Celery beat task (every 2 s locally, 6 s on Sepolia) or a long-running management command `run_indexer`:

1. Read `IndexerCursor(chain_id)`. First run starts at the deployment's `startBlock`.
2. `to_block = head − CHAIN_CONFIRMATIONS`; process in batches of 2,000 blocks with `eth_getLogs` filtered by the four contract addresses.
3. For each log in (block, logIndex) order: decode with the ABI, insert into `ChainEvent` (unique on `tx_hash, log_index`, so replays are safe), fetch the block timestamp once per block (cache), fetch the tx receipt once per tx for `gas_used`, `effective_gas_price`, `from` → `ChainTx`.
4. Apply the event to the projection tables, and refresh the touched rows from view functions (`getParcel`, `getBoundary`, `getDocs`, `ownerHistory`, `getApplication`, `getTransfer`, `getPayment`, `profileOf`, `rolesOf`) so the projection always equals the contract state.
5. Write history rows, activity rows and notifications (section 12); link staged documents to the new record (job 13.4); mark matching intents `confirmed`.
6. Save the cursor in the same database transaction.

**Reorgs:** keep each block's hash. If the stored hash of the cursor block differs from the chain's, roll back events newer than the last matching block (delete `ChainEvent` rows, rebuild affected projections from view functions) and continue. Ganache never reorgs; Sepolia rarely does beyond 2 blocks. **Fresh chain:** if `eth_chainId` or the `TitleRegistry` address differs from the cursor's, or the cursor block is above head (Ganache restarted with `chain:fresh`), wipe the projection for that chain and re-index from `startBlock`. `POST /admin/indexer/resync` forces this.

**Mapping, mirroring snapshot.ts:**

| Event | Projection update | Activity row (`fn(args)`) | History row |
| --- | --- | --- | --- |
| `ProfileSubmitted` | upsert `ChainIdentity(address)` status pending | `submitProfile(0x1234abcd…, citizen)` from `who` |  |
| `ProfileVerified` / `Rejected` | status verified / rejected | `verifyProfile(GH-…)` / `rejectProfile(GH-…)` from `by` |  |
| `ApplicationSubmitted` | create `Parcel(record_id)` + boundary + docs, `Application(app_id)` | `submitApplication("GA-BRK-0015", 4 pillars)` | Application: "Applied by GH-…" |
| `ApplicationApproved` | application approved, decided\_by/at | `approveApplication(APP-15)` |  |
| `TitleMinted` | parcel registered, token id, registered\_at, owner history [owner] |  | Registration: "Title GLT #15 minted to GH-…" |
| `ApplicationRejected` | application rejected + reason; parcel rejected | `rejectApplication(APP-15, "reason")` | Rejected: "Rejected by the registrar: reason" |
| `TransferRequested` | create `TransferRequest`, parcel transfer\_pending | `requestTransfer("GA-BRK-0006", GH-…)` | Transfer requested: "GH-a asked to transfer to GH-b" |
| `TransferApproved` | transfer approved; parcel owner = to, owners append, status registered | `approveTransfer(TRF-3)` | Transfer: "GH-a → GH-b, approved by the registrar" |
| `TransferRejected` | transfer rejected + reason; parcel registered | `rejectTransfer(TRF-3, "reason")` | Transfer rejected: "Rejected by the registrar: reason" |
| `TransferCancelled` | transfer cancelled; parcel registered | `cancelTransfer(TRF-3)` from the transfer's `from` | Transfer cancelled: "Cancelled by the owner" |
| `PaymentRecorded` | create `Payment(payment_id)` from `getPayment` | `recordPayment("GA-BRK-0002", Stamp duty)` |  |
| `RoleGranted` / `RoleRevoked` | update `ChainRole` | `grantRole(REGISTRAR_ROLE, 0x…)` |  |

History and payments are shown only for the **current** record of each parcel ID (the frontend's `isCurrent`); older rejected records stay in the database and are reachable with `?record_id=`.

## 7. Data model (Django models, schema `landchain`)

Two kinds of table. **Off-chain** tables are owned by Django and hold everything that must never go on chain. **Projection** tables are written only by the indexer and can be rebuilt from the chain at any time; API views never write to them.

### 7.1 Off-chain (source of truth is Django)

```
Profile
  id                 uuid pk
  supabase_user_id   uuid unique            # JWT sub
  email              citext null
  phone              varchar(20) null       # E.164
  full_name          varchar(120)           # never on chain; replaces localStorage "landchain-names"
  wallet_address     char(42) unique null   # lowercase
  public_id          char(11) unique null   # GH-xxxxxxxx, derived from wallet_address
  wallet_linked_at   timestamptz null
  roles              text[] default {}      # subset of {registrar, id_officer, admin}
  notify_email       bool default true
  notify_sms         bool default false
  is_demo            bool default false
  created_at, updated_at

WalletNonce
  nonce              varchar(32) pk
  address            char(42)
  profile            fk Profile
  message            text                    # exact EIP-4361 text issued
  expires_at         timestamptz
  used_at            timestamptz null

Document                                     # replaces vault.ts (IndexedDB)
  id                 "doc_" ULID pk
  sha256             char(66) index          # 0x + 64 hex, equals on-chain Doc.hash
  doc_type           varchar(40)             # Site plan | Indenture | Search report | Consent / concurrence
  original_name      varchar(255)            # private: may contain a person's name
  mime               varchar(80)
  size_bytes         int
  storage_path       varchar(300)            # parcel-documents/<sha256>
  uploaded_by        fk Profile
  status             enum(staged, attached, orphaned)
  parcel_record_id   int null                # set when the indexer sees the fingerprint on a record
  created_at, attached_at
  unique (sha256, uploaded_by)

Enquiry                                      # replaces enquiries.ts (localStorage)
  id                 "enq_" ULID pk
  parcel_id          varchar(11)
  record_id          int
  to_public_id       char(11)                # owner at the time
  to_profile         fk Profile null         # resolved owner profile (never returned to the sender)
  from_profile       fk Profile null         # null for anonymous visitors
  from_public_id     varchar(11) default "public"
  name               varchar(120)
  contact            varchar(160)            # phone or email of the enquirer
  message            text (max 2000)
  status             enum(new, read, answered)
  relayed_at         timestamptz null        # email/SMS sent to owner
  ip_hash            char(64)                # sha256(ip + salt) for rate limiting / abuse
  created_at, read_at, answered_at

PaymentReceipt                               # private side of a FeeLedger payment
  payment_id         int pk                  # FeeLedger payment id (after indexing)
  intent             fk TxIntent unique
  receipt_no         varchar(64)             # plain receipt number, officers only
  consideration_ghs  numeric(14,2) null      # price paid, for stamp duty
  note               text null

TxIntent
  id                 "txi_" ULID pk
  chain_id           int
  action             varchar(40)             # submitProfile, submitApplication, ...
  contract           varchar(30)
  function           varchar(40)
  args_json          jsonb                   # decoded args
  args_label         varchar(200)            # human label, same as UI's Tx.args
  signer_mode        enum(wallet, backend_registrar, backend_id_officer, backend_admin, dev_unlocked)
  from_address       char(42)
  to_address         char(42)
  data               text                    # calldata
  gas_limit          bigint
  status             enum(awaiting_signature, queued, submitted, mined, confirmed, reverted, failed, expired)
  tx_hash            char(66) unique null
  block_number       bigint null
  revert_reason      text null
  error              text null
  result_json        jsonb null              # {app_id, record_id, transfer_id, payment_id}
  idempotency_key    uuid null
  created_by         fk Profile
  created_at, updated_at, expires_at
  unique (created_by, idempotency_key)

OfficerAction                                # who pressed the button (role wallets are shared)
  id, intent fk TxIntent, officer fk Profile, role varchar(20), action varchar(40),
  target varchar(40)                         # APP-15, TRF-3, GH-…, GA-BRK-0002
  reason text null, session_id uuid null, ip inet null, created_at

Notification
  id                 "ntf_" ULID pk
  recipient_public_id varchar(11) null       # for a citizen
  recipient_role     varchar(20) null        # "registrar" | "id_officer" (UI's "role:Registrar")
  recipient_profile  fk Profile null
  kind               varchar(40)             # see section 12
  text               varchar(300)
  parcel_id          varchar(11) null
  link               varchar(120) null       # "/title/GA-BRK-0006", "/review"
  source_event       fk ChainEvent null
  at                 timestamptz
  NotificationRead(notification, profile, read_at)  # role notifications are read per officer

RevertLog                                    # simulation refusals, shown in the activity log
  id, chain_id, contract, function, args_label, from_address, from_public_id,
  error text, intent fk null, created_at
```

### 7.2 Projection (written by the indexer only)

```
IndexerCursor(chain_id pk, title_registry_address, last_block, last_block_hash, updated_at)
ChainBlock(chain_id, number, hash, timestamp)                         pk (chain_id, number)
ChainEvent(chain_id, tx_hash, log_index, block_number, contract, event, args jsonb)  unique (chain_id, tx_hash, log_index)
ChainTx(chain_id, tx_hash pk, from_address, to_address, contract, function, args_label,
        block_number, at, status "Success", gas_used, effective_gas_price_wei, cost_wei)

ChainIdentity(address pk, public_id, status, citizen bool, card_hash, updated_at)
ChainRole(address, role)                                              # registrar | id_officer | admin

Parcel
  record_id          int pk                  # TitleRegistry record id
  parcel_id          varchar(11) index       # not unique (rejected ids are reused)
  is_current         bool index              # latest record for this parcel_id
  interest           smallint
  holder, region, location, plan_number, gps_address  varchar
  acres_x100         int
  status             smallint
  owner_address      char(42); owner_public_id char(11)
  token_id           int null
  registered_at      timestamptz null; updated_at timestamptz
  boundary           geometry(Polygon, 4326)   # PostGIS, GIST index
  lats_micro int[]; lngs_micro int[]
  created_block, updated_block bigint

ParcelDoc(record_id, position, doc_type, sha256)
OwnerHistory(record_id, position, address, public_id)                 # oldest first
Application(app_id pk, record_id, applicant_address, applicant_public_id, created_at,
            decision, decided_by, decided_at, reason)
TransferRequest(transfer_id pk, record_id, from_address, from_public_id, to_address, to_public_id,
                requested_at, decision, decided_by, decided_at, reason)
Payment(payment_id pk, record_id, kind, amount_pesewas, receipt_hash, payer_address, payer_public_id,
        recorded_by, at, transfer_id null, block_number, tx_hash)
HistoryEvent(id, record_id, parcel_id, type, text, at, block_number, tx_hash)
```

Overlap check in SQL (touching edges are allowed, as in the frontend's strict segment test):

```
SELECT parcel_id FROM landchain.parcel
WHERE is_current AND status <> 3                                 -- not rejected
  AND ST_Intersects(boundary, ST_GeomFromGeoJSON(%s))
  AND NOT ST_Touches(boundary, ST_GeomFromGeoJSON(%s))
LIMIT 1;
```

## 8. Shared JSON objects

Field marked **private** are present only when the caller passes the privacy check for that parcel or person (section 11); otherwise they are omitted or `null`, as noted.

#### PersonRef

How the API refers to any person. Replaces `shownName` in the UI.

```
{
  "public_id": "GH-7d4e894d",
  "name": "Ama Owusu",          // private: null unless the caller is an officer or this person; officers' role name always shown
  "kind": "citizen",            // "citizen" | "officer"
  "label": "Ama Owusu"          // what to display: name if visible, else public_id; officers: "Lands Commission registrar"
}
```

#### Me

```
{
  "user_id": "8d0f6c1e-5b3a-4f7e-9a51-2c1d0e7b9f33",
  "email": "efua@example.com",
  "phone": null,
  "full_name": "Efua Mensah",
  "wallet_address": "0x28a8746e75304c0780e011bed21c72cd78cd535e",
  "public_id": "GH-3c1f9a02",
  "kind": "citizen",                         // "citizen" | "officer"
  "roles": ["Citizen"],                      // UI labels: "Citizen" | "Registrar" | "Identity officer"; plus "Admin"
  "identity": {
    "status": "none",                        // none | pending | verified | rejected   (from chain)
    "citizenship": null,                     // "citizen" | "non-citizen" | null
    "card_hash": null,
    "updated_at": null,
    "pending_intent": null                   // TxIntent id if a submitProfile is in flight
  },
  "capabilities": {
    "can_link_wallet": false,
    "can_submit_identity": true,
    "can_register_land": false,
    "can_request_transfer": false,
    "can_review_identities": false,
    "can_review_registrations": false,
    "can_record_fees": false,
    "is_admin": false
  },
  "counts": { "unread_notifications": 2, "new_enquiries": 0, "parcels_owned": 0, "queue_items": 0 },
  "notify": { "email": true, "sms": false }
}
```

#### Parcel (detail)

```
{
  "parcel_id": "GA-BRK-0002",
  "record_id": 2,
  "title_no": 2,                              // GLT token id; null while pending / rejected
  "status": "registered",                     // pending | registered | transfer_pending | rejected
  "status_label": "Registered",
  "interest": "Customary freehold",
  "holder": "Berekuso Stool",
  "region": "Eastern",
  "location": "Berekuso, Eastern Region",
  "plan_number": "SER B4102/25",
  "gps_address": "EA-1805-5795",
  "acres": "1.24",
  "acres_x100": 124,
  "owner": { "public_id": "GH-7d4e894d", "name": null, "kind": "citizen", "label": "GH-7d4e894d" },
  "owners": [ { "public_id": "GH-7d4e894d", "name": null, "kind": "citizen", "label": "GH-7d4e894d" } ],
  "boundary": {
    "pillars": [[5.750912, -0.228113], [5.751204, -0.227401], [5.750633, -0.227088], [5.750341, -0.227802]],
    "lats_micro": [5750912, 5751204, 5750633, 5750341],
    "lngs_micro": [-228113, -227401, -227088, -227802],
    "centroid": [5.750773, -0.227601],
    "pillar_count": 4
  },
  "registered_at": "2026-11-19T13:47:31Z",
  "updated_at": "2026-11-19T13:47:31Z",
  "documents": [
    { "doc_type": "Site plan", "sha256": "0x9f2c…e41a", "file_available": true,  "can_open": false },
    { "doc_type": "Indenture", "sha256": "0x51b0…07cd", "file_available": false, "can_open": false },
    { "doc_type": "Search report", "sha256": "0xa33e…9b10", "file_available": false, "can_open": false }
  ],
  "application": {                            // latest application for this record
    "id": "APP-2", "decision": "approved",
    "applicant": { "public_id": "GH-7d4e894d", "name": null, "kind": "citizen", "label": "GH-7d4e894d" },
    "created_at": "2026-11-19T13:47:20Z",
    "decided_by": { "public_id": "GH-1a2b3c4d", "name": "Lands Commission", "kind": "officer", "label": "Lands Commission registrar" },
    "decided_at": "2026-11-19T13:47:31Z",
    "reason": null
  },
  "open_transfer": null,                      // TransferRequest object when status = transfer_pending
  "fees": {                                    // private: null for public
    "total_ghs": "3076.00", "count": 3,
    "stamp_duty_recorded": true, "first_registration_recorded": true, "official_search_recorded": true
  },
  "visibility": "public",                      // "public" | "private" (caller can see private details)
  "viewer": { "is_owner": false, "was_owner": false, "can_transfer": false, "can_cancel_transfer": false, "can_enquire": true },
  "chain": {
    "chain_id": 1337,
    "contract": "TitleRegistry",
    "address": "0xcfeb869f69431e42cdb54a4f4f105c19c080a601",
    "record_id": 2, "token_id": 2,
    "explorer_url": null                       // https://sepolia.etherscan.io/token/<addr>?a=2 on Sepolia
  }
}
```

**Parcel (list item)** is the same minus `documents`, `application`, `fees`, `boundary.lats_micro/lngs_micro`, plus `"owners_count": 1`.

#### Application

```
{ "id": "APP-15", "app_id": 15, "parcel_id": "GA-BRK-0015", "record_id": 15,
  "applicant": PersonRef, "created_at": "…", "decision": "waiting",
  "decided_by": PersonRef | null, "decided_at": null, "reason": null,
  "fees_ready": false,                          // stamp duty + first registration both recorded
  "missing_fees": ["Stamp duty", "First registration"] }
```

#### TransferRequest

```
{ "id": "TRF-3", "transfer_id": 3, "parcel_id": "GA-BRK-0006", "record_id": 6,
  "from": PersonRef, "to": PersonRef, "to_identity": "verified",
  "requested_at": "…", "decision": "waiting",
  "decided_by": null, "decided_at": null, "reason": null,
  "transfer_fee_recorded": false }
```

#### Payment

```
{ "id": "PAY-5", "payment_id": 5, "parcel_id": "GA-BRK-0002", "record_id": 2,
  "kind": "Stamp duty", "kind_index": 1, "paid_to": "Ghana Revenue Authority",
  "amount_ghs": "744.00", "amount_pesewas": 74400,
  "receipt_hash": "0x6b1d…a0f3",
  "receipt_no": "GRA-SD-2026-004411",         // officers only; never on chain
  "payer": PersonRef, "recorded_by": PersonRef,
  "transfer_id": null,                          // "TRF-3" for Transfer fees
  "at": "…", "block": 24, "tx_hash": "0x…" }
```

#### HistoryEvent

```
{ "parcel_id": "GA-BRK-0001",
  "type": "Transfer",   // Application | Registration | Transfer requested | Transfer | Transfer rejected | Transfer cancelled | Rejected
  "text": "GH-1f0e… → GH-9c2a…, approved by the registrar",
  "at": "…", "block": 41, "tx_hash": "0x…" }
```

#### ActivityTx

```
{ "tx_hash": "0x…",                    // null for simulation refusals
  "contract": "TitleRegistry", "function": "requestTransfer",
  "args_label": "\"GA-BRK-0002\", GH-9c2a41d0",
  "call": "TitleRegistry.requestTransfer(\"GA-BRK-0002\", GH-9c2a41d0)",
  "from": PersonRef, "block": 57, "at": "…",
  "status": "Success",                   // "Success" | "Reverted"
  "error": null,                         // revert reason when Reverted
  "gas_used": 98211, "cost_eth": "0.000196" }
```

#### TxIntent

```
{ "id": "txi_01JD3K8W5Q9Y2M7T4R6V1B0C3N",
  "action": "submitApplication",
  "contract": "TitleRegistry", "function": "submitApplication",
  "args_label": "\"GA-BRK-0015\", 4 pillars",
  "signer": "wallet",                     // wallet | backend:registrar | backend:id_officer | backend:admin | dev_unlocked
  "status": "awaiting_signature",
  "from": "0x28a8746e75304c0780e011bed21c72cd78cd535e",
  "tx": {                                 // present while awaiting_signature (wallet mode)
    "from": "0x28a8746e75304c0780e011bed21c72cd78cd535e",
    "to": "0xcfeb869f69431e42cdb54a4f4f105c19c080a601",
    "data": "0x6c7c…",
    "value": "0x0",
    "gas": "0x9c7a8",
    "chainId": "0x539"
  },
  "tx_hash": null, "block": null,
  "revert_reason": null, "error": null,
  "result": null,                         // after confirmed: {"application_id":"APP-15","record_id":15,"parcel_id":"GA-BRK-0015"}
  "success_message": "Application submitted",
  "created_at": "…", "updated_at": "…", "expires_at": "…" }
```

#### Notification

```
{ "id": "ntf_01JD…", "kind": "transfer_requested_to_you",
  "text": "GH-1f0e2b7a asked to transfer GA-BRK-0006 to you",
  "parcel_id": "GA-BRK-0006", "link": "/title/GA-BRK-0006",
  "audience": "me",                       // "me" | "role:Registrar" | "role:Identity officer"
  "at": "…", "read": false }
```

#### Enquiry (owner's view)

```
{ "id": "enq_01JD…", "parcel_id": "GA-BRK-0003",
  "from_public_id": "public", "name": "Kojo Appiah", "contact": "024 000 0000",
  "message": "I'm interested in buying this plot. Is it available?",
  "status": "new", "at": "…" }
```

## 9. Endpoints

Each card lists auth, the request, the response and the errors specific to it. All endpoints can also return `401 TOKEN_EXPIRED / TOKEN_INVALID`, `429 RATE_LIMITED`, `503 CHAIN_UNAVAILABLE` and `500 INTERNAL`. Chips: auth level contract call it causes.

### 9.1 System and config

#### `GET /health` · Public

Liveness for the load balancer. Checks database and Redis, not the chain.

##### Response 200

```
{ "ok": true, "version": "1.0.0", "db": "ok", "redis": "ok" }
```

#### `GET /config` · Public

Everything the frontend currently reads from `chain/config.ts` and `generated/deployments.json`. The UI no longer needs ABIs.

##### Response 200

```
{
  "chain_id": 1337,
  "chain_name": "Local Ganache",            // 11155111 → "Sepolia testnet"
  "is_local": true,
  "rpc_url_public": "http://127.0.0.1:7545", // for MetaMask wallet_addEthereumChain
  "explorer": null,                          // "https://sepolia.etherscan.io"
  "contracts": {
    "LandAccessControl": "0xe78a0f7e598cc8b0bb87894b0f60dd2a88d6a8ab",
    "IdentityRegistry":  "0x5b1869d9a4c187f2eaa108f3062412ecf0526b24",
    "TitleRegistry":     "0xcfeb869f69431e42cdb54a4f4f105c19c080a601",
    "FeeLedger":         "0x254dffcd3277c0b1660f6d42efbb754edabac2b"
  },
  "deployment": { "network": "development", "start_block": 0, "deployed_at": "2026-11-19T13:47:10.274Z" },
  "features": { "dev_unlocked_signing": true, "demo_accounts": true, "sms_relay": false },
  "doc_types": [
    { "type": "Site plan", "required": true, "note": "Prepared by a licensed surveyor, approved by Survey & Mapping" },
    { "type": "Indenture", "required": true, "note": "Proof of ownership: indenture, family declaration or deed of gift" },
    { "type": "Search report", "required": true, "note": "Official search from the Lands Commission" },
    { "type": "Consent / concurrence", "required": false, "note": "Only for stool or family land" }
  ],
  "interests": ["Allodial", "Customary freehold", "Common-law freehold", "Leasehold"],
  "limits": { "min_pillars": 3, "max_pillars": 32, "max_upload_mb": 20,
              "ghana_box": { "min_lat": 4.5, "max_lat": 11.2, "min_lng": -3.3, "max_lng": 1.3 } }
}
```

#### `GET /chain/status` · Public

Replaces `ChainStatus` in `store.ts` (the banner "Can't reach … Is the chain running?").

##### Response 200

```
{ "kind": "ok",                       // "ok" | "error"
  "chain_id": 1337, "name": "Local Ganache",
  "head_block": 212, "indexed_block": 212, "lag_blocks": 0,
  "contracts_match": true,            // code exists at every configured address
  "error": null }                     // e.g. "This chain doesn't have the current LandChain contracts. Run npm run setup:all in landchain-contracts."
```

#### `GET /dev/demo-accounts` · Public · local chain only

Lists the seeded Supabase demo users so the login page can offer one-click sign-in. Returns `404` unless `CHAIN_ID=1337` and `DEMO_MODE=true`.

##### Response 200

```
{ "password_hint": "set by DEMO_PASSWORD",
  "accounts": [
    { "name": "Lands Commission", "email": "registrar@demo.landchain.local", "kind": "officer", "roles": ["Registrar", "Admin"], "public_id": "GH-…", "address": "0x90f8bf6a479f320ead074411a4b0e7944ea8c9c1" },
    { "name": "Abena Sarpong", "email": "abena@demo.landchain.local", "kind": "officer", "roles": ["Identity officer"], "public_id": "GH-…", "address": "0xffcf8fdee72ac11b5c542428b35eef5769c409f0" },
    { "name": "Ama Owusu", "email": "ama@demo.landchain.local", "kind": "citizen", "roles": ["Citizen"], "identity": "verified", "public_id": "GH-…", "address": "0x22d491bde2303f2f43325b2108d26f1eaba1e32b" },
    { "name": "Yaw Boakye",    "email": "yaw@demo.landchain.local",    "address": "0xe11ba2b4d45eaed5996cd0823791e0c93114882d", "identity": "verified" },
    { "name": "Kofi Mensah",   "email": "kofi@demo.landchain.local",   "address": "0xd03ea8624c8c5987235048901fb614fdca89b117", "identity": "verified" },
    { "name": "Akosua Darko",  "email": "akosua@demo.landchain.local", "address": "0x95ced938f7991cd0dfcb48f0a06a40fa1af46ebc", "identity": "verified", "citizenship": "non-citizen" },
    { "name": "Kwabena Ofori", "email": "kwabena@demo.landchain.local","address": "0x3e5e9111ae8eb78fe1cc3bb8915d5d461f3ef9a9", "identity": "pending" },
    { "name": "Efua Mensah",   "email": "efua@demo.landchain.local",   "address": "0x28a8746e75304c0780e011bed21c72cd78cd535e", "identity": "none" }
  ] }
```

### 9.2 Me, wallet, notifications

#### `GET /me` · IsSignedIn

The signed-in person. Replaces `useMe()`. Creates the profile on first call.

##### Response 200

A [Me](#obj-me) object.

#### `PATCH /me` · IsSignedIn

Edit off-chain profile details. Replaces `setMyName`.

##### Request

```
{ "full_name": "Efua Mensah", "phone": "+233240000000", "notify": { "email": true, "sms": true } }
```

##### Response 200

Updated [Me](#obj-me).

##### Errors

`400 VALIDATION` (name 2–120 chars; phone E.164 `^\+233\d{9}$` or other country codes).

#### `POST /auth/wallet/nonce` · IsSignedIn

##### Request

```
{ "address": "0x28a8746E75304c0780E011BEd21C72cD78cd535E" }
```

##### Response 200

```
{ "nonce": "f3K9qzL2xY8wPm1R",
  "expires_at": "2026-11-20T10:10:00Z",
  "message": "landchain.example wants you to sign in with your Ethereum account:\n0x28a8746E75304c0780E011BEd21C72cD78cd535E\n\nLink this wallet to your LandChain account. This does not send a transaction or cost anything.\n\nURI: https://landchain.example\nVersion: 1\nChain ID: 1337\nNonce: f3K9qzL2xY8wPm1R\nIssued At: 2026-11-20T10:00:00Z\nExpiration Time: 2026-11-20T10:10:00Z" }
```

##### Errors

`400 VALIDATION` bad address · `409 WALLET_ALREADY_LINKED` profile already has a wallet · `409 WALLET_IN_USE` address linked to another profile.

#### `POST /auth/wallet/verify` · IsSignedIn

Checks the `personal_sign` signature and links the address.

##### Request

```
{ "message": "<exact message from /nonce>", "signature": "0x5f1c…1b" }
```

##### Response 200

Updated [Me](#obj-me) (with `wallet_address`, `public_id`, on-chain `identity` read immediately from `profileOf`).

##### Errors

`400 NONCE_INVALID` unknown, used or expired · `400 SIGNATURE_INVALID` recovered address differs · `409 WALLET_IN_USE` · `409 WALLET_IS_OFFICER` the address holds a Lands Commission role on chain.

#### `GET /me/parcels` · IsSignedIn

Parcels whose current owner is me (My Parcels page), plus my pending and rejected applications.

##### Query

`?include=owned,applications,past` (default `owned,applications`; `past` adds parcels I used to own).

##### Response 200

```
{ "owned": [ Parcel list item, … ],
  "applications": [ Parcel list item with status pending|rejected, … ],
  "past": [],
  "totals": { "count": 2, "acres": "3.10" } }
```

#### `GET /me/notifications` · IsSignedIn

Notifications addressed to my public ID, plus those addressed to each of my roles (`role:Registrar`, `role:Identity officer`), plus new enquiries about my parcels (text "New enquiry about GA-BRK-0003 from Kojo Appiah. Open the title to read it."). Newest first.

##### Query

`?unread=true`, `?before=<iso>`, `?page_size=8` (bell shows 8).

##### Response 200

```
{ "count": 14, "unread": 2, "next": "…", "previous": null, "results": [ Notification, … ] }
```

#### `POST /me/notifications/read` · IsSignedIn

##### Request

```
{ "ids": ["ntf_01JD…"] }       // or { "all": true }
```

##### Response 200

```
{ "unread": 0 }
```

### 9.3 Identity (IdentityRegistry)

#### `POST /identity/submit` · HasWallet · citizen · IdentityRegistry.submitProfile

Prepares the citizen's `submitProfile(cardHash, citizen)` transaction. The card number is hashed in the browser (`hashCard`) and only the hash is sent, as today. Also allowed after a rejection (resubmit).

##### Request

```
{ "card_hash": "0x8b3e5c…d2",          // keccak256("landchain-card:GHA-700000006-6")
  "citizenship": "citizen",             // "citizen" | "non-citizen"
  "full_name": "Efua Mensah" }          // optional; saved to the profile, never on chain
```

##### Pre-checks (same as the contract)

- caller's wallet is not an officer → else `422 CHAIN_REVERT` "Only citizens can submit a profile"
- hash is 32 bytes and not zero → "Card hash is empty"
- status not verified → "Identity already verified"; not pending → "Your profile is already waiting for review"
- `cardOwner(hash)` is zero or me → "This Ghana Card is already linked to another profile"

##### Response 201

```
{ "intent": TxIntent (signer "wallet", status "awaiting_signature", args_label "0x8b3e5c…, citizen") }
```

The UI then sends `intent.tx` with MetaMask and calls [`POST /chain/intents/{id}/submitted`](#ep-intents), or on the local demo `POST /chain/intents/{id}/dev-sign`.

#### `GET /identities` · IsOfficer

People with an on-chain profile. Default filter is the identity queue.

##### Query

`?status=pending` (default) `|verified|rejected|none`, `?q=` name or public ID.

##### Response 200

```
{ "count": 1, "results": [
  { "public_id": "GH-5e0a77c1", "name": "Kwabena Ofori", "address": "0x3e5e…f9a9",
    "status": "pending", "citizenship": "citizen", "card_hash": "0x…",
    "submitted_at": "…", "email": "kwabena@demo.landchain.local", "phone": null } ] }
```

#### `GET /identities/lookup` · IsSignedIn

Used by the Transfer dialog: the owner types the buyer's public ID and sees only whether they can receive a title (PROJECT\_CONTEXT P1 #7). No name is returned.

##### Query

`?public_id=GH-9c2a41d0`

##### Response 200

```
{ "public_id": "GH-9c2a41d0", "exists": true, "verified": true, "is_you": false }
```

##### Errors

`404 NOT_FOUND` unknown public ID (return `{"exists": false}` with 200 if you prefer not to leak existence through status codes; pick one and keep it).

#### `POST /identities/{public_id}/verify` · IsIdentityOfficer · IdentityRegistry.verifyProfile

Signed by the identity-officer role wallet.

##### Request

```
{ "note": "Checked against NIA record" }     // optional, stored in OfficerAction only
```

##### Query

`?wait=true` blocks until `confirmed` (timeout 30 s, then returns 202).

##### Response 202 (or 200 with wait)

```
{ "intent": TxIntent (signer "backend:id_officer", status "queued" | "confirmed", success_message "Identity verified"),
  "identity": { "public_id": "GH-5e0a77c1", "status": "verified" } }   // identity only with 200
```

##### Errors

`403 FORBIDDEN` not an identity officer · `404` unknown public ID · `422 CHAIN_REVERT` "No pending request for this person".

#### `POST /identities/{public_id}/reject` · IsIdentityOfficer · IdentityRegistry.rejectProfile

Same as verify. The contract takes no reason; the optional reason is stored off chain and sent in the notification.

##### Request

```
{ "reason": "Card number does not match the name on file" }
```

##### Response 202 / 200

As verify, `success_message` "Identity rejected".

### 9.4 Documents vault

#### `POST /documents` · HasWallet

Upload one document before submitting an application. Django computes SHA-256 itself, stores the file at `parcel-documents/<sha256>` (content-addressed, so the same file uploaded twice is stored once), and returns the fingerprint to put on chain. Replaces `putFile`, which today runs *after* submission; uploading first means the file is never lost.

##### Request (multipart/form-data)

```
file      = <binary>                  # pdf, jpeg, png; ≤ 20 MB
doc_type  = "Site plan"
sha256    = "0x9f2c…e41a"               # optional: browser's hash; must equal the server's
```

##### Response 201

```
{ "id": "doc_01JD3M…", "sha256": "0x9f2c…e41a", "doc_type": "Site plan",
  "name": "site-plan-efua.pdf", "mime": "application/pdf", "size_bytes": 482113,
  "status": "staged", "created_at": "…" }
```

##### Errors

`400 VALIDATION` unknown doc type, empty file · `413 FILE_TOO_LARGE` · `415 UNSUPPORTED_MEDIA_TYPE` · `422 HASH_MISMATCH` browser hash differs.

Staged documents not attached to a record within 7 days are deleted (job 13.5).

#### `GET /documents/{sha256}/url` · canSeePrivate for a parcel holding this fingerprint

Signed URL to open a file (the "Open" buttons in the title record and review dialog). Replaces `openFile`.

##### Query

`?parcel_id=GA-BRK-0015` (required; access is checked against this parcel).

##### Response 200

```
{ "url": "https://<ref>.supabase.co/storage/v1/object/sign/parcel-documents/0x9f2c…?token=…",
  "expires_in": 60, "name": "site-plan-efua.pdf", "mime": "application/pdf", "doc_type": "Site plan" }
```

##### Errors

`403 PRIVATE` "Files are held by the Lands Commission. Only their fingerprints are public." · `404 FILE_NOT_IN_VAULT` "This file isn't in the vault. Seeded demo parcels have fingerprints only." · `404` fingerprint not on that parcel.

#### `POST /parcels/{parcel_id}/documents/check` · Public

"Have a copy? Check it against the register." Hashing can stay in the browser (send only the hash, so the file never leaves the visitor's device); a multipart file is also accepted.

##### Request

```
{ "sha256": "0x9f2c…e41a" }            // or multipart file=<binary>
```

##### Response 200

```
{ "match": true, "doc_type": "Site plan",
  "message": "This file matches the registered Site plan. It hasn't been changed." }
// no match:
{ "match": false, "doc_type": null,
  "message": "This file doesn't match any document registered for this parcel." }
```

### 9.5 Parcels and map

#### `GET /parcels` · Public

Map and Verify list. Current records only. Rejected parcels excluded unless asked.

##### Query

|  |  |
| --- | --- |
| `status` | `pending,registered,transfer_pending` (default), add `rejected` to include |
| `bbox` | `minLng,minLat,maxLng,maxLat` (PostGIS `&&`) |
| `owner` | public ID |
| `region`, `interest` | exact |
| `format` | `json` (default) or `geojson` |
| `ordering` | `parcel_id` (default), `-registered_at`, `-updated_at`, `acres` |

##### Response 200 (json)

```
{ "count": 14, "next": null, "previous": null, "results": [ Parcel list item, … ] }
```

##### Response 200 (geojson)

```
{ "type": "FeatureCollection",
  "features": [ { "type": "Feature", "id": "GA-BRK-0003",
    "geometry": { "type": "Polygon", "coordinates": [[[-0.2281, 5.7509], …, [-0.2281, 5.7509]]] },
    "properties": { "parcel_id": "GA-BRK-0003", "status": "registered", "title_no": 3, "acres": "2.05",
                    "interest": "Leasehold", "holder": "Berekuso Stool", "region": "Eastern",
                    "owner": PersonRef } } ] }
```

GeoJSON uses `[lng, lat]` order; the JSON format uses `[lat, lng]` like the UI.

#### `GET /parcels/search` · Public

Map search box: "Parcel ID, owner ID or token #". Exact match first, then contains.

##### Query

`?q=GA-BRK-0003` | `?q=GH-7d4e` | `?q=#3`

##### Response 200

```
{ "results": [ Parcel list item, … ], "best": "GA-BRK-0003" }
```

#### `GET /parcels/{parcel_id}` · Public (privacy-filtered)

Title record. Case-insensitive parcel ID. Resolves to the latest record; `?record_id=` fetches an older one.

##### Response 200

A [Parcel (detail)](#obj-parcel).

##### Errors

`404 NOT_FOUND` "No parcel called GA-BRK-0099."

#### `GET /parcels/{parcel_id}/history` · Public

On-chain history, oldest first (block order).

##### Response 200

```
{ "parcel_id": "GA-BRK-0001", "results": [ HistoryEvent, … ] }
```

#### `GET /parcels/next-id` · Public

Suggests the next free parcel ID (Register page placeholder; today it counts up from 15).

##### Query

`?prefix=GA-BRK`

##### Response 200

```
{ "parcel_id": "GA-BRK-0015" }
```

#### `POST /parcels/boundary-check` · Public

Live check while drawing: area, plots, overlap, Ghana box, duplicate boundary. Replaces `validateBoundary` and `areaAcres`.

##### Request

```
{ "pillars": [[5.750912, -0.228113], [5.751204, -0.227401], [5.750633, -0.227088]],
  "ignore_parcel_id": null }
```

##### Response 200

```
{ "ok": false,
  "acres": "0.62", "acres_x100": 62,
  "plots_100x70ft": "3.9",               // acres ÷ (100 × 70 × 0.092903 / 4046.8564)
  "pillar_count": 3,
  "inside_ghana": true,
  "overlaps": "GA-BRK-0004",             // null if clear
  "duplicate_boundary": false,
  "error": "Boundary overlaps neighbouring parcel GA-BRK-0004" }
```

Possible `error` values: "A boundary needs at least 3 corner pillars", "A boundary can have at most 32 corner pillars", "All pillars must be inside Ghana", "Boundary overlaps neighbouring parcel …", "This boundary is already registered".

#### `GET /stats` · Public

"Register snapshot" card and map filter counts.

##### Response 200

```
{ "registered_titles": 11, "applications_pending": 2, "completed_transfers": 2, "title_holders": 5,
  "by_status": { "registered": 10, "transfer_pending": 1, "pending": 2, "rejected": 0 },
  "block": 212 }
```

### 9.6 Applications (registration)

#### `POST /applications` · IsVerifiedCitizen · TitleRegistry.submitApplication

Prepares the application transaction from the Register Land form. The server converts degrees to micro-degrees, computes `acresX100`, uppercases plan number and GPS address, and puts the staged documents' types and fingerprints in `docs` (file names stay off chain).

##### Request

```
{ "parcel_id": "GA-BRK-0015",
  "interest": "Leasehold",
  "holder": "Berekuso Stool",
  "region": "Eastern",
  "location": "Berekuso, Eastern Region",      // optional; default "Berekuso, {region} Region"
  "plan_number": "SER B4115/26",
  "gps_address": "EA-1805-5795",               // optional
  "pillars": [[5.752101, -0.229004], [5.752390, -0.228310], [5.751822, -0.228011], [5.751530, -0.228702]],
  "documents": ["doc_01JD3M…", "doc_01JD3N…", "doc_01JD3P…"] }
```

##### Validation (400 VALIDATION, field\_errors)

- `parcel_id` matches `AA-AAA-0000` → "Parcel ID must look like GA-BRK-0015"
- `holder` non-empty → "Name the allodial holder"; `plan_number` non-empty → "Add the regional plan number from the site plan"
- `gps_address` empty or `^[A-Z]{2}-\d{3,4}-\d{4}$` → "Format: two letters, then numbers, e.g. EA-1805-5795"
- pillars 3–32, inside Ghana, no overlap (boundary-check rules)
- documents: each owned by the caller and staged; Site plan, Indenture and Search report present → "Still needed: Indenture, Search report."

##### Chain pre-checks (422 CHAIN\_REVERT)

"Verify your identity before registering land", "Parcel ID GA-BRK-0015 is already used", "This boundary is already registered", "Area must be greater than zero".

##### Response 201

```
{ "intent": TxIntent (action "submitApplication", args_label "\"GA-BRK-0015\", 4 pillars",
                      success_message "Application submitted"),
  "preview": { "parcel_id": "GA-BRK-0015", "acres": "1.30", "acres_x100": 130,
               "docs": [ { "doc_type": "Site plan", "sha256": "0x…" }, … ] } }
```

On `confirmed`, `intent.result` = `{"application_id": "APP-15", "record_id": 15, "parcel_id": "GA-BRK-0015"}` and the documents become `attached`. The UI then shows "Application GA-BRK-0015 submitted" with the 4 next steps.

#### `GET /applications` · IsSignedIn

Officers see all; citizens see their own.

##### Query

`?decision=waiting` (default for officers) `|approved|rejected`, `?parcel_id=`, `?applicant=`.

##### Response 200

```
{ "count": 2, "results": [ Application + { "parcel": Parcel list item }, … ] }
```

#### `GET /applications/{id}` · IsOfficer or applicant

Review dialog: application, parcel detail (map, plan number, pillars, documents with `can_open`), and the fee checklist.

##### Response 200

```
{ "application": Application,
  "parcel": Parcel (detail),
  "fee_checklist": [
    { "kind": "Official search", "required": false, "recorded": true,  "payment": Payment, "suggested_ghs": "163.00" },
    { "kind": "Stamp duty", "required": true, "recorded": false, "payment": null, "suggested_ghs": null,
      "how": "0.25% up to GH¢ 10,000, 0.5% up to GH¢ 50,000, 1% above, of the price paid", "paid_to": "Ghana Revenue Authority" },
    { "kind": "First registration", "required": true, "recorded": false, "payment": null, "suggested_ghs": "2356.00",
      "how": "GH¢ 1,148–1,178 per acre or part of an acre", "paid_to": "Lands Commission" } ],
  "can_approve": false,
  "blocked_reason": "Record the stamp duty and registration fee receipts first. The contract refuses approval without them." }
```

#### `POST /applications/{id}/approve` · IsRegistrar · TitleRegistry.approveApplication

Mints the title NFT to the applicant. Signed by the registrar role wallet.

##### Request

```
{ "note": "Site visit 18 Nov, boundary pillars confirmed" }    // optional, off chain
```

##### Response 202 / 200 (?wait=true)

```
{ "intent": TxIntent (success_message "Registered: title NFT minted"),
  "parcel": Parcel (detail) }        // only with 200: status "registered", title_no set
```

##### Errors (422 CHAIN\_REVERT)

"Record the stamp duty receipt before approving", "Record the registration fee before approving", "This application has already been decided", "Application not found" (404), "Only the registrar can approve a registration" (403 if the caller lacks the role; this message only appears if the backend wallet lost its on-chain role, which should alert admins).

#### `POST /applications/{id}/reject` · IsRegistrar · TitleRegistry.rejectApplication

The reason goes on chain (public). Tell officers in the UI not to put personal data in it.

##### Request

```
{ "reason": "Site plan not approved by Survey & Mapping" }     // required, 1–280 chars
```

##### Response 202 / 200

`intent` with `success_message` "Application rejected". Frees the parcel ID and boundary.

##### Errors

`400 VALIDATION` / `422` "A reason is required to reject", "This application has already been decided".

### 9.7 Fees and payments (FeeLedger)

#### `GET /fees/schedule` · Public

From `fees.ts`. Estimates only; the source text must be shown.

##### Response 200

```
{ "kinds": [
  { "kind": "Official search", "index": 0, "paid_to": "Lands Commission", "how": "GH¢ 163 for a land certificate search", "required_for": [] },
  { "kind": "Stamp duty", "index": 1, "paid_to": "Ghana Revenue Authority", "how": "0.25% up to GH¢ 10,000, 0.5% up to GH¢ 50,000, 1% above, of the price paid", "required_for": ["registration"] },
  { "kind": "First registration", "index": 2, "paid_to": "Lands Commission", "how": "GH¢ 1,148–1,178 per acre or part of an acre", "required_for": ["registration"] },
  { "kind": "Transfer", "index": 3, "paid_to": "Lands Commission", "how": "GH¢ 973 per acre or part of an acre", "required_for": ["transfer"] } ],
  "source": "Lands Commission fee schedule as reported by YEN.com.gh (27 Oct 2026). Stamp Duty Act 2005 (Act 689) as amended by Act 1109. Estimates: confirm with the Lands Commission and the GRA." }
```

#### `GET /fees/estimate` · Public

Suggested amount. Rules: search 163; stamp duty = round(price × rate), rate 0.25% if price ≤ 10,000, 0.5% if < 50,000, else 1%; first registration 1,178 × max(1, ceil(acres)); transfer 973 × max(1, ceil(acres)).

##### Query

`?kind=Stamp duty&acres=1.24&consideration=60000` or `?kind=First registration&parcel_id=GA-BRK-0015`

##### Response 200

```
{ "kind": "Stamp duty", "suggested_ghs": "600.00", "suggested_pesewas": 60000, "basis": "1% of GH¢ 60,000.00" }
```

#### `GET /parcels/{parcel_id}/payments` · canSeePrivate

##### Response 200

```
{ "parcel_id": "GA-BRK-0002", "total_ghs": "3076.00", "results": [ Payment, … ] }
```

##### Errors

`403 PRIVATE` "Receipts are private. Only the owner and the Lands Commission can see what was paid for GA-BRK-0002."

#### `POST /parcels/{parcel_id}/payments` · IsRegistrar · FeeLedger.recordPayment

The registrar records an official receipt from the Review Queue fee recorder. The receipt number is hashed (keccak256 of the trimmed, uppercased number) and the plain number is kept in `PaymentReceipt`. For `Transfer`, the contract binds the fee to the parcel's open transfer.

##### Request

```
{ "kind": "Stamp duty",                    // or "kind_index": 1
  "amount_ghs": "600.00",                  // > 0; if omitted, the suggested amount is used
  "receipt_no": "GRA-SD-2026-004411",
  "consideration_ghs": "60000.00",         // stamp duty only, off chain
  "transfer_id": "TRF-3" }                 // optional check for Transfer: must equal the open transfer
```

##### Response 202 / 200

```
{ "intent": TxIntent (args_label "\"GA-BRK-0015\", Stamp duty", success_message "Stamp duty receipt recorded"),
  "payment": Payment }                     // only with 200
```

##### Errors

`400` "Add the official receipt number" · `404` "Parcel GA-BRK-0099 does not exist" · `422 CHAIN_REVERT` "Amount must be greater than zero", "This receipt has already been recorded", "This fee is already recorded for the parcel", "There is no transfer waiting for this parcel", "The transfer fee is already recorded".

### 9.8 Transfers of ownership

#### `POST /transfers` · IsVerifiedCitizen · owner · TitleRegistry.requestTransfer

The owner asks to record a new owner (sale or gift agreed off the platform). The buyer is given by public ID; the server resolves the address.

##### Request

```
{ "parcel_id": "GA-BRK-0002", "to_public_id": "GH-9c2a41d0" }
```

##### Errors

`404` "Pick the new owner" (unknown public ID) · `422 CHAIN_REVERT` "Only the owner can transfer this title", "Only a registered title with no pending transfer can be transferred", "You already own this title", "The new owner must have a verified identity".

##### Response 201

```
{ "intent": TxIntent (signer "wallet", args_label "\"GA-BRK-0002\", GH-9c2a41d0",
                      success_message "Transfer requested: waiting for the registrar") }
```

On confirm, `result` = `{"transfer_id": "TRF-4", "parcel_id": "GA-BRK-0002"}`.

#### `POST /transfers/{id}/cancel` · HasWallet · requester · TitleRegistry.cancelTransfer

##### Request

```
{}
```

##### Response 201

`intent` (wallet), `success_message` "Transfer cancelled".

##### Errors

`422` "Only the owner who asked can cancel this transfer", "This transfer has already been decided", `404` "Transfer not found".

#### `GET /transfers` · IsSignedIn

Officers see all; citizens see transfers where they are `from` or `to`.

##### Query

`?decision=waiting`, `?parcel_id=`, `?role=from|to`

##### Response 200

```
{ "count": 1, "results": [ TransferRequest, … ] }
```

#### `GET /transfers/{id}` · IsOfficer, from or to

Transfer review dialog.

##### Response 200

```
{ "transfer": TransferRequest,
  "parcel": Parcel (detail),
  "fee_checklist": [ { "kind": "Transfer", "required": true, "recorded": false, "suggested_ghs": "973.00", … } ],
  "can_approve": false,
  "blocked_reason": "Record the transfer fee before approving",
  "reminder": "Check the signed indenture before approving. Approving moves the title NFT to the new owner and adds them to the on-chain owner history." }
```

#### `POST /transfers/{id}/approve` · IsRegistrar · TitleRegistry.approveTransfer

##### Request

```
{ "note": "Indenture dated 12 Nov 2026 sighted" }          // optional
```

##### Response 202 / 200

`intent`, `success_message` "Transfer approved: title moved to the new owner"; with 200 also the updated `parcel`.

##### Errors

`422` "Record the transfer fee before approving", "The new owner must have a verified identity", "This transfer has already been decided".

#### `POST /transfers/{id}/reject` · IsRegistrar · TitleRegistry.rejectTransfer

##### Request

```
{ "reason": "Indenture not signed by all family heads" }   // required, public on chain
```

##### Response 202 / 200

`intent`, `success_message` "Transfer rejected".

### 9.9 Chain intents

#### `GET /chain/intents/{id}` · creator or IsOfficer

Poll every 1–2 s until `confirmed`, `reverted`, `failed` or `expired`. Replaces the toast flow in `chainAct` ("Sending to Local Ganache…" → "Confirmed in block 213 · 0x8f1c2a…").

##### Response 200

A [TxIntent](#obj-intent).

#### `POST /chain/intents/{id}/submitted` · creator

The UI reports the hash MetaMask returned. The backend checks the transaction matches the intent and starts watching its receipt.

##### Request

```
{ "tx_hash": "0x8f1c2a…" }
```

##### Response 200

`TxIntent` with status `submitted` (or already `mined`).

##### Errors

`409 INTENT_NOT_AWAITING` · `410 INTENT_EXPIRED` · `422 TX_MISMATCH` "This transaction is not the one prepared for this action." · `404 TX_NOT_FOUND` after 60 s of retries.

#### `POST /chain/intents/{id}/rejected-by-wallet` · creator

The user cancelled in MetaMask (error code 4001). Marks the intent `failed` with "You cancelled the transaction in your wallet" so it shows in the activity log as the frontend does today.

##### Request

```
{ "code": 4001, "message": "User denied transaction signature." }
```

#### `POST /chain/intents/{id}/dev-sign` · creator · local chain only

Sends the prepared transaction from Ganache's unlocked account (no wallet). `404` unless `CHAIN_ALLOW_UNLOCKED_SIGNING=true` and chain 1337; `403 CANNOT_SIGN` "This account can't sign here. Connect it in MetaMask or pick a demo account." if the address isn't unlocked.

##### Response 200

`TxIntent` (`signer` becomes `dev_unlocked`; usually already `mined`).

### 9.10 Review queue

#### `GET /review/queue` · IsOfficer

The three cards of the Review Queue, with a hint for items the caller's role cannot act on ("Only the registrar can act").

##### Response 200

```
{ "acting_as": { "name": "Abena Sarpong", "roles": ["Identity officer"] },
  "identities":   { "count": 1, "can_act": true,  "items": [ { "public_id": "GH-5e0a77c1", "name": "Kwabena Ofori", "citizenship": "citizen", "submitted_at": "…" } ] },
  "applications": { "count": 2, "can_act": false, "items": [ { "id": "APP-13", "parcel_id": "GA-BRK-0013", "holder": "Berekuso Stool", "applicant": PersonRef, "acres": "1.10", "created_at": "…", "fees_ready": true } ] },
  "transfers":    { "count": 1, "can_act": false, "items": [ { "id": "TRF-3", "parcel_id": "GA-BRK-0006", "from": PersonRef, "to": PersonRef, "requested_at": "…", "transfer_fee_recorded": false } ] } }
```

#### `GET /review/counts` · IsOfficer

Badge in the nav: items the caller can act on (`pendingCountFor`). Identity officer counts identities; registrar counts applications + transfers.

##### Response 200

```
{ "total": 3, "actionable": 1, "identities": 1, "applications": 2, "transfers": 1 }
```

### 9.11 Enquiries

#### `POST /parcels/{parcel_id}/enquiries` · Public

"Enquire about this land". Goes to the current owner without revealing them. Not allowed on rejected parcels, by officers, or by the owner themself.

##### Request

```
{ "name": "Kojo Appiah",                     // 2–120
  "contact": "024 000 0000",                 // phone or email, 5–160
  "message": "I'm interested in buying this plot. Is it available?",   // 1–2000
  "captcha_token": "…" }                     // required for anonymous callers when CAPTCHA is enabled
```

##### Response 201

```
{ "id": "enq_01JD…", "parcel_id": "GA-BRK-0003", "status": "sent",
  "message": "Enquiry sent to the owner. If they're interested, they'll contact you." }
```

Side effects: notification to the owner, and an email / SMS relay (job 13.3) containing the message and the enquirer's contact. The response never contains the owner's identity.

##### Errors

`400 VALIDATION` · `403 CANNOT_ENQUIRE` "You own this parcel." / "Lands Commission accounts can't send enquiries." · `409` rejected parcel · `429`.

#### `GET /me/enquiries` · IsSignedIn

The owner's inbox (Enquiries section on the title record). Only enquiries addressed to my public ID.

##### Query

`?parcel_id=GA-BRK-0003`, `?status=new`

##### Response 200

```
{ "count": 1, "new": 1, "results": [ Enquiry, … ] }
```

#### `PATCH /enquiries/{id}` · recipient

Replaces `markEnquiry` (read on hover, "Mark as answered").

##### Request

```
{ "status": "read" }          // "read" | "answered"
```

##### Response 200

The updated `Enquiry`.

### 9.12 Activity log and receipt

#### `GET /activity` · Public (names filtered)

Every contract call, newest first, including refused simulations (`RevertLog`) and wallet cancellations. Now shared by everyone, where today reverts are kept per browser.

##### Query

|  |  |
| --- | --- |
| `parcel` | substring of `args_label` (UI's "Filter by parcel") |
| `from` | public ID |
| `contract` | `IdentityRegistry | TitleRegistry | FeeLedger | LandAccessControl` |
| `status` | `Success | Reverted` |
| `before`, `page_size` | pagination |

##### Response 200

```
{ "count": 186, "next": "…", "results": [ ActivityTx, … ],
  "facets": { "contracts": ["IdentityRegistry", "TitleRegistry", "FeeLedger"],
              "people": [ PersonRef, … ] } }
```

#### `GET /parcels/{parcel_id}/receipt` · canSeePrivate

Statement of costs. One row per distinct transaction on the parcel (an approval that also mints is one row). Gas comes from stored receipts (replaces `chain/gas.ts`).

##### Response 200

```
{ "parcel": { "parcel_id": "GA-BRK-0002", "title_no": 2, "owner": PersonRef, "plan_number": "SER B4102/25",
              "acres": "1.24", "interest": "Customary freehold", "location": "Berekuso, Eastern Region" },
  "fees": { "total_ghs": "3076.00", "items": [ Payment, … ] },
  "transactions": {
    "items": [ { "label": "Application", "tx_hash": "0x…", "signed_by": PersonRef, "block": 18,
                 "gas_used": 512344, "gas_price_gwei": "2", "cost_eth": "0.001025", "at": "…" },
               { "label": "Record stamp duty receipt", … },
               { "label": "Registration", … } ],
    "total_eth": "0.001411",
    "owner_signed_eth": "0.001025" },
  "chain_name": "Local Ganache",
  "notes": [ "On Local Ganache this is test ETH with no real value. Officer transactions are paid by the Lands Commission's own wallet.",
             "Fee amounts are what the registrar recorded from the official receipts." ] }
```

##### Errors

`403 PRIVATE` "Receipts are private. Only the owner and the Lands Commission can see what was paid for GA-BRK-0002."

### 9.13 Admin

#### `GET /admin/officers` · IsAdmin

##### Response 200

```
{ "results": [ { "user_id": "…", "name": "Abena Sarpong", "email": "abena@…", "roles": ["id_officer"], "since": "…" } ],
  "signers": { "registrar": "0x90f8…c9c1", "id_officer": "0xffcf…09f0", "admin": "0x90f8…c9c1" } }
```

#### `POST /admin/officers` · IsAdmin

Give a Supabase user an officer role. Off chain only: the person acts through the role wallet. Syncs `app_metadata.landchain_roles`.

##### Request

```
{ "email": "kwame@lands.gov.gh", "roles": ["registrar"] }    // or "user_id"
```

##### Response 200

The officer row.

##### Errors

`404` no Supabase user with that email · `409 OFFICER_HAS_WALLET` a person with a linked citizen wallet holding titles can't be an officer (decide in 18.4).

#### `DELETE /admin/officers/{user_id}` · IsAdmin

Removes all officer roles. `?role=registrar` removes one. Returns `204`.

#### `POST /admin/chain/roles` · IsAdmin · LandAccessControl.grantRole / revokeRole

Rotate a role wallet on chain (e.g. new registrar key). Signed by the admin wallet.

##### Request

```
{ "action": "grant", "role": "REGISTRAR_ROLE", "address": "0x…" }      // action grant | revoke
```

##### Response 202

`{ "intent": TxIntent }`

#### `GET /admin/signers` · IsAdmin

##### Response 200

```
{ "results": [ { "role": "registrar", "address": "0x90f8…c9c1", "balance_eth": "998.41", "pending_nonce": 57,
                 "has_role_on_chain": true, "queue_depth": 0, "low_balance": false } ] }
```

#### `POST /admin/indexer/resync` · IsAdmin

Wipe the projection for the current chain and re-index from `startBlock`. Use after `npm run chain:fresh` + `setup:all`.

##### Request

```
{ "from_block": 0 }          // optional
```

##### Response 202

```
{ "job_id": "…", "from_block": 0, "head_block": 212 }
```

## 10. Errors and revert catalog

### 10.1 Error codes

| HTTP | code | When |
| --- | --- | --- |
| 400 | `VALIDATION` | Bad body or query; `field_errors: {"plan_number": ["Add the regional plan number from the site plan"]}` |
| 400 | `NONCE_INVALID`, `SIGNATURE_INVALID` | Wallet linking |
| 401 | `TOKEN_EXPIRED`, `TOKEN_INVALID`, `AUTH_REQUIRED` | Missing or bad Supabase token |
| 403 | `FORBIDDEN` | Role missing ("Only the registrar can approve a registration") |
| 403 | `PRIVATE` | Privacy rule blocks documents / fees / receipt |
| 403 | `WALLET_REQUIRED`, `IDENTITY_NOT_VERIFIED`, `CANNOT_SIGN`, `CANNOT_ENQUIRE`, `MFA_REQUIRED` | Precondition on the caller |
| 404 | `NOT_FOUND`, `FILE_NOT_IN_VAULT`, `TX_NOT_FOUND` |  |
| 409 | `WALLET_IN_USE`, `WALLET_ALREADY_LINKED`, `WALLET_IS_OFFICER`, `INTENT_NOT_AWAITING`, `IDEMPOTENCY_CONFLICT` | State conflict off chain |
| 410 | `INTENT_EXPIRED` |  |
| 413 / 415 | `FILE_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE` | Uploads |
| 422 | `CHAIN_REVERT` | The contract refused (simulation or mined revert). `message` = `revert_reason` = the Solidity `require` sentence, shown to the user as is. |
| 422 | `HASH_MISMATCH`, `TX_MISMATCH` |  |
| 429 | `RATE_LIMITED` |  |
| 503 | `CHAIN_UNAVAILABLE` | RPC unreachable: "Can't reach http://127.0.0.1:7545. Is the chain running?"; contracts missing: "This chain doesn't have the current LandChain contracts…" |
| 503 | `SIGNER_UNAVAILABLE` | Role wallet missing, unfunded, or lost its on-chain role |

Revert reason extraction: port `revertReason()` from `chain/client.ts`. With web3.py, catch `ContractLogicError` and use `e.message`, stripping the prefixes `"execution reverted: "`, `"VM Exception while processing transaction: revert "`, `"reverted with reason string '…'"`. OpenZeppelin custom errors (`ERC721…`, `AccessControl…`) arrive as 4-byte selectors: decode with the ABI and map to a sentence.

### 10.2 Every contract `require` message

| Contract.function | Message (exact) | API mapping |
| --- | --- | --- |
| IdentityRegistry.submitProfile | Only citizens can submit a profile | 422 (pre-check: 409 `WALLET_IS_OFFICER` at link time) |
| Card hash is empty | 400 |
| Identity already verified | 422 |
| Your profile is already waiting for review | 422 |
| This Ghana Card is already linked to another profile | 422 |
| IdentityRegistry.verifyProfile / rejectProfile | Only an identity officer can do this · No pending request for this person | 403 · 422 |
| TitleRegistry.submitApplication | Verify your identity before registering land | 403 `IDENTITY_NOT_VERIFIED` |
| Parcel ID must look like GA-BRK-0015 | 400 |
| Parcel ID {id} is already used | 422 |
| Latitudes and longitudes must pair up | 400 (never happens: server builds both arrays) |
| A boundary needs at least 3 corner pillars | 400 |
| A boundary can have at most 32 corner pillars | 400 |
| All pillars must be inside Ghana | 400 |
| This boundary is already registered | 422 |
| Area must be greater than zero | 400 |
| Name the allodial holder · Add the regional plan number from the site plan | 400 |
| TitleRegistry.approveApplication | Only the registrar can approve a registration · Application not found · This application has already been decided · Record the stamp duty receipt before approving · Record the registration fee before approving | 403 · 404 · 422 · 422 · 422 |
| TitleRegistry.rejectApplication | Only the registrar can reject a registration · A reason is required to reject · (as above) | 403 · 400 |
| TitleRegistry.requestTransfer | Parcel does not exist · Only the owner can transfer this title · Only a registered title with no pending transfer can be transferred · You already own this title · The new owner must have a verified identity | 404 · 422 ×4 |
| TitleRegistry.cancelTransfer | Transfer not found · This transfer has already been decided · Only the owner who asked can cancel this transfer | 404 · 422 · 422 |
| TitleRegistry.approveTransfer | Only the registrar can approve a transfer · The new owner must have a verified identity · Record the transfer fee before approving | 403 · 422 · 422 |
| TitleRegistry.rejectTransfer | Only the registrar can reject a transfer · A reason is required to reject | 403 · 400 |
| TitleRegistry.setFeeLedger | Only the admin can connect the fee ledger · Fee ledger already set | Not exposed (migration only) |
| TitleRegistry transfers (ERC-721) | Titles move only through a registrar-approved transfer | Not exposed |
| FeeLedger.recordPayment | Only the registrar can record a payment · Parcel does not exist · Amount must be greater than zero · Add the official receipt number · This receipt has already been recorded · There is no transfer waiting for this parcel · The transfer fee is already recorded · This fee is already recorded for the parcel | 403 · 404 · 400 · 400 · 422 ×4 |
| FeeLedger.getPayment | Payment not found | 404 |

## 11. Privacy rules (server side)

Port of `privacy.ts`, implemented once in `landchain/core/privacy.py` and used by every serializer.

```
def can_see_private(viewer: Profile | None, parcel: Parcel) -> bool:
    """Officers and the parcel's own owner, applicant or past owners see its private details."""
    if viewer is None: return False
    if viewer.is_officer: return True
    pid = viewer.public_id
    return pid is not None and (pid == parcel.owner_public_id
                                or pid in parcel.owner_public_ids
                                or pid == parcel.applicant_public_id)

def shown_name(viewer: Profile | None, person_public_id: str) -> str | None:
    """Officers' names always (they act officially); everyone else's only to officers and themselves."""
    target = profile_by_public_id(person_public_id)        # role wallets map to "Lands Commission registrar" etc.
    if target is None: return None
    if target.is_officer_wallet: return target.role_label
    if viewer and (viewer.is_officer or viewer.public_id == person_public_id): return target.full_name or None
    return None
```

| Field | Public | Owner / past owner / applicant | Officer |
| --- | --- | --- | --- |
| Parcel record, status, boundary, plan no., GPS address, holder, interest, title no. | ✓ | ✓ | ✓ |
| Owner & owner history public IDs, on-chain history, document types & fingerprints | ✓ | ✓ | ✓ |
| Person names | officers only | own name + officers | all |
| Document files, original file names | ✗ | ✓ | ✓ |
| Fees, receipt page, receipt hashes | ✗ | ✓ | ✓ |
| Plain receipt numbers, consideration | ✗ | ✗ | ✓ |
| Enquiry content | ✗ | current owner it was sent to | ✗ (not even officers; decide in 18.5) |
| Email, phone, card hash | ✗ | own | ✓ (identity queue) |
| Which officer pressed a button (OfficerAction) | ✗ | ✗ | ✓ |

Note: fee amounts and receipt hashes are public on chain (anyone with a node can read them). The API hides them as the UI does today; it is presentation privacy, not secrecy.

## 12. Notifications catalog

Created by the indexer, same texts as `snapshot.ts`.

| Event | kind | To | Text | Relay |
| --- | --- | --- | --- | --- |
| ProfileSubmitted | `identity_submitted` | role:Identity officer | New identity request from GH-… | email officers (digest) |
| ProfileVerified | `identity_verified` | person | Your identity has been verified | email/SMS |
| ProfileRejected | `identity_rejected` | person | Your identity request was rejected (+ off-chain reason) | email/SMS |
| ApplicationSubmitted | `application_submitted` | role:Registrar | New title application GA-BRK-0015 waiting for your review | digest |
| ApplicationRejected | `application_rejected` | applicant | Your application GA-BRK-0015 was rejected: {reason} | email/SMS |
| TitleMinted | `title_issued` | owner | Title GLT #15 issued for GA-BRK-0015 | email/SMS |
| TransferRequested | `transfer_requested` | role:Registrar | Transfer of GA-BRK-0006 waiting for approval | digest |
| TransferRequested | `transfer_requested_to_you` | to | GH-… asked to transfer GA-BRK-0006 to you | email/SMS |
| TransferApproved | `transfer_received` / `transfer_approved` | to / from | GA-BRK-0006 is now registered to you / Transfer of GA-BRK-0006 approved | email/SMS |
| TransferRejected | `transfer_rejected` | from | Transfer of GA-BRK-0006 was rejected: {reason} | email/SMS |
| PaymentRecorded | `payment_recorded` | payer | Stamp duty receipt of GH¢ 600.00 recorded for GA-BRK-0015 | in-app |
| Enquiry created | `enquiry_received` | owner | New enquiry about GA-BRK-0003 from Kojo Appiah. Open the title to read it. | email/SMS with message + contact |

## 13. Background jobs (Celery)

1. **indexer.tick** (beat, 2 s local / 6 s Sepolia, single instance via Redis lock): section 6.5.
2. **signer.send** (queues `signer.registrar`, `signer.id_officer`, `signer.admin`, concurrency 1): re-simulate, sign, send, store hash, hand to watcher.
3. **notify.relay**: email (Django email backend: SMTP / Resend / SES) and SMS (Hubtel or Twilio for Ghana numbers) for notifications marked relay; retries 3× with backoff; respects `notify_email` / `notify_sms`.
4. **documents.attach** (after each indexed `ApplicationSubmitted`): for each on-chain doc hash, mark the matching staged `Document` of the applicant `attached` with the record id. Fingerprints with no file → `file_available=false`.
5. **documents.cleanup** (daily): delete staged files older than 7 days that never reached a record; never delete attached files.
6. **intents.watch** (every 3 s): fetch receipts for `submitted` intents; mark `mined`/`reverted`; expire `awaiting_signature` after 15 min; `failed` if the hash is unknown after 10 min (Sepolia: check for replacement by nonce).
7. **signers.health** (every 5 min): balance and on-chain role of each signer; alert admins.

## 14. Settings and environment variables

| Variable | Example | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `ALLOWED_HOSTS` |  |  |
| `DATABASE_URL` | `postgresql://postgres.<ref>:…@aws-0-eu-west-2.pooler.supabase.com:5432/postgres` | Supabase session pooler or direct |
| `DB_SCHEMA` | `landchain` | search\_path |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |  |
| `SUPABASE_SERVICE_ROLE_KEY` | secret | Storage + Admin API, server only |
| `SUPABASE_JWT_SECRET` | secret | Only for HS256 projects |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |  |
| `SUPABASE_DOCS_BUCKET` | `parcel-documents` |  |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + locks |
| `CHAIN_ID` | `1337` / `11155111` |  |
| `RPC_URL` | `http://127.0.0.1:7545` | Server-side RPC (Sepolia: Infura/Alchemy key) |
| `RPC_URL_PUBLIC` | `http://127.0.0.1:7545` | Returned in `/config` for MetaMask |
| `CONTRACTS_DIR` | `../landchain-contracts/shared` | Reads `abi/*.json` and `deployments.local.json`; or set the four `*_ADDRESS` vars and `START_BLOCK` |
| `CHAIN_CONFIRMATIONS` | `0` local / `2` Sepolia |  |
| `REGISTRAR_SIGNER_KEY`, `ID_OFFICER_SIGNER_KEY`, `ADMIN_SIGNER_KEY` | 0x… | Locally Ganache deterministic keys of accounts 0, 1, 0 (printed by `npm run chain`). Production: KMS references instead. |
| `CHAIN_ALLOW_UNLOCKED_SIGNING` | `true` | Local only; forced false when `CHAIN_ID≠1337` |
| `DEMO_MODE`, `DEMO_PASSWORD` | `true`, `landchain-demo` | Seeds and lists demo users |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` |  |
| `SITE_DOMAIN`, `SITE_URI` | `localhost:5173` | SIWE message domain/URI |
| `EMAIL_*`, `SMS_PROVIDER`, `SMS_API_KEY`, `SMS_SENDER_ID` |  | Relay |
| `CAPTCHA_SECRET` |  | Turnstile/hCaptcha for anonymous enquiries |
| `REQUIRE_OFFICER_MFA` | `false` | Require `aal2` on officer writes |

Frontend additions: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. `VITE_CHAIN_ID` / `VITE_RPC_URL` can be replaced by `GET /config`.

## 15. Django project layout

```
land-backend/
├─ manage.py
├─ pyproject.toml          # django~=5.1, djangorestframework, drf-spectacular, django-cors-headers, django-ratelimit,
│                          # psycopg[binary], dj-database-url, PyJWT[crypto], supabase, web3~=7, eth-account,
│                          # celery[redis], shapely, pyproj, python-ulid, pytest-django, factory-boy
├─ config/                 # settings.py, urls.py (/api/v1/ + /api/v1/schema/ + /api/v1/docs/), celery.py
└─ landchain/
   ├─ core/                # errors.py (exception handler + codes), pagination.py, privacy.py, ids.py, permissions.py, idempotency.py
   ├─ accounts/            # Profile, WalletNonce, auth.py (SupabaseJWTAuthentication), SIWE views, /me, admin officers
   ├─ chain/               # web3 client, contracts loader (ABIs + addresses), encoding.py (6.4), simulate.py,
   │                       # TxIntent, OfficerAction, RevertLog, signer tasks, intents views, /config, /chain/status
   ├─ indexer/             # IndexerCursor, ChainBlock, ChainEvent, ChainTx, handlers per event, run_indexer command
   ├─ registry/            # projection models: ChainIdentity, ChainRole, Parcel, ParcelDoc, OwnerHistory, Application,
   │                       # TransferRequest, HistoryEvent; parcels/applications/transfers/identity views; geo.py
   ├─ fees/                # Payment (projection), PaymentReceipt, schedule.py (port of fees.ts), views
   ├─ documents/           # Document, storage.py (Supabase Storage), upload/url/check views, attach/cleanup tasks
   ├─ enquiries/           # Enquiry, views, relay task
   ├─ notifications/       # Notification, NotificationRead, views, relay
   └─ demo/                # seed_demo_users command, /dev/demo-accounts
```

Management commands: `migrate`, `run_indexer`, `seed_demo_users`, `sync_contracts --from ../landchain-contracts/shared`, `check_signers`.

Sketch of a chain write, officer side:

```
# landchain/registry/views.py
class ApproveApplication(APIView):
    permission_classes = [IsRegistrar]
    def post(self, request, app_id):
        app = get_object_or_404(Application, app_id=parse_id(app_id, "APP"))
        intent = chain.write(
            signer="registrar", contract="TitleRegistry", function="approveApplication",
            args=[app.app_id], label=f"APP-{app.app_id}", success="Registered: title NFT minted",
            by=request.user.profile, target=f"APP-{app.app_id}", note=request.data.get("note"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )   # simulates now; raises ChainRevert(reason) → 422 and writes RevertLog; else queues signer.send
        return intent_response(intent, wait=request.query_params.get("wait") == "true",
                               then=lambda: ParcelDetailSerializer(app.parcel, context=ctx(request)).data)
```

Citizen side uses `chain.prepare(from_address=profile.wallet_address, …)`, which simulates with `{"from": wallet}`, estimates gas ×1.2, and stores the unsigned tx in the intent.

## 16. Frontend migration map

Screens keep calling `landchain.*` and reading `useChain()` / `useMe()`; only `store.ts` changes (rule 5 in PROJECT\_CONTEXT). Replace polling of the chain with TanStack Query against the API (refetch every 3 s, or Supabase Realtime later).

| Today (frontend) | Becomes |
| --- | --- |
| `loadChainState()` in `chain/snapshot.ts` | `GET /parcels`, `/stats`, `/activity`, `/me/notifications`, `/review/queue` as needed per screen |
| `signInAs(id)`, `switchAccount`, `signOut` | Supabase `signInWithPassword` / `signOut`; demo list from `/dev/demo-accounts` |
| `connectWallet()` | MetaMask connect + `/auth/wallet/nonce` + `personal_sign` + `/auth/wallet/verify` |
| `setMyName`, `localNames` | `PATCH /me` |
| `landchain.submitIdentity(hash, c)` | `POST /identity/submit` → sign → `/submitted` |
| `landchain.verifyIdentity(who, ok)` | `POST /identities/{who}/verify|reject?wait=true` |
| `landchain.submitApplication(i)` + `putFile` | `POST /documents` ×N, then `POST /applications` → sign → `/submitted` |
| `landchain.approveApplication`, `rejectApplication` | `POST /applications/{id}/approve|reject?wait=true` |
| `landchain.recordPayment(parcel, kind, amount, receiptNo)` | `POST /parcels/{id}/payments?wait=true` |
| `landchain.requestTransfer(parcel, to)` | `GET /identities/lookup` then `POST /transfers` → sign |
| `landchain.cancelTransfer` | `POST /transfers/{id}/cancel` → sign |
| `landchain.approveTransfer`, `rejectTransfer` | `POST /transfers/{id}/approve|reject?wait=true` |
| `vault.openFile(hash)` | `GET /documents/{sha256}/url?parcel_id=`, open the URL with an `<a target="_blank">` |
| Fingerprint check (local `sha256Hex`) | Keep hashing in the browser; `POST /parcels/{id}/documents/check` |
| `sendEnquiry`, `markEnquiry`, `useEnquiries` | `POST /parcels/{id}/enquiries`, `PATCH /enquiries/{id}`, `GET /me/enquiries` |
| `validateBoundary`, `areaAcres` | Keep for instant feedback; confirm with `POST /parcels/boundary-check` before submit |
| `gasCost(hash)` | `GET /parcels/{id}/receipt` |
| `recordRevert` / `localReverts` | Server `RevertLog`, visible in `/activity` |
| `canSeePrivate`, `shownName` | Server decides; UI uses `visibility`, `viewer.*`, `PersonRef.label` |
| `estimateFee`, `FEE_INFO` | `GET /fees/schedule`, `/fees/estimate` (or keep the static copy) |

Write flow helper for the UI (keeps the existing toasts):

```
async function runIntent(res: { intent: TxIntent }) {
  let it = res.intent;
  const t = toast.loading(`Sending to ${config.chain_name}…`);
  if (it.status === "awaiting_signature") {
    if (config.features.dev_unlocked_signing && isDemoAccount) it = await api.post(`/chain/intents/${it.id}/dev-sign`);
    else try {
      const hash = await window.ethereum.request({ method: "eth_sendTransaction", params: [it.tx] });
      it = await api.post(`/chain/intents/${it.id}/submitted`, { tx_hash: hash });
    } catch (e) { await api.post(`/chain/intents/${it.id}/rejected-by-wallet`, e); throw e; }
  }
  while (!["confirmed", "reverted", "failed", "expired"].includes(it.status)) { await sleep(1000); it = await api.get(`/chain/intents/${it.id}`); }
  it.status === "confirmed"
    ? toast.success(it.success_message, { id: t, description: `Confirmed in block ${it.block} · ${it.tx_hash.slice(0, 10)}…` })
    : toast.error("Transaction reverted", { id: t, description: it.revert_reason ?? it.error });
  queryClient.invalidateQueries();
}
```

## 17. Seed data and tests

Seed (from `landchain-contracts/scripts/seed.js`): 14 parcels around Berekuso (GA-BRK-0001…0014), each with plan number, GPS address, three document fingerprints (Site plan, Indenture, Search report) and fees (search, stamp duty on an illustrative GH¢ 60,000/acre, registration, transfer where relevant). 10 registered; GA-BRK-0001 and GA-BRK-0008 transferred once (GA-BRK-0001: Yaw Boakye → Kofi Mensah); GA-BRK-0006 has a transfer waiting; GA-BRK-0013 and GA-BRK-0014 waiting for registration. Seeded parcels have fingerprints but no files, so `file_available=false`.

Backend acceptance tests (pytest, against Ganache seeded with `npm run setup:local`), mirroring `src/test/chain.e2e.test.ts`:

1. Indexer reproduces the register: GA-BRK-0002 plan number starts with `SER B`, docs are [Site plan, Indenture, Search report], payments [Official search, Stamp duty, First registration]; statuses 0002 registered, 0006 transfer\_pending, 0013 pending; 0001 owner is Kofi, owners [Yaw, Kofi]; a Transfer history row exists.
2. Kofi tries `POST /transfers` for GA-BRK-0002 (Ama's) → 422 "Only the owner can transfer this title", and `/activity?status=Reverted` shows it.
3. Abena (identity officer) calls `POST /applications/APP-14/approve` → 403 "Only the registrar can approve a registration".
4. Full life: Efua links wallet → submits identity (card GHA-700000006-6) → Abena verifies → Efua uploads 3 docs and applies → registrar approve blocked until stamp duty + registration recorded → approve mints GLT → Efua requests transfer to Ama → transfer fee → approve → owners [Efua, Ama].
5. Privacy: anonymous `GET /parcels/GA-BRK-0002` has no names, `fees=null`; `/receipt` 403; Ama sees her name and fees; registrar sees all.
6. Receipt reuse: recording the same receipt number twice → 422 "This receipt has already been recorded".
7. Document access: another citizen gets 403 on `/documents/{sha}/url`; owner and officers get a URL; `/documents/check` works anonymously.
8. Enquiry: anonymous enquiry on GA-BRK-0003 creates an owner notification; the response contains no owner data; the owner can mark it answered; a 6th enquiry within an hour from one IP → 429.
9. JWT: expired token → 401 TOKEN\_EXPIRED; HS256 and JWKS both verified; `anon` role token rejected.
10. Indexer resilience: restart Ganache with `chain:fresh` + setup → indexer detects the new chain and rebuilds.

## 18. Open decisions for the team

1. **Citizen signing.** Recommended: prepare + MetaMask (keeps "wallet = identity" and `msg.sender` checks). Alternative: custodial wallets held by the backend per citizen (easier onboarding, but the Lands Commission could act for citizens, which weakens the two-key story). A third option, meta-transactions (ERC-2771), needs contract changes.
2. **Ghana Card handling.** Today only the hash leaves the browser and the officer verifies on trust. Should the backend also keep evidence for the identity officer (an encrypted card photo in `identity-evidence`, or last 4 digits)? It helps real verification but stores personal data.
3. **Per-officer wallets vs shared role wallets.** Shared wallets (this spec) are simpler; per-officer wallets make on-chain `decidedBy` name the individual but need key management per officer.
4. **Can an officer also own land?** The contracts refuse `submitProfile` from officer addresses. Because officers act through role wallets, an officer's personal wallet could be a citizen. Decide whether to allow it.
5. **Who may read enquiries.** Owner only (this spec), or Lands Commission too for abuse handling.
6. **Sync vs async officer actions.** Spec supports both (`?wait=true`). Pick the UI default: wait on Ganache, async on Sepolia.
7. **Not-found vs exists for public ID lookup** (9.3).
8. **Hosting.** Django + Celery on Render/Fly/Railway; Redis on Upstash; Supabase for the rest.

End of spec. Sources: `landchain-web/src/lib/landchain/{store,types,engine,privacy,fees,vault,enquiries,queue,geo}.ts`, `chain/{client,snapshot,config,gas}.ts`, all routes and `components/lc/*`; `landchain-contracts/contracts/*.sol`, `migrations/1_deploy_land_system.js`, READMEs and PROJECT\_CONTEXT.md.