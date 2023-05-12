from base64 import b64decode, b64encode
import gzip
import json
import xml.etree.ElementTree as ET


class Quickstart(object):
    """Class to create/manipulate quickstart files."""
    xml_config = ''
    asset_id = None
    router_name = 'generic-quickstart-router'
    node_name = 'node'

    def __init__(self, filename=None):
        """Create a quickstart object from file or from scratch."""
        pass

    def update_xml_config(self, filename):
        with open(filename) as fd:
            self.xml_config = fd.read()

    def read_config_export(self, filename):
        with gzip.open(filename, mode='rt') as fd:
            self.xml_config = fd.read()

            ns = {'authy': 'http://128technology.com/t128/config/authority-config',
                  'sys': 'http://128technology.com/t128/config/system-config'}
            root = ET.fromstring(self.xml_config)
            for authority in root.findall('authy:authority', ns):
                for router in authority.findall('authy:router', ns):
                    name = router.find('authy:name', ns)
                    self.router_name = name.text
                    for node in router.findall('sys:node', ns):
                        name = node.find('sys:name', ns)
                        self.node_name = name.text

    def to_bytes(self):
        quickstart = {
            'n': self.node_name,
            'a': self.asset_id,
            'c': b64encode(gzip.compress(bytes(self.xml_config, 'ascii'))).decode('ascii'),
        }
        return bytes(json.dumps(quickstart), 'ascii')
