import os.path

from . import BaseSynchronizeCommand, settings


class Command(BaseSynchronizeCommand):
    help = "Synchronizes media files to cloud files."

    CONTAINER_KEY = 'CONTAINER'

    # paths
    DIRECTORY = os.path.abspath(settings.MEDIA_ROOT)
    URL = settings.MEDIA_URL

    purge_missing_files = False
