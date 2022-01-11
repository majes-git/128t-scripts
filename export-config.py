#!/usr/bin/env python3

import argparse
import datetime
import os
import requests

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


PREFIX = 'auto-backup-'


class UnauthorizedException(Exception):
    pass


class RestApi(object):
    """Representation of REST connection."""

    token = None
    authorized = False

    def __init__(self, host='localhost', verify=False, user='admin', password=None):
        self.host = host
        self.verify = verify
        self.user = user
        self.password = password

    def get(self, location, authorization_required=True):
        """Get data per REST API."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.get(
            url, headers=headers,
            verify=self.verify)
        return request

    def post(self, location, json, authorization_required=True):
        """Send data per REST API via post."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        # Login if not yet done
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.post(
            url, headers=headers, json=json,
            verify=self.verify)
        return request

    def delete(self, location, authorization_required=True):
        """Delete data per REST API."""
        url = 'https://{}/api/v1/{}'.format(self.host, location.strip('/'))
        headers = {
            'Content-Type': 'application/json',
        }
        if authorization_required:
            if not self.authorized:
                self.login()
            if self.token:
                headers['Authorization'] = 'Bearer {}'.format(self.token)
        request = requests.delete(
            url, headers=headers,
            verify=self.verify)
        return request

    def login(self):
        json = {
            'username': self.user,
        }
        if self.password:
            json['password'] = self.password
        else:
            key_file = 'pdc_ssh_key'
            if not os.path.isfile(key_file):
                key_file = '/home/admin/.ssh/pdc_ssh_key'

            key_content = ''
            with open(key_file) as fd:
                key_content = fd.read()
            json['local'] = key_content
        request = self.post('/login', json, authorization_required=False)
        if request.status_code == 200:
            self.token = request.json()['token']
            self.authorized = True
        else:
            message = request.json()['message']
            raise UnauthorizedException(message)


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
