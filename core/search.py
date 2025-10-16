from meilisearch import Client
from django.conf import settings

def meili():
    return Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
