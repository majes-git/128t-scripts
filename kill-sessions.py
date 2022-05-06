#!/usr/bin/env python3

import argparse
import subprocess
import time
import sys
from requests import ConnectTimeout, ReadTimeout
from tabulate import tabulate

from lib.log import *
from lib.rest import RestApi

DAEMONS = ['mars']
KILL_COMMAND = ['pkill', '-x']


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Kill sessions on 128T/SSR router, which met certain criteria')
    parser.add_argument('--dry-run', action='store_true',
                        help='show sessions only - no kill')
    parser.add_argument('--quiet', action='store_true',
                        help='no output')
    parser.add_argument('--port', help='source/destination port', type=int)
    parser.add_argument('--kill-daemons', type=float,
                        help='kill related daemons if api does not respond with X seconds')
    parser.add_argument('--same-interface', action='store_true',
                        help='Same ingress/egress interface')
    return parser.parse_args()


def get_filtered_sessions(api, args):
    json = {
        'query': '''
            {
              allNodes {
                nodes {
                  flowEntries(first: 100000) {
                    nodes {
                      sessionUuid
                      serviceName
                      sourceIp
                      sourcePort
                      destIp
                      destPort
                      encrypted
                      networkInterfaceName
                    }
                  }
                }
              }
            }
        '''
    }
    kwargs = {}
    timeout = args.kill_daemons
    if timeout:
        print('Timeout:', timeout)
        kwargs['timeout'] = timeout
    try:
        request = api.post('/graphql', json, **kwargs)
    except (ConnectTimeout, ReadTimeout):
        print('Getting sessions took too long. Killing daemons:', *DAEMONS)
        if not args.dry_run:
            for daemon in DAEMONS:
                subprocess.call(KILL_COMMAND + [daemon])
                time.sleep(1)
                subprocess.call(KILL_COMMAND + ['-9', daemon])
        sys.exit(1)

    sessions = {}
    filtered_sessions = {}
    retrieval_failed = False
    if request.status_code == 200:
        # aggregate flows into sessions
        try:
            for flow in request.json()['data']['allNodes']['nodes'][0]['flowEntries']['nodes']:
                id = flow['sessionUuid']
                if id not in sessions:
                    sessions[id] = []
                sessions[id].append(flow)
        except TypeError:
            retrieval_failed = True

        if not args.quiet:
            print('Total number of sessions:', len(sessions))

        for flows in sessions.values():
            interfaces = [flow['networkInterfaceName'] for flow in flows]
            for flow in flows:
                if args.port:
                    if args.port not in (flow['sourcePort'], flow['destPort']):
                        # no match - ignore this flow
                        continue
                if args.same_interface:
                    if len(set(interfaces)) != 1:
                        # no match - ignore this flow
                        continue
                # all criteria are met - add session to filtered_sessions
                id = flow['sessionUuid']
                filtered_sessions[id] = sessions[id]
                break

        if not args.quiet:
            print('Matching number of sessions:', len(filtered_sessions))
        return filtered_sessions

    else:
        retrieval_failed = True

    if retrieval_failed:
        error('Retrieving sessions table has failed: {} ({})'.format(
              request.text, request.status_code))

def main():
    args = parse_arguments()
    api = RestApi()
    filtered_sessions = get_filtered_sessions(api, args)

    if filtered_sessions:
        dataset = [e for s in filtered_sessions.values() for e in s]
        header = dataset[0].keys()
        rows =  [x.values() for x in dataset]
        if not args.quiet:
            if not args.dry_run:
                print('The following sessions will be deleted:')
            print(tabulate(rows, header, tablefmt='rst'))

        if not args.dry_run:
            for id in filtered_sessions.keys():
                location = '/router/{}/node/{}/traffic/session?sessionId={}'.format(
                    api.get_router_name(),
                    api.get_node_name(),
                    id,
                )
                api.delete(location)


if __name__ == '__main__':
    main()
