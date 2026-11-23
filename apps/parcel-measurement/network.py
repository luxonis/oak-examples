import ipaddress
import subprocess


def frontend_urls(host, port):
    if host != "0.0.0.0":
        address = f"[{host}]" if ":" in host else host
        return [f"https://{address}:{port}"]
    try:
        addresses = subprocess.check_output(
            ["hostname", "-I"], text=True, timeout=2, stderr=subprocess.DEVNULL
        ).split()
    except (OSError, subprocess.SubprocessError):
        return []
    urls = []
    for address in dict.fromkeys(addresses):
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip.version == 4 and not (
            ip.is_loopback or ip.is_unspecified or ip.is_multicast
        ):
            urls.append(f"https://{address}:{port}")
    return urls
