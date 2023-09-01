#!/usr/bin/env python3

import argparse
import csv
import sys

from lib.log import *
from lib.rest import RestGraphqlApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Manage users on 128T/SSR routers - read comma separated lines with user attributes: username,full_name,role,local/remote,password')
    parser.add_argument('-c', '--host',
                        help='Conductor/router hostname')
    parser.add_argument('-u', '--user',
                        help='Conductor/router username (if no key auth)')
    parser.add_argument('-p', '--password',
                        help='Conductor/router password (if no key auth)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Do not create/modify/delete users')
    parser.add_argument('--ignore-disabled-users', action='store_true',
                        help='Do not automaticall enable disabled users')
    parser.add_argument('--default-admin', action='store_true',
                        help='If role is omitted use "admin" as default instead of "user"')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--disable-missing-users', action='store_true',
                        help='Disable a user account rather than deleting it')
    group.add_argument('--delete', action='store_true',
                        help='Delete user account if not present in input')

    return parser.parse_args()


def get_users(api):
    users = {}
    for user in api.get('/user').json():
        users[user['name']] = {
            'authentication_type': user['authenticationType'],
            'full_name': user['fullName'],
            'name': user['name'],
            'role': 'admin' if 'admin' in user['roles'] else 'user',
        }
        if user.get('enabled') == False:
            users[user['name']]['enabled'] = False
    return users


def add_user(api, name, attributes, dry_run):
    info('adding user:', name)
    if dry_run:
        return

    data = {
        'name': name,
        'authenticationType': attributes['authentication_type'],
        'fullName': attributes['full_name'],
        'roles': [
            attributes['role']
        ],
    }
    if attributes['authentication_type'] == 'local':
        if not attributes.get('password'):
            warn('No password provided for local user:', name, 'Skipping.')
            return
        data['password'] = attributes['password']

    request = api.post('/user', data)
    if request.status_code != 201:
        print('Error:', request.status_code, request.text)


def delete_user(api, name, dry_run):
    info('deleting user:', name)
    if dry_run:
        return

    request = api.delete('/user/' + name)
    if request.status_code != 204:
        print('Error:', request.status_code, request.text)


def update_user(api, name, attributes, dry_run):
    info('updating user:', name)
    if dry_run:
        return

    data = {
        'name': name,
    }
    if attributes.get('authentication_type'):
        data['authenticationType'] = attributes['authentication_type']
    if attributes.get('full_name'):
        data['fullName'] = attributes['full_name']
    if attributes.get('role'):
        data['roles'] = [ attributes['role'] ]
    if 'enabled' in attributes:
        data['enabled'] = attributes['enabled']
    request = api.patch('/user/' + name, data)
    if request.status_code != 200:
        print('Error:', request.status_code, request.text)


def main():
    args = parse_arguments()
    params = {}
    if args.host:
        params['host'] = args.host
        if args.user and args.password:
            params['user'] = args.user
            params['password'] = args.password
    api = RestGraphqlApi(**params)

    # Retrieve existing users
    users = get_users(api)

    # Read reference users from standard input
    fieldnames = [
        'name',
        'full_name',
        'role',
        'authentication_type',
        'password',
    ]
    input_users = {}
    reader = csv.DictReader(sys.stdin, fieldnames=fieldnames)
    for row in reader:
        if not row['password']:
            del(row['password'])
        input_users[row['name']] = row

        # if authentication_type is omitted, assume "remote"
        if not row['authentication_type']:
            row['authentication_type'] = 'remote'

        # handle role attribute if omitted
        if not row['role']:
            if args.default_admin:
                row['role'] = 'admin'
            else:
                row['role'] = 'user'


    # Process reference users
    for name, attributes in users.items():
        if name not in input_users:
            if name == 'admin':
                # do not delete the admin user
                continue
            if args.delete:
                delete_user(api, name, args.dry_run)
                continue
            if args.disable_missing_users:
                input_users[name] = attributes.copy()
                input_users[name]['enabled'] = False

        # modify user
        else:
            if input_users[name].get('password'):
                # remove password, since it cannot be changed this way
                del(input_users[name]['password'])
            if 'enabled' in attributes and not attributes['enabled']:
                if not args.ignore_disabled_users:
                    # if user disabled, but present in input -> enable it
                    input_users[name]['enabled'] = True

        if name in input_users and attributes != input_users[name]:
            update_user(api, name, input_users[name], args.dry_run)

    # Add new users
    for name, attributes in input_users.items():
        if name not in users:
            add_user(api, name, attributes, args.dry_run)


if __name__ == '__main__':
    main()
