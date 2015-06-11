import datetime
import mimetypes
import optparse
import os

from azure import WindowsAzureMissingResourceError
from azure.storage import BlobService

from azurite.settings import AZURITE

from django.conf import settings
from django.core.management.base import BaseCommand

class BaseSynchronizeCommand(BaseCommand):
    option_list = BaseCommand.option_list + (
        optparse.make_option('-w', '--wipe',
            action='store_true', dest='wipe', default=False,
            help="Wipes out entire contents of container first."),
        optparse.make_option('-t', '--test-run',
            action='store_true', dest='test_run', default=False,
            help="Performs a test run of the sync."),
        optparse.make_option('-c', '--container',
            dest='container', help="Override target container."),
    )

    CONTAINER_KEY = None

    # settings from azurite.settings
    ACCOUNT_NAME     = AZURITE['ACCOUNT_NAME']
    ACCOUNT_KEY      = AZURITE['ACCOUNT_KEY']

    _container = None

    @property
    def container(self):
        if self._container is None:
            container = AZURITE[self.CONTAINER_KEY]
        else:
            container = self._container

        return container

    @container.setter
    def container(self, value):
        self._container = value

    purge_missing_files = False

    # paths
    DIRECTORY = None
    URL = None

    local_object_names = []
    create_count = 0
    upload_count = 0
    update_count = 0
    skip_count = 0
    delete_count = 0
    service = None

    _url = None
    _directory = None

    def handle(self, *args, **options):
        self.wipe = options.get('wipe')
        self.test_run = options.get('test_run')
        self.verbosity = int(options.get('verbosity'))
        if hasattr(options, 'container'):
            self.container = options.get('container')

        self._directory = self.DIRECTORY

        if not self.DIRECTORY.endswith('/'):
            self._directory += os.path.sep

        self._url = self.URL.lstrip('/')

        self.sync_files()

    def sync_files(self):
        self.service = BlobService(account_name=self.ACCOUNT_NAME,
                                   account_key=self.ACCOUNT_KEY)

        try:
            self.service.get_container_properties(self.container)
        except WindowsAzureMissingResourceError:
            self.service.create_container(self.container,
                x_ms_blob_public_access='blob')

        self.service.set_container_acl(self.container, x_ms_blob_public_access='blob')

        # if -w option is provided, wipe out the contents of the container
        if self.wipe:
            blob_count = len(self.service.list_blobs(self.container))

            if self.test_run:
                print "Wipe would delete %d objects." % blob_count
            else:
                print "Deleting %d objects..." % blob_count
                for blob in self.service.list_blobs(self.container):
                    self.service.delete_blob(self.container, blob.name)

        # walk through the directory, creating or updating files on the cloud
        os.path.walk(self._directory, self.upload_files, "foo")

        if self.purge_missing_files:
            # remove any files on remote that don't exist locally
            self.delete_files()

        # print out the final tally to the cmd line
        self.update_count = self.upload_count - self.create_count

        print
        if self.test_run:
            print "Test run complete with the following results:"
        print "Skipped %d. Created %d. Updated %d. Deleted %d." % (
            self.skip_count, self.create_count, self.update_count, self.delete_count)

    def upload_files(self, arg, dirname, names):
        # upload or skip items
        for item in names:
            file_path = os.path.join(dirname, item)
            if os.path.isdir(file_path):
                continue # Don't try to upload directories

            object_name = self._url + file_path.split(self._directory)[1]
            self.local_object_names.append(object_name)

            try:
                properties = self.service.get_blob_properties(self.container,
                    object_name)
            except WindowsAzureMissingResourceError:
                properties = {}
                self.create_count += 1

            cloud_datetime = None
            if 'last-modified' in properties:
                cloud_datetime = (properties['last-modified'] and
                                  datetime.datetime.strptime(
                                    properties['last-modified'],
                                    "%a, %d %b %Y %H:%M:%S %Z"
                                  ) or None)

            local_datetime = datetime.datetime.utcfromtimestamp(
                                               os.stat(file_path).st_mtime)

            if cloud_datetime and local_datetime < cloud_datetime:
                self.skip_count += 1
                if self.verbosity > 1:
                    print "Skipped %s: not modified." % object_name
                continue

            if not self.test_run:
                file_contents = open(file_path, 'r').read()
                content_type, encoding = mimetypes.guess_type(file_path)
                self.service.put_blob(self.container, object_name, file_contents,
                    x_ms_blob_type='BlockBlob', x_ms_blob_content_type=content_type,
                    content_encoding=encoding)
                # sync_headers(cloud_obj)
            self.upload_count += 1
            if self.verbosity > 1:
                print "Uploaded", object_name

    def delete_files(self):
        # remove any objects in the container that don't exist locally
        for blob in self.service.list_blobs(self.container):
            if blob.name not in self.local_object_names:
                self.delete_count += 1
                if self.verbosity > 1:
                    print "Deleted %s" % blob.name
                if not self.test_run:
                    self.service.delete_blob(self.container, blob.name)
