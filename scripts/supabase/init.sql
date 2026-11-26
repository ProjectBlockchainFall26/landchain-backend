-- Run once on the Supabase project (task A1, spec 5.6) in the SQL editor.
create extension if not exists postgis;
create extension if not exists pgcrypto;
create schema if not exists landchain;
-- Do NOT add `landchain` to API -> Exposed schemas, so the anon key can't read Django tables through PostgREST.
-- Storage: create the private bucket `parcel-documents` (20 MB, application/pdf, image/jpeg, image/png) with no
-- policies for anon or authenticated: only Django (service-role key) touches it.
