#!/usr/bin/env python3

import argparse
import os
import pkgutil
from subprocess import run
from lib.log import *

WHITELIST = (
    '/etc/salt/minion',
    '/etc/128technology/global.init',
    '/etc/128technology/local.init',
    '/etc/128technology/pki/api/api.key',
    '/etc/128technology/pki/api/api.key.pub',
    '/etc/128technology/pki/api/conductor-api.key.pub',
    '/etc/128technology/pki/api/router-api.key',
    '/etc/128technology/pki/api/router-api.key.pub',
    '/home/admin/.ssh/netconf_authorized_keys',
    '/home/admin/.ssh/pdc_ssh_key',
    '/home/admin/.ssh/pdc_ssh_key.pub',
)
IGNORE_DIRS = (
    '/dev',
    '/etc/128technology/system.demon',
    '/etc/wanpipe/api',
    '/proc',
    '/run',
    '/sys',
    '/tmp',
    '/var/cache',
    '/var/lib/cloud/instances',
    '/var/lib/128technology/influxdb/wal/t128',
    '/var/log',
    '/var/spool',
)
IGNORE_FILES = (
    '__init__.pxd',
    '__init__.py',
    '__init__.pyi',
    'py.typed',
)
IGNORE_EXTENSIONS = (
    '.gpg',
    '.gpg~',
    '.lock',
    '.lease',
)


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Find 0 byte files and fix them')
    parser.add_argument('--start-dir', '-d', required=True,
                        help='directory to start with search (default: /)')
    parser.add_argument('--remove-zero', action='store_true',
                        help='remove/delete 0 byte files')
    parser.add_argument('--remove-whitelisted', action='store_true',
                        help='remove/delete whitelisted files')
    parser.add_argument('--hook-zero',
                        help='command to be run after 0 byte files were found')
    parser.add_argument('--hook-whitelisted',
                        help='command to be run after whitelisted files were found')
    parser.add_argument('--hook-no-arg', action='store_true',
                        help='pass no files as argument')
    parser.add_argument('--hook-one-arg', action='store_true',
                        help='pass all files as one argument (space separated)')
    parser.add_argument('--show-zero', '-0', action='store_true',
                        help='show 0 byte files')
    parser.add_argument('--show-whitelisted', '-w', action='store_true',
                        help='show whitelisted files')
    parser.add_argument('--ignore-file', help='use additional file with ignores')
    parser.add_argument('--whitelist-file', help='use additional file as whitelist')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='no output')
    return parser.parse_args()


def call(cmd, list, no_arg=False, one_arg=False):
    full_cmd = cmd.split(' ')
    if not no_arg:
        full_cmd += list
    if one_arg:
        full_cmd = cmd.split(' ') + [' '.join(list)]
    run(full_cmd)


def read_ignore_list(ignore_file):
    ignore_list = []
    data = pkgutil.get_data('ignore', 'ignore_list')
    ignore_list.extend(data.decode('ascii').splitlines())
    if ignore_file:
        try:
            with open(ignore_file) as fd:
                for line in fd.readlines():
                    ignore_list.append(line.strip())
        except:
            error('Cannot read ignore file:', ignore_file)
    return ignore_list


def read_white_list(whitelist_file):
    white_list = list(WHITELIST)
    if whitelist_file:
        try:
            with open(whitelist_file) as fd:
                for line in fd.readlines():
                    white_list.append(line.strip())
        except:
            error('Cannot read whitelist file:', whitelist_file)
    return white_list


def main():
    args = parse_arguments()
    ignore_list = read_ignore_list(args.ignore_file)
    white_list = read_white_list(args.whitelist_file)
    found_zero_bytes = []
    found_whitelisted = []
    # check all files in start_dir
    for root, dirs, files in os.walk(args.start_dir):
        for dir in dirs[:]:
            path = os.path.join(root, dir)
            if path in IGNORE_DIRS:
                dirs.remove(dir)

        for file in files:
            name = os.path.join(root, file)
            low = file.lower()

            # check ignore lists
            if file in IGNORE_FILES:
                continue
            if any([low.endswith(extension) for extension in IGNORE_EXTENSIONS]):
                continue
            if name in ignore_list:
                continue

            if os.path.isfile(name):    # ignore symlinks and other non-files
                size = os.path.getsize(name)
                if size == 0:
                    found_zero_bytes.append(name)
                    if args.show_zero:
                        info('zero-bytes:', name)
                    if name in white_list:
                        found_whitelisted.append(name)
                        if args.show_whitelisted:
                            info('whitelisted:', name)

    # removing files if requested
    if args.remove_zero:
        for file in found_zero_bytes:
            try:
                if not args.quiet:
                    info('removing:', file)
                os.remove(file)
            except FileNotFoundError:
                # file was already removed
                pass

    if args.remove_whitelisted:
        for file in found_whitelisted:
            try:
                if not args.quiet:
                    info('removing:', file)
                os.remove(file)
            except FileNotFoundError:
                # file was already removed
                pass

    # calling hooks
    if args.hook_zero and found_zero_bytes:
        call(args.hook_zero, found_zero_bytes, args.hook_one_arg)
    if args.hook_whitelisted and found_whitelisted:
        call(args.hook_whitelisted, found_whitelisted, args.hook_one_arg)


if __name__ == '__main__':
    main()
