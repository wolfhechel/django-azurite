from azure.storage._common_models import WindowsAzureData


class CorsRule(WindowsAzureData):

    def _wildcard_if_none_or_comma_list(self, val):
        if val is None:
            ret = '*'
        else:
            ret = ','.join(list(val))

        return ret

    default_methods = ['GET']

    def __init__(self, origins=None, allowed_headers=None, exposed_headers=None, methods=None):
        if methods is None:
            methods = self.default_methods

        self.allowed_methods = self._wildcard_if_none_or_comma_list(methods)
        self.allowed_origins = self._wildcard_if_none_or_comma_list(origins)
        self.allowed_headers = self._wildcard_if_none_or_comma_list(allowed_headers)
        self.exposed_headers = self._wildcard_if_none_or_comma_list(exposed_headers)
        self.max_age_in_seconds = 200


class Cors(WindowsAzureData):

    def __init__(self):
        self.cors_rules = list()

    def add_cors_rule(self, cors_rule):
        self.cors_rules.append(cors_rule)


class StorageServiceProperties(WindowsAzureData):

    def __init__(self):
        self.cors = Cors()

    def add_cors_origin(self, *args, **kwargs):
        self.cors.add_cors_rule(CorsRule(*args, **kwargs))