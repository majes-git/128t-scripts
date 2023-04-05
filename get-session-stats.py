#!/usr/bin/env python3

import argparse
import json

from lib.rest import RestGraphqlApi


class _Api(RestGraphqlApi):
    """Override imported class for additional methods."""
    def get_kpi(self, router_name, id):
        json = {
            'id': id,
            'window': {
                'start': 'now-86400',
                'end': 'now-10'
            },
            'order': 'ascending',
        }
        request = self.post('/router/{}/metrics'.format(router_name), json=json)
        if request.status_code == 200:
            #print('request:', request.json())
            values = [e.get('value', 0) for e in request.json() if 'value' in e]
            return values


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Get session KPIs for the last 24 hours from all connected routers')
    parser.add_argument('-c', '--host',
                        help='Conductor/router hostname')
    parser.add_argument('-u', '--user',
                        help='Conductor/router username (if no key auth)')
    parser.add_argument('-p', '--password',
                        help='Conductor/router password (if no key auth)')
    parser.add_argument('-i', '--id', action='append',
                        help='KPI ids to be retrieved')
    parser.add_argument('--json', action='store_true',
                        help='Output in json instead of csv')
    parser.add_argument('--max', action='store_true',
                        help='Aggregate sample values with max instead average')
    parser.add_argument('--null', action='store_true',
                        help='Use NULL instead of empty string if no value could be retrieved')
    parser.add_argument('--round', action='store_true',
                        help='Round values instead of using float numbers')
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.id:
        kpi_ids = args.id
    else:
        kpi_ids = [
            '/stats/aggregate-session/node/session-count',
            '/stats/aggregate-session/node/session-arrival-rate',
        ]

    if args.max:
        aggregate = max
    else:
        # default: average
        aggregate = lambda l: sum(l)/float(len(l))

    # Prepare API
    keys = ('host', 'user', 'password')
    parameters = {k: v for k, v in args.__dict__.items() if k in keys and v}
    parameters['app'] = __file__
    api = _Api(**parameters)

    stats = {}
    for router_name in api.get_router_names():
        is_router = False
        for node in api.get_nodes(router_name):
            if node.get('role') == 'conductor':
                break
            if node.get('role') == 'combo':
                is_router = True
                break
        if is_router:
            router_kpis = {}
            for id in kpi_ids:
                values = api.get_kpi(router_name, id)
                if values:
                    # KPI for the interval is defined as max of values
                    aggregated_value = aggregate(values)
                    if args.round:
                        router_kpis[id] = round(aggregated_value)
                    else:
                        router_kpis[id] = aggregated_value
                else:
                    if args.null:
                        router_kpis[id] = None
                    else:
                        router_kpis[id] = ''
            if router_kpis:
                stats[router_name] = router_kpis

    if args.json:
        print(json.dumps(stats, indent=4))
    else:
        # output csv
        lines = [[[router],[v for k,v in kpis.items()]] for router,kpis in stats.items()]
        for line in lines:
            print(','.join([str(num) for sublist in line for num in sublist]))


if __name__ == '__main__':
    main()
