#!/usr/bin/env python3
import argparse
import socket

MESSAGE = 'Hello, World!'


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser('send UDP packet with DSCP/TOS')
    parser.add_argument('--ip', '-i', required=True, help='destination IP address')
    parser.add_argument('--dport', '-d', type=int, default=12800, help='destination port (default: 12800)')
    parser.add_argument('--sport', '-s', type=int, default=12800, help='source port (default: 12800)')
    parser.add_argument('--tos', '-t', type=int, default=0x10, help='TOS value (default: 0x10)')
    return parser.parse_args()


def main():
    args = parse_arguments()

    print(f'UDP target IP: {args.ip}')
    print(f'UDP target port: {args.dport}')
    print(f'UDP source port: {args.sport}')

    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, args.tos)
    sock.bind(('0.0.0.0', args.sport))
    sock.sendto(MESSAGE.encode(), (args.ip, args.dport))


if __name__ == '__main__':
    main()
