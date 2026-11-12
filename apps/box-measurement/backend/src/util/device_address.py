import ipaddress
import logging
import socket

logger = logging.getLogger(__name__)

# Connecting a UDP socket selects a local route without sending any packets.
# TEST-NET-1 is reserved for documentation and does not need to be reachable.
_ROUTE_PROBE_ADDRESS = ("192.0.2.1", 9)


def discover_device_ipv4_address() -> str | None:
    """Returns the IPv4 address of the default route's interface, or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route_probe:
            route_probe.connect(_ROUTE_PROBE_ADDRESS)
            address = route_probe.getsockname()[0]
    except OSError:
        logger.warning("Could not discover the OAK device IPv4 address")
        return None

    try:
        parsed_address = ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError:
        logger.warning("Ignoring invalid discovered OAK device address: %s", address)
        return None

    if (
        parsed_address.is_loopback
        or parsed_address.is_multicast
        or parsed_address.is_unspecified
    ):
        logger.warning("Ignoring unusable discovered OAK device address: %s", address)
        return None
    return str(parsed_address)
