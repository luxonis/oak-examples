import datetime
import ipaddress
import logging
import os
import posixpath
import socket
import ssl
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_IP = "0.0.0.0"
DEFAULT_FRONTEND_PORT = 8082
APP_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FRONTEND_DIR = (APP_ROOT / "frontend" / "dist").resolve()
DEFAULT_CERT_PATH = APP_ROOT / ".https" / "server.crt"
DEFAULT_KEY_PATH = APP_ROOT / ".https" / "server.key"

CUSTOM_MIME_TYPES = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".wasm": "application/wasm",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".eot": "application/vnd.ms-fontobject",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def is_standalone_frontend_managed() -> bool:
    """Return True when the oakapp runtime manages static frontend hosting."""
    return bool(os.environ.get("OAKAPP_STATIC_FRONTEND_PORT"))


def _generate_self_signed_certificate(cert_path: Path, key_path: Path) -> None:
    """Generate a self-signed TLS certificate for localhost HTTPS."""
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        _generate_self_signed_certificate_with_openssl(cert_path, key_path)
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


def _generate_self_signed_certificate_with_openssl(
    cert_path: Path, key_path: Path
) -> None:
    """Fallback self-signed certificate generator using the openssl CLI."""
    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                "365",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Failed to generate a self-signed TLS certificate for local HTTPS. "
            "Install the 'cryptography' package, ensure 'openssl' is available on PATH, "
            "or provide --certificate-path and --key-path."
        ) from exc
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


class _FrontendRequestHandler(SimpleHTTPRequestHandler):
    def guess_type(self, path: str) -> str:
        _, ext = posixpath.splitext(path)
        custom_type = CUSTOM_MIME_TYPES.get(ext.lower())
        if custom_type is not None:
            return custom_type
        return super().guess_type(path)

    def send_head(self):
        if self._is_browser_route():
            self.path = "/index.html"
        return super().send_head()

    def _is_browser_route(self) -> bool:
        target = self.translate_path(self.path)
        return (
            not os.path.isfile(target)
            and not os.path.isfile(os.path.join(target, "index.html"))
            and not os.path.splitext(target)[1]
        )

    def log_message(self, format: str, *args) -> None:
        logger.debug(format, *args)

    def log_error(self, format: str, *args) -> None:
        message = format % args
        if self.path:
            message = f"{self.path} - {message}"
        logger.error(message)

    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError, socket.error) as e:
            logger.debug("Client disconnected during file transfer: %s", e)

    def do_GET(self) -> None:
        try:
            super().do_GET()
        except Exception as e:
            logger.error("Error handling GET request: %s", e)
            try:
                self.send_error(500, "Internal Server Error")
            except Exception:
                logger.debug(
                    "Failed to send error response; client may have disconnected."
                )

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()


class _SafeThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        _, exc_value, _ = sys.exc_info()
        if isinstance(
            exc_value,
            (ConnectionResetError, BrokenPipeError, ssl.SSLError, socket.error),
        ):
            logger.debug(
                "Client disconnected from %s: %s",
                client_address,
                exc_value,
            )
            return
        logger.error("Error handling request from %s: %s", client_address, exc_value)


class FrontendServer:
    INDEX_FILE = "index.html"

    def __init__(
        self,
        ip: str = DEFAULT_FRONTEND_IP,
        port: int = DEFAULT_FRONTEND_PORT,
        directory: Optional[Path] = None,
        use_ssl: bool = False,
        certificate_path: Optional[Path] = None,
        key_path: Optional[Path] = None,
    ):
        self._ip = ip
        self._use_ssl = use_ssl
        self._directory = Path(
            directory
            or os.environ.get("OAKAPP_STATIC_FRONTEND_PATH")
            or DEFAULT_FRONTEND_DIR
        ).resolve()

        if not (self._directory / self.INDEX_FILE).is_file():
            raise FileNotFoundError(
                f"Failed to start the frontend server. File {self.INDEX_FILE} not found "
                f"in {self._directory}. Build the frontend first: "
                "cd frontend && npm ci && npm run build"
            )

        handler = partial(_FrontendRequestHandler, directory=str(self._directory))
        self._httpd = _SafeThreadingHTTPServer((ip, port), handler)
        self._port = self._httpd.server_port
        self._thread: Optional[threading.Thread] = None
        self._stopped = False

        if self._use_ssl:
            try:
                cert_file = Path(certificate_path or DEFAULT_CERT_PATH).resolve()
                key_file = Path(key_path or DEFAULT_KEY_PATH).resolve()
                if not (cert_file.is_file() and key_file.is_file()):
                    logger.info(
                        "Generating self-signed HTTPS certificate for localhost..."
                    )
                    _generate_self_signed_certificate(cert_file, key_file)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(str(cert_file), str(key_file))
                self._httpd.socket = context.wrap_socket(
                    self._httpd.socket, server_side=True
                )
            except Exception:
                self._httpd.server_close()
                raise

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="p2p-frontend-http-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)

    @property
    def ip(self) -> str:
        return self._ip

    @property
    def printable_ip(self) -> str:
        if not self._ip or self._ip == "0.0.0.0":
            return "localhost"
        return self._ip

    @property
    def port(self) -> int:
        return self._port

    @property
    def protocol(self) -> str:
        return "https" if self._use_ssl else "http"

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.printable_ip}:{self.port}"


def start_frontend_server(
    ip: str = DEFAULT_FRONTEND_IP,
    port: int = DEFAULT_FRONTEND_PORT,
    directory: Optional[str] = None,
    use_ssl: bool = False,
    certificate_path: Optional[str] = None,
    key_path: Optional[str] = None,
    no_frontend: bool = False,
) -> Optional[FrontendServer]:
    """Start the local static frontend server in peripheral mode.

    Returns None when disabled via --no-frontend or when running in standalone
    mode (where oakapp serves the static frontend bundle).
    """
    if no_frontend or is_standalone_frontend_managed():
        return None

    server = FrontendServer(
        ip=ip,
        port=port,
        directory=Path(directory) if directory else None,
        use_ssl=use_ssl,
        certificate_path=Path(certificate_path) if certificate_path else None,
        key_path=Path(key_path) if key_path else None,
    )
    server.start()
    print(f"Serving frontend at {server.url}")
    return server
