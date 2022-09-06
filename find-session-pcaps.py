#!/usr/bin/env python3

import argparse

from lib.log import *
from lib.rest import RestApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Find pcaps on all routers, which meet certain criteria')
    parser.add_argument('-c', '--host', required=True,
                        help='Conductor/router hostname')
    parser.add_argument('-u', '--user', required=True,
                        help='Conductor/router username (if no key auth)')
    parser.add_argument('-p', '--password', required=True,
                        help='Conductor/router password (if no key auth)')
    parser.add_argument('-s', '--string', required=True,
                        help='Search string to be contained in file name')
    parser.add_argument('--ignore-routers',
                        help='Comma separated patterns for routers to be ignored')
    parser.add_argument('--show-routers', action='store_true',
                        help='Show routers that have matching pcaps')
    parser.add_argument('--no-download', action='store_true',
                        help='Do not download pcaps')
    parser.add_argument('--selected-routers',
                        help='Comma separated list of routers to be checked')
    return parser.parse_args()


def download_pcap(api, router, node, filename):
    local_filename = '/tmp/{}_{}'.format(router, filename)
    print('local_filename:', local_filename)
    with open(local_filename, 'wb') as fd:
        for chunk in api.download_file(router, node, filename):
            fd.write(chunk)


def main():
    args = parse_arguments()
    params = {
        'host': args.host,
        'user': args.user,
        'password': args.password,
    }
    api = RestApi(**params)
    found_routers = []
    if args.selected_routers:
        routers = args.selected_routers.split(',')
    else:
        routers = api.get_router_names()
    for router in routers:
        if args.ignore_routers:
            ignore = False
            for pattern in args.ignore_routers.split(','):
                if pattern in router:
                    ignore = True
                    break
            if ignore:
                continue

        for node in api.get_node_names(router):
            location = '/router/{}/node/{}/logs/collapsed'.format(router, node)
            r = api.get(location)
            if r.status_code == 200:
                for file in r.json():
                    if file['type'] == 'pcap' and args.string in file['name']:
                        found_routers.append(router)
                        if args.no_download:
                            break
                        else:
                            download_pcap(api, router, node, file['name'])

    if args.show_routers or args.no_download:
        print('Routers that have matching pcap files:')
        print('\n'.join(found_routers))


if __name__ == '__main__':
    main()
