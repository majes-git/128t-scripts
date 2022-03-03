#!/usr/bin/env python3

import argparse
import json
from crypt import crypt
from hmac import compare_digest
from lib.log import *
from lib.rest import RestApi


DEFAULT_PASSWD = '128tRoutes'
USER_FILE = '/var/lib/128technology/user-running.json'


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Change default password on 128T/SSR router')
    parser.add_argument('--username', help='username', required=True)
    parser.add_argument('--password', help='password', required=True)
    parser.add_argument('--silent', help='no output', action='store_true')
    return parser.parse_args()


def check_if_default(username, silent=False):
    with open(USER_FILE) as fd:
        users_config = json.load(fd)['datastore']['config']
        for user in users_config['authority']['router'][0]['user']:
            if username != user['name']:
                continue
            passwd = user['password']
            is_default = compare_digest(crypt(DEFAULT_PASSWD, passwd), passwd)
            if not is_default and not silent:
                error('User "{}" has not got default password. Cannot be changed!'.format(username))
            return
        if not silent:
            error('User "{}" could not be found.'.format(username))


def change_password(api, username, password, silent=False):
    data = { 'password': password,
             'oldPassword': DEFAULT_PASSWD}
    r = api.patch('/user/{}'.format(username), data)
    if r.status_code != 200 and not silent:
        error(r.status_code, r.json().get('message'))


def main():
    args = parse_arguments()
    api = RestApi()

    check_if_default(args.username, args.silent)
    change_password(api, args.username, args.password, args.silent)


if __name__ == '__main__':
    main()
