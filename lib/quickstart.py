from base64 import b64decode, b64encode
import gzip
import json

class Quickstart(object):
    """Class to create/manipulate quickstart files."""
    xml_config = ''
    asset_id = None
    router_name = 'generic-quickstart-router'

    def __init__(self, filename=None):
        """Create a quickstart object from file or from scratch."""
        pass

    def update_xml_config(self, filename):
        with open(filename) as fd:
            self.xml_config = fd.read()

    def read_config_export(self, filename):
        with gzip.open(filename, mode='rt') as fd:
            self.xml_config = fd.read()

    def to_bytes(self):
        quickstart = {
            'n': self.router_name,
            'a': self.asset_id,
            'c': b64encode(gzip.compress(bytes(self.xml_config, 'ascii'))).decode('ascii'),
        }
        return bytes(json.dumps(quickstart), 'ascii')
