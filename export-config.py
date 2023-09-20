#!/usr/bin/env python3

import argparse
import datetime
import os

from lib.rest import RestGraphqlApi


PREFIX = 'auto-backup-'


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Export config of 128T/SSR router')
    parser.add_argument('--host', help='Conductor/router hostname')
    parser.add_argument('--user', help='Conductor/router username (if no key auth)')
    parser.add_argument('--password', help='Conductor/router password (if no key auth)')
    parser.add_argument('--directory', default=os.getcwd(),
                        help='Director to store the download')
    parser.add_argument('--download', action='store_true',
                        help='Download the exported config to this machine')
    parser.add_argument('--keep', action='store_true',
                        help='Keep backup files on the conductor/router after the download')
    parser.add_argument('--max-backups', type=int, default=3,
                        help='Delete too old backups (default: 3)')
    return parser.parse_args()


def create_backup(api):
    name = '{}{:%Y-%m-%d-%H-%M}'.format(PREFIX, datetime.datetime.now())
    r = api.post('/config/export', {'filename': name, 'datastore': 'running'})
    # return the filename without the path
    filename = r.json()['exportPath'].replace('/etc/128technology/config-exports/', '')
    return filename


def delete_backup(api, filename):
    r = api.delete('/config/export/{}'.format(filename))


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
        delete_backup(api, backup)


def download_backup(api, directory, filename):
    nonce = api.get('/nonce').json()['nonce']
    r = api.get(f'/config/export/{filename}/download?nonce={nonce}')
    # write the file to local disk
    path = os.path.join(directory, filename)
    with open(path, 'wb') as fd:
        fd.write(r.content)
        print('Successfully saved config as:', path)


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestGraphqlApi(**params)

    filename = create_backup(api)
    # when the file should be downloaded, just get the file (unless --keep is given)
    # otherwise do a cleanup
    if args.download:
        download_backup(api, args.directory, filename)
        if not args.keep:
            delete_backup(api, filename)
    else:
        delete_old_backups(api, args.max_backups)


if __name__ == '__main__':
    main()
