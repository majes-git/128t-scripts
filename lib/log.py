import sys


def info(*msg):
    print('INFO:', *msg)


def error(*msg):
    print('ERROR:', *msg)
    sys.exit(1)


def warn(*msg):
    print('WARNING:', *msg)
