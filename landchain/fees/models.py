"""Models for `fees`. Payment is a projection (C2, written by the indexer); PaymentReceipt is off chain (D4)."""
from django.db import models

from landchain.chain.encoding import FEE_KINDS


class Payment(models.Model):
    """FeeLedger.getPayment(id)."""

    payment_id = models.IntegerField(primary_key=True)
    record_id = models.IntegerField(db_index=True)
    kind = models.SmallIntegerField()
    amount_pesewas = models.BigIntegerField()
    receipt_hash = models.CharField(max_length=66)
    payer_address = models.CharField(max_length=42)
    payer_public_id = models.CharField(max_length=11, blank=True, default="")
    recorded_by = models.CharField(max_length=42)
    at = models.DateTimeField(null=True)
    transfer_id = models.IntegerField(null=True, blank=True)
    block_number = models.BigIntegerField(default=0)
    tx_hash = models.CharField(max_length=66, blank=True, default="")

    class Meta:
        db_table = "payment"
        ordering = ["payment_id"]

    @property
    def kind_name(self) -> str:
        return FEE_KINDS[self.kind]


class PaymentReceipt(models.Model):
    """Private side of a payment: the plain receipt number and the consideration (officers only)."""

    intent = models.OneToOneField("chain.TxIntent", on_delete=models.CASCADE, related_name="receipt")
    payment_id = models.IntegerField(null=True, blank=True, unique=True)   # set once the indexer sees it
    receipt_hash = models.CharField(max_length=66, db_index=True)
    receipt_no = models.CharField(max_length=64)
    consideration_ghs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_receipt"
