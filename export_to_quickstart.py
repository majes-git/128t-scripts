#!/usr/bin/env python3

import argparse

from lib.quickstart import Quickstart


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Convert an export config into quickstart')
    parser.add_argument('-e', '--export', required=True,
                        help='Export config file name')
    parser.add_argument('-q', '--quickstart', required=True,
                        help='Quickstart file name')
    return parser.parse_args()


def main():
    args = parse_arguments()
    quickstart = Quickstart()
    quickstart.read_config_export(args.export)
    with open(args.quickstart, 'wb') as fd:
        fd.write(quickstart.to_bytes())


if __name__ == '__main__':
    main()
