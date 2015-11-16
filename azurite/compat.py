try:
    from azure.storage import BlobService
    from azure import WindowsAzureMissingResourceError
except ImportError:
    from azure.storage.blob import BlobService
    from azure.common import AzureMissingResourceHttpError as WindowsAzureMissingResourceError


__all__ = [
    'BlobService',
    'WindowsAzureMissingResourceError'
]