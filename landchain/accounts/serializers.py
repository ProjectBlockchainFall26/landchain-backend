"""Me object (spec 8) and officer rows (spec 9.13)."""
from __future__ import annotations

from landchain.chain.encoding import iso
from landchain.core.permissions import chain_identity_status


def identity_block(profile) -> dict:
    from landchain.chain.models import TxIntent
    from landchain.registry.models import ChainIdentity
    ci = ChainIdentity.objects.filter(address=profile.wallet_address).first() if profile.wallet_address else None
    pending = TxIntent.objects.filter(
        created_by=profile, function="submitProfile",
        status__in=["awaiting_signature", "submitted", "mined"]).order_by("-created_at").first()
    return {"status": ci.status_name if ci else "none",
            "citizenship": (("citizen" if ci.citizen else "non-citizen") if ci and ci.status else None),
            "card_hash": ci.card_hash if ci and ci.status else None,
            "updated_at": iso(ci.updated_at) if ci else None,
            "pending_intent": pending.id if pending else None}


def me_obj(profile) -> dict:
    from landchain.enquiries.models import Enquiry
    from landchain.notifications.service import unread_for
    from landchain.registry.selectors import parcels_owned_by
    from landchain.registry.views_review import counts_for
    status = chain_identity_status(profile)
    citizen_wallet = bool(profile.wallet_address and not profile.is_officer)
    verified = citizen_wallet and status == "verified"
    return {
        "user_id": str(profile.supabase_user_id), "email": profile.email, "phone": profile.phone,
        "full_name": profile.full_name, "wallet_address": profile.wallet_address, "public_id": profile.public_id,
        "kind": profile.kind, "roles": profile.role_labels,
        "identity": identity_block(profile),
        "capabilities": {
            "can_link_wallet": not profile.wallet_address and not profile.is_officer,
            "can_submit_identity": citizen_wallet and status in ("none", "rejected"),
            "can_register_land": verified, "can_request_transfer": verified,
            "can_review_identities": profile.is_id_officer, "can_review_registrations": profile.is_registrar,
            "can_record_fees": profile.is_registrar, "is_admin": profile.is_admin,
        },
        "counts": {
            "unread_notifications": unread_for(profile).count(),
            "new_enquiries": Enquiry.objects.filter(to_public_id=profile.public_id, status="new").count()
            if profile.public_id else 0,
            "parcels_owned": parcels_owned_by(profile.public_id).count() if profile.public_id else 0,
            "queue_items": counts_for(profile)["actionable"] if profile.is_officer else 0,
        },
        "notify": {"email": profile.notify_email, "sms": profile.notify_sms},
    }


def officer_row(profile) -> dict:
    return {"user_id": str(profile.supabase_user_id), "name": profile.full_name, "email": profile.email,
            "roles": list(profile.roles), "since": iso(profile.updated_at)}
