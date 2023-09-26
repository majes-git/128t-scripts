#!/usr/bin/env python3

import argparse

from lib.log import *
from lib.rest import RestGraphqlApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Adjust transmit cap of an SSR router node interface')
    parser.add_argument('-c', '--host',
                        help='Conductor/router hostname')
    parser.add_argument('-u', '--user',
                        help='Conductor/router username (if no key auth)')
    parser.add_argument('-p', '--password',
                        help='Conductor/router password (if no key auth)')
    parser.add_argument('-r', '--router', required=True,
                        help='Router to be adjusted')
    parser.add_argument('-n', '--node', required=True,
                        help='Node to be adjusted')
    parser.add_argument('-i', '--interface', required=True,
                        help='Interface to be adjusted')
    parser.add_argument('-t', '--transmit-cap', required=True,
                        help='Transmit cap to be set')
    parser.add_argument('--commit', action='store_true',
                        help='Commit config after change')
    return parser.parse_args()


def set_transmit_cap(api, router, node, interface, transmit_cap):
    url = f'/config/candidate/authority/router/{router}/node/{node}/device-interface/{interface}/traffic-engineering'
    json = {
        'enabled': True,
        'transmit-cap': transmit_cap,
    }
    request = api.patch(url, json)
    if request.status_code != 200:
        error('Could not set transmit cap')


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestGraphqlApi(**params)

    router = args.router
    node = args.node
    interface = args.interface
    transmit_cap = args.transmit_cap

    routers = api.get_router_names()
    if router not in routers:
        error('Cannot find router:', router)

    nodes = api.get_node_names(router)
    if node not in nodes:
        error('Cannot find node:', node)

    interfaces = [i['name'] for i in api.get_device_interfaces(router, node)]
    if interface not in interfaces:
        error('Cannot find interface:', interface)

    set_transmit_cap(api, router, node, interface, transmit_cap)

    if args.commit:
        request = api.commit()
        if request.status_code != 200:
            error('Could not commit config:', request.text)


if __name__ == '__main__':
    main()
