import socket
import sys

# Force IPv4 only to bypass buggy/slow IPv6 DNS resolution in Docker/Railway builders
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    responses = orig_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = getaddrinfo_ipv4

# Run standard pip entrypoint
from pip._internal.cli.main import main
if __name__ == '__main__':
    sys.exit(main())
