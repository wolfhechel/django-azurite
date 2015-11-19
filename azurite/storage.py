import datetime
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.conf import settings

from .compat import BlobService, WindowsAzureMissingResourceError
from .settings import AZURITE
from . import cors


class AzureStorage(Storage):
    """
    Custom file storage system for Azure
    """
    container = AZURITE['CONTAINER']
    account_name = AZURITE['ACCOUNT_NAME']
    account_key = AZURITE['ACCOUNT_KEY']
    cdn_host = AZURITE['CDN_HOST']
    use_ssl = AZURITE['USE_SSL']

    def __init__(self, account_name=None, account_key=None, use_ssl=None):
        if account_name is not None:
            self.account_name = account_name

        if account_key is not None:
            self.account_key = account_key

        if use_ssl is not None:
            self.use_ssl = use_ssl

        self._create_container()

    def _create_container(self):
        self._get_service().create_container(
            container_name=self.container,
            x_ms_blob_public_access='blob'
        )

    def __getstate__(self):
        return dict(account_name=self.account_name,
            account_key=self.account_key, container=self.container,
            cdn_host=self.cdn_host, use_ssl=self.use_ssl)

    def _get_protocol(self):
        if self.use_ssl:
            return 'https'
        return 'http'

    def _get_service(self):
        if not hasattr(self, '_blob_service'):
            self._blob_service = BlobService(account_name=self.account_name,
                account_key=self.account_key, protocol=self._get_protocol())

        return self._blob_service

    def _get_container_url(self):
        if self.cdn_host is not None:
            return self.cdn_host

        if not hasattr(self, '_container_url'):
            self._container_url =  '%s://%s/%s' % (self._get_protocol(),
                self._get_service()._get_host(), self.container)

        return self._container_url

    def _get_properties(self, name):
        return self._get_service().get_blob_properties(self.container,
                name)

    def _get_file_obj(self, name):
        """
        Helper function to get retrieve the requested Cloud Files Object.
        """
        return self._get_service().get_blob(self.container, name)

    def _open(self, name, mode='rb'):
        """
        Return the AzureStorageFile.
        """
        contents = self._get_service().get_blob(self.container, name)
        return ContentFile(contents)

    def _save(self, name, content):
        """
        Use the Azure Storage service to write ``content`` to a remote file
        (called ``name``).
        """
        content.open()
        content_type = None
        if hasattr(content.file, 'content_type'):
            content_type = content.file.content_type
        else:
            content_type, _ = mimetypes.guess_type(name)

        if hasattr(content, 'chunks'):
            content_str = ''.join(chunk for chunk in content.chunks())
        else:
            content_str = content.read()
        self._get_service().put_blob(self.container, name, content_str,
            'BlockBlob', x_ms_blob_content_type=content_type)
        content.close()

        # Avoid the filesize cache trying to access the file again after close.
        content._size = len(content_str)

        return name

    def listdir(self, path):
        """
        Lists the contents of the specified path, returning a 2-tuple of lists;
        the first item being directories, the second item being files.
        """
        files = []
        if path and not path.endswith('/'):
            path = '%s/' % path
        path_len = len(path)
        blob_list = self._get_service().list_blobs(self.container, prefix=path)
        for name in blob_list:
            files.append(name[path_len:])
        return ([], files)

    def exists(self, name):
        """
        Returns True if a file referenced by the given name already exists in
        the storage system, or False if the name is available for a new file.
        """
        try:
            self._get_properties(name)
            return True
        except WindowsAzureMissingResourceError:
            return False

    def delete(self, name):
        """
        Deletes the file referenced by name.
        """
        try:
            self._get_service().delete_blob(self.container, name)
        except WindowsAzureMissingResourceError:
            pass

    def size(self, name):
        """
        Returns the total size, in bytes, of the file referenced by name.
        """
        try:
            properties = self._get_properties(name)
            return int(properties['content-length'])
        except WindowsAzureMissingResourceError:
            pass

    def url(self, name):
        """
        Returns the URL where the contents of the file referenced by name can
        be accessed.
        """
        return '%s/%s' % (self._get_container_url(), name)

    def modified_time(self, name):
        """
        Returns a datetime object containing the last modified time.
        """
        try:
            properties = self._get_properties(name)
            return datetime.datetime.strptime(properties['last-modified'],
                '%a, %d %b %Y %H:%M:%S %Z')
        except WindowsAzureMissingResourceError:
            pass


class AzureStaticStorage(AzureStorage):
    """
    Subclasses AzureStorage to automatically set the container to the one
    specified in AZURITE['STATIC_CONTAINER']. This provides the ability to
    specify a separate storage backend for Django's collectstatic command.

    To use, make sure AZURITE['STATIC_CONTAINER'] is set to something other
    than AZURITE['CONTAINER']. Then, tell Django's staticfiles app by setting
    STATICFILES_STORAGE = 'azurite.storage.AzureStaticStorage'.
    """
    container = AZURITE['STATIC_CONTAINER']

    def post_process(self, paths, dry_run=False, **options):
        if not dry_run:
            self.update_cors_headers()

        return [(path, path, False) for path in paths.iterkeys()]

    def update_cors_headers(self):
        storage_service_properties = cors.StorageServiceProperties()

        if AZURITE.get('USE_CORS', False):
            if settings.DEBUG:
                origins = None  # Will default to allow host
            else:
                origins = []

                for allowed_host in settings.ALLOWED_HOSTS:
                    origins.extend(['%s://%s' % (scheme, allowed_host)
                                    for scheme in ('http', 'https')])

            storage_service_properties.add_cors_origin(origins=origins)

        self._get_service().set_blob_service_properties(storage_service_properties)