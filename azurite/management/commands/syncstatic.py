import os.path

from . import BaseSynchronizeCommand, settings


class Command(BaseSynchronizeCommand):
    help = "Synchronizes static media to cloud files."

    CONTAINER_KEY = 'STATIC_CONTAINER'

    # paths
    DIRECTORY = os.path.abspath(settings.STATIC_ROOT)
    URL = settings.STATIC_URL

    purge_missing_files = True
