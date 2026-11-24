"""Models for `accounts`. Owner: Person A. Spec section 7.1 (field names frozen in J1)."""
import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

OFFICER_ROLES = ("registrar", "id_officer")
ALL_ROLES = ("registrar", "id_officer", "admin")
ROLE_LABELS = {"registrar": "Registrar", "id_officer": "Identity officer", "admin": "Admin"}


class Profile(models.Model):
    """One per Supabase user (JWT sub). Names and contacts live here, never on chain."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supabase_user_id = models.UUIDField(unique=True)
    email = models.EmailField(max_length=254, null=True, blank=True)       # stored lowercase (citext in the spec)
    phone = models.CharField(max_length=20, null=True, blank=True)        # E.164
    full_name = models.CharField(max_length=120, blank=True, default="")
    wallet_address = models.CharField(max_length=42, unique=True, null=True, blank=True)   # lowercase
    public_id = models.CharField(max_length=11, unique=True, null=True, blank=True)        # GH-xxxxxxxx
    wallet_linked_at = models.DateTimeField(null=True, blank=True)
    roles = ArrayField(models.CharField(max_length=20), default=list, blank=True)      # registrar | id_officer | admin
    notify_email = models.BooleanField(default=True)
    notify_sms = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profile"
        indexes = [models.Index(fields=["email"])]

    def __str__(self):
        return self.full_name or self.email or str(self.supabase_user_id)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.wallet_address:
            self.wallet_address = self.wallet_address.lower()
        super().save(*args, **kwargs)

    # ---- derived (spec 5.5)
    @property
    def is_officer(self) -> bool:
        return any(r in OFFICER_ROLES for r in (self.roles or []))

    @property
    def is_registrar(self) -> bool:
        return "registrar" in (self.roles or [])

    @property
    def is_id_officer(self) -> bool:
        return "id_officer" in (self.roles or [])

    @property
    def is_admin(self) -> bool:
        return "admin" in (self.roles or [])

    @property
    def kind(self) -> str:
        return "officer" if self.is_officer else "citizen"

    @property
    def role_labels(self) -> list[str]:
        labels = [ROLE_LABELS[r] for r in ("registrar", "id_officer") if r in (self.roles or [])]
        if not labels:
            labels = ["Citizen"]
        if self.is_admin:
            labels.append("Admin")
        return labels


class WalletNonce(models.Model):
    """Sign-In with Ethereum nonce: the exact EIP-4361 message issued, single use, 10 minute TTL. Task A4."""

    nonce = models.CharField(max_length=32, primary_key=True)
    address = models.CharField(max_length=42)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="wallet_nonces")
    message = models.TextField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "wallet_nonce"
