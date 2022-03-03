#!/usr/bin/env python3

import argparse
import datetime

from lib.rest import RestApi


PREFIX = 'auto-backup-'


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Export config of 128T/SSR router')
    parser.add_argument('--host', help='Conductor/router hostname')
    parser.add_argument('--user', help='Conductor/router username (if no key auth)')
    parser.add_argument('--password', help='Conductor/router password (if no key auth)')
    parser.add_argument('--max-backups', type=int, default=3,
                        help='Delete too old backups (default: 3)')
    return parser.parse_args()


def create_backup(api):
    name = '{}{:%Y-%m-%d-%H-%M}'.format(PREFIX, datetime.datetime.now())
    r = api.post('/config/export', {'filename': name, 'datastore': 'running'})


def delete_old_backups(api, max_backups=3):
    generated_backups = []
    r = api.get('/config/export')
    for backup in r.json():
        name = backup['name']
        if name.startswith(PREFIX):
            generated_backups.append(name)

    generated_backups.sort(reverse=True)
    # delete all but <max_backups> most recent backups
    for backup in generated_backups[max_backups:]:
        r = api.delete('/config/export/{}'.format(backup))


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestApi(**params)

    create_backup(api)
    delete_old_backups(api, args.max_backups)


if __name__ == '__main__':
    main()
