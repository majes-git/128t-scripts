#!/usr/bin/env python3

import argparse
import json
from ipaddress import ip_network
from requests.exceptions import ConnectionError

from lib.log import *
from lib.rest import RestGraphqlApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Show overlapping ip prefixes in 128T services')
    parser.add_argument('-c', '--host',
                        help='Conductor/router hostname')
    parser.add_argument('-u', '--user',
                        help='Conductor/router username (if no key auth)')
    parser.add_argument('-p', '--password',
                        help='Conductor/router password (if no key auth)')
    parser.add_argument('--config-store', default='running', choices=['running', 'candidate'],
                        help='Config store to be used (running/candidate)')
    parser.add_argument('--dump-json', action='store_true',
                        help='Write config dump to json file "t128-show-ip-prefix-conflicts.json"')
    return parser.parse_args()


def broadcast_address(network):
    try:
        return ip_network(network).broadcast_address
    except ValueError:
        # warn(f'Invalid network address: {network}')
        return None

def have_conflict(ref_address, comp_address):
    ref_broadcast = broadcast_address(ref_address)
    comp_broadcast = broadcast_address(comp_address)
    if ref_broadcast and comp_broadcast:
        return ref_broadcast == comp_broadcast
    return False


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestGraphqlApi(**params)

    try:
        config = api.get(f'/config/{args.config_store}').json()

        if args.dump_json:
            with open('t128-show-ip-prefix-conflicts.json', 'w') as fd:
                json.dump(config, fd)

        authority = config.get('authority', {})
        services = authority.get('service')

        if not services:
            error('Could not find any service to be checked.')

        for service in services:
            name = service.get('name')
            addresses = service.get('address')

            # sanity checks
            if service.get('generated'):
                continue

            if not addresses:
                if service.get('applicationType') in ('template', 'dhcp-relay'):
                    # templates and dhcp-relay don't have an address
                    continue
                if service.get('applicationName'):
                    # services with application name shouldn't have an address
                    continue
                if service.get('domainName'):
                    # services with domain name shouldn't have an address
                    continue

                error('Service has got no addresses:', name)

            conflicting_addresses = []
            for ref_address in addresses:
                next_index = addresses.index(ref_address) + 1
                if next_index >= len(addresses):
                    break
                for comp_address in addresses[next_index:]:
                    if have_conflict(ref_address, comp_address):
                        conflicting_addresses.append((ref_address, comp_address))

            if conflicting_addresses:
                warn(f'Service "{name}" has conflicting addresses:')
                for conflict in conflicting_addresses:
                    print('* {} and {}'.format(*conflict))

    except ConnectionError:
        error('Could not connect to conductor. Wrong username/password?')


if __name__ == '__main__':
    main()
