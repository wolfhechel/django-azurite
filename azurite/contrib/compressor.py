from django.core.files.storage import get_storage_class

from ..storage import AzureStaticStorage


class CachedAzureStaticStorage(AzureStaticStorage):
    """
    S3 storage backend that saves the files locally, too.
    """
    def __init__(self, *args, **kwargs):
        super(CachedAzureStaticStorage, self).__init__(*args, **kwargs)

        self.local_storage = get_storage_class("compressor.storage.CompressorFileStorage")()

    def save(self, name, content):
        name = super(CachedAzureStaticStorage, self).save(name, content)
        self.local_storage._save(name, content)

        return name