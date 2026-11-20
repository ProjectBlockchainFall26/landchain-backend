from django.apps import AppConfig


class IndexerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "landchain.indexer"
    label = "indexer"
