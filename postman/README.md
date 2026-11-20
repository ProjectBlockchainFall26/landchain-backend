# Postman

- `LandChain.postman_collection.json`: all 58 endpoints from `docs/api-spec.md` section 9, each with the request body
  and the example response from the spec (open a request → Examples).
- `LandChain-Local.postman_environment.json` / `LandChain-Staging.postman_environment.json`.

## Use it
1. Postman → Import → select the three files. Pick the **LandChain Local** environment.
2. Fill `supabaseUrl`, `supabaseAnonKey`, `email`, `password` (ask the A1 owner).
3. Run **0. Sign in (Supabase) → Sign in with email + password**. It saves `accessToken`; every request sends it as a Bearer token.
4. Without Supabase (local only): enable the `X-Dev-User` header on a request (needs `DEV_AUTH=true`, task A2).
5. Routes that are not built yet answer `501 NOT_IMPLEMENTED` with the owner task ID.

## Keep it in sync
When you build an endpoint, update its request in the collection if anything changed, add a test script
(status code + key fields), export and commit. Task D1 runs the collection in CI with newman.
