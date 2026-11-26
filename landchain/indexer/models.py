"""Indexer bookkeeping (task C2, spec 7.2). Written only by the indexer."""
from django.db import models


class IndexerCursor(models.Model):
    chain_id = models.IntegerField(primary_key=True)
    title_registry_address = models.CharField(max_length=42)
    last_block = models.BigIntegerField(default=-1)           # -1 = nothing indexed yet
    last_block_hash = models.CharField(max_length=66, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "indexer_cursor"


class ChainBlock(models.Model):
    chain_id = models.IntegerField()
    number = models.BigIntegerField()
    hash = models.CharField(max_length=66)
    timestamp = models.DateTimeField()

    class Meta:
        db_table = "chain_block"
        constraints = [models.UniqueConstraint(fields=["chain_id", "number"], name="uniq_chain_block")]


class ChainEvent(models.Model):
    chain_id = models.IntegerField()
    tx_hash = models.CharField(max_length=66)
    log_index = models.IntegerField()
    block_number = models.BigIntegerField(db_index=True)
    contract = models.CharField(max_length=30)
    event = models.CharField(max_length=40)
    args = models.JSONField(default=dict)

    class Meta:
        db_table = "chain_event"
        ordering = ["block_number", "log_index"]
        constraints = [models.UniqueConstraint(fields=["chain_id", "tx_hash", "log_index"], name="uniq_chain_event")]


class ChainTx(models.Model):
    """One row per mined contract call: the activity log (with RevertLog for refusals)."""

    tx_hash = models.CharField(max_length=66, primary_key=True)
    chain_id = models.IntegerField()
    from_address = models.CharField(max_length=42, db_index=True)
    from_public_id = models.CharField(max_length=11, db_index=True, blank=True, default="")
    to_address = models.CharField(max_length=42)
    contract = models.CharField(max_length=30, db_index=True)
    function = models.CharField(max_length=40)
    args_label = models.CharField(max_length=300, blank=True, default="")
    record_ids = models.JSONField(default=list)              # TitleRegistry records the call touched
    block_number = models.BigIntegerField(db_index=True)
    tx_index = models.IntegerField(default=0)
    at = models.DateTimeField(null=True, db_index=True)
    status = models.CharField(max_length=10, default="Success")
    gas_used = models.BigIntegerField(default=0)
    effective_gas_price_wei = models.DecimalField(max_digits=40, decimal_places=0, default=0)
    cost_wei = models.DecimalField(max_digits=40, decimal_places=0, default=0)

    class Meta:
        db_table = "chain_tx"
        ordering = ["-block_number", "-tx_index"]
