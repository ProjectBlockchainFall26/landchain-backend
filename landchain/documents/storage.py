"""Document storage (task D2): Supabase Storage private bucket, keyed by the SHA-256 fingerprint.

When SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set, files go to the `parcel-documents` bucket and are
opened with signed URLs that expire in 60 seconds. Without them (local development), files are kept under
VAULT_LOCAL_DIR and opened through a Django URL signed the same way (`/api/v1/dev/vault/<token>`).
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core import signing

SIGNED_URL_TTL = 60


def using_supabase() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _bucket():
    from supabase import create_client
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY).storage.from_(
        settings.SUPABASE_DOCS_BUCKET)


def _local(path: str) -> Path:
    root = Path(settings.VAULT_LOCAL_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root / path


def exists(path: str) -> bool:
    if using_supabase():
        try:
            return bool(_bucket().exists(path))
        except Exception:
            return False
    return _local(path).exists()


def put(path: str, data: bytes, mime: str) -> None:
    """Content-addressed: the same fingerprint is stored once."""
    if exists(path):
        return
    if using_supabase():
        _bucket().upload(path, data, {"content-type": mime, "upsert": "true"})
    else:
        _local(path).write_bytes(data)


def delete(path: str) -> None:
    if using_supabase():
        _bucket().remove([path])
    else:
        p = _local(path)
        if p.exists():
            p.unlink()


def signed_url(path: str, *, name: str, mime: str, request=None) -> str:
    if using_supabase():
        res = _bucket().create_signed_url(path, SIGNED_URL_TTL, {"download": name})
        return res.get("signedURL") or res.get("signedUrl") or res["signed_url"]
    token = signing.dumps({"p": path, "n": name, "m": mime}, salt="vault")
    rel = f"/api/v1/dev/vault/{token}"
    return request.build_absolute_uri(rel) if request is not None else rel


def read_signed(token: str) -> tuple[bytes, str, str]:
    """Local backend only: verify a token from signed_url() and return (bytes, name, mime)."""
    data = signing.loads(token, salt="vault", max_age=SIGNED_URL_TTL)
    return _local(data["p"]).read_bytes(), data["n"], data["m"]
