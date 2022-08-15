#!/usr/bin/env python3

import argparse
import subprocess
import time
import sys
from requests import ConnectTimeout, ReadTimeout
from tabulate import tabulate

from lib.log import *
from lib.rest import RestApi


IKE_PORT = 500


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Kill sessions on 128T/SSR router, when ESP and IKE paths differ')
    parser.add_argument('--timeout', type=int,
                        help='wait X seconds on API calls')
    parser.add_argument('--dry-run', action='store_true',
                        help='show sessions only - no kill')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quiet', action='store_true',
                        help='no output')
    group.add_argument('--print-sessions', action='store_true',
                        help='show session details')
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
                      protocol
                      sourceIp
                      sourcePort
                      destIp
                      destPort
                      networkInterfaceName
                      forward
                    }
                  }
                }
              }
            }
        '''
    }
    try:
        request = api.post('/graphql', json, timeout=args.timeout)
    except (ConnectTimeout, ReadTimeout):
        error('Getting sessions took too long.')

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

        info('Total number of sessions:', len(sessions))

        # Search IKE sessions
        filtered_sessions = {}
        for flows in sessions.values():
            interfaces = [flow['networkInterfaceName'] for flow in flows]
            for flow in flows:
                if IKE_PORT not in (flow['sourcePort'], flow['destPort']) and \
                   flow['protocol'] != 'ESP':
                        # no match - ignore this flow
                        continue
                if flow['forward']:
                    client = flow['sourceIp']
                else:
                    client = flow['destIp']
                id = flow['sessionUuid']
                if client not in filtered_sessions:
                    filtered_sessions[client] = {}
                filtered_sessions[client][id] = sessions[id]
                break
        return filtered_sessions

    else:
        retrieval_failed = True

    if retrieval_failed:
        error('Retrieving sessions table has failed: {} ({})'.format(
              request.text, request.status_code))


def get_stuck_sessions(filtered_sessions):
    stuck_sessions = {}
    for client, sessions in filtered_sessions.items():
        ike_waypoint = ''
        esp_waypoint = ''
        for id, flows in sessions.items():
            is_ike = False
            is_esp = False
            for flow in flows:
                if IKE_PORT in (flow['sourcePort'], flow['destPort']):
                    is_ike = True
                    break
                if flow['protocol'] == 'ESP':
                    is_esp = True
                    break

            if is_ike:
                for flow in flows:
                    if IKE_PORT not in (flow['sourcePort'], flow['destPort']):
                        # this is the SVR flow
                        if ike_waypoint != '':
                            error('Found more than one IKE session for client:',
                                  client, 'Aborting.')
                        if flow['forward']:
                            ike_waypoint = flow['destIp']
                        else:
                            ike_waypoint = flow['sourceIp']
                        # this session is IKE, we can go ahead with next session
                        break

            if is_esp:
                for flow in flows:
                    if flow['protocol'] == 'UDP':
                        # inspect SVR flow and check if waypoint differs IKE
                        if flow['forward']:
                            esp_waypoint = flow['destIp']
                        else:
                            esp_waypoint = flow['sourceIp']
                        # this session is ESP, we can go ahead with next session
                        break

        if not ike_waypoint:
            warn('No IKE session for ESP found ({}).'.format(id),
                 'Checking next client...')
            continue

        if ike_waypoint != esp_waypoint:
            info('Found waypoint mismatch:', id)
            stuck_sessions[id] = [{
                'session-id': id,
                'service-name': flow['serviceName'],
                'protocol': 'ESP',
                'ike_waypoint': ike_waypoint,
                'esp_waypoint': esp_waypoint,
                'client': client,
                'svr-interface': flow['networkInterfaceName'],
                'svr-src-port': flow['sourcePort'],
                'svr-dst-port': flow['destPort'],
            }]
    return stuck_sessions


def print_session_details(sessions):
    dataset = [e for s in sessions.values() for e in s]
    header = dataset[0].keys()
    rows =  [x.values() for x in dataset]
    print(tabulate(rows, header, tablefmt='rst'))


def main():
    global info
    global warn
    def quiet(*msg):
        pass

    args = parse_arguments()
    if args.quiet:
        info = quiet
        warn = quiet
    api = RestApi()
    filtered_sessions = get_filtered_sessions(api, args)
    stuck_sessions = get_stuck_sessions(filtered_sessions)

    if filtered_sessions and args.print_sessions:
        sessions = {}
        for client, cs in filtered_sessions.items():
            for id, flows in cs.items():
                for flow in flows:
                    flow['client'] = client
                sessions[id] = flows
        print_session_details(sessions)

    if stuck_sessions:
        if not args.dry_run:
            print('The following sessions will be deleted:')
            print_session_details(stuck_sessions)
            for id in stuck_sessions.keys():
                location = '/router/{}/node/{}/traffic/session?sessionId={}'.format(
                    api.get_router_name(),
                    api.get_node_name(),
                    id,
                )
                api.delete(location)


if __name__ == '__main__':
    main()
