#!/usr/bin/env python3

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
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
    parser.add_argument('--test-file',
                        help='Load sessions from file for testing')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quiet', action='store_true',
                        help='no output')
    group.add_argument('--print-sessions', action='store_true',
                        help='show session details')
    group.add_argument('--print-sessions-from-file',
                        help='Load file and show session details')
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
                      startTime
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

                duration = int(time.time()) - flow['startTime']
                days = duration // 86400
                hours = (duration % 86400) // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                duration_string = ''
                if days:
                    duration_string += '{}d '.format(days)
                duration_string += '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
                flow['duration'] = duration_string

                if id not in sessions:
                    sessions[id] = []
                sessions[id].append(flow)
        except (TypeError, IndexError):
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
                client = flow['sourceIp']
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
        esp_sessions = []
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
                    esp_sessions.append(id)
                    break

            if is_ike:
                for flow in flows:
                    if IKE_PORT not in (flow['sourcePort'], flow['destPort']):
                        # this is the SVR flow
                        if ike_waypoint != '':
                            warn('Found more than one IKE session for client:',
                                  client)
                        ike_waypoint = flow['sourceIp']
                        # this session is IKE, we can go ahead with next session
                        break

            if is_esp:
                for flow in flows:
                    if flow['protocol'] == 'UDP':
                        # inspect SVR flow and check if waypoint differs IKE
                        esp_waypoint = flow['sourceIp']
                        # this session is ESP, we can go ahead with next session
                        break

        if len(esp_sessions) == 0:
            warn('No ESP sessions found for client: {}.'.format(client))
            continue

        if len(esp_sessions) != 1:
            warn('Unexpected number of ESP sessions: {}.'.format(
                 len(esp_sessions)))

        if not ike_waypoint:
            warn('No IKE session for ESP found ({}).'.format(esp_sessions[0]),
                 'Checking next client...')
            continue

        if ike_waypoint != esp_waypoint:
            for id in esp_sessions:
                info('Found waypoint mismatch:', id,
                     '({} is not {})'.format(ike_waypoint, esp_waypoint))
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


def format_filtered_sessions(filtered_sessions):
    sessions = {}
    for client, cs in filtered_sessions.items():
        for id, flows in cs.items():
            for flow in flows:
                flow['client'] = client
            sessions[id] = flows
    return sessions


def print_session_details(sessions):
    dataset = [e for s in sessions.values() for e in s]
    header = dataset[0].keys()
    rows =  [x.values() for x in dataset]
    print(tabulate(rows, header, tablefmt='rst'))


def dump_data(sessions):
    dirname = '/var/log/128technology/kill-stuck-esp_{:%Y-%m-%d_%H-%M-%S}'.format(
        datetime.datetime.now())
    os.mkdir(dirname)
    # sessions
    with open(os.path.join(dirname, 'sessions.json'), 'w') as fd:
        json.dump(sessions, fd, indent=4)

    # bgp data
    subprocess.run('vtysh -c "show bgp summary" > {}'.format(
        os.path.join(dirname, 'bgp_summary.txt')), shell=True)
    subprocess.run('vtysh -c "show bgp 0.0.0.0" > {}'.format(
        os.path.join(dirname, 'bgp_default_route.txt')), shell=True)


def main():
    global info
    global warn
    def quiet(*msg):
        pass

    args = parse_arguments()
    if args.print_sessions_from_file:
        with open(args.print_sessions_from_file) as fd:
            sessions = json.load(fd)
            print_session_details(format_filtered_sessions(sessions))
        return

    if args.quiet:
        info = quiet
        warn = quiet
    api = RestApi()
    if args.test_file:
        # restore sessions from file and do not try to kill (--dry-run)
        with open(args.test_file) as fd:
            filtered_sessions = json.load(fd)
        args.dry_run = True
    else:
        filtered_sessions = get_filtered_sessions(api, args)
    stuck_sessions = get_stuck_sessions(filtered_sessions)

    if not args.test_file:
        # do not write a new file in testing mode
        with open('/var/log/128technology/stuck-esp-sessions.json.log', 'w') as fd:
            json.dump(filtered_sessions, fd)

    if filtered_sessions and args.print_sessions:
        sessions = format_filtered_sessions(filtered_sessions)
        print_session_details(sessions)

    if stuck_sessions:
        message = 'The following sessions will be deleted:'
        if args.dry_run:
            message = 'The following sessions would be deleted (without --dry-run):'
        print(message)
        print_session_details(stuck_sessions)

        if not args.dry_run:
            # write sessions and other data prior to session removal
            dump_data(filtered_sessions)

            # delete session
            for id in stuck_sessions.keys():
                location = '/router/{}/node/{}/traffic/session?sessionId={}'.format(
                    api.get_router_name(),
                    api.get_node_name(),
                    id,
                )
                api.delete(location)


if __name__ == '__main__':
    main()
