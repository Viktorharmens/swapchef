"""Een receptpagina ophalen zonder dat de engine misbruikt kan worden.

De bezoeker geeft zelf de link op. Zonder controle kan iemand de engine zo
adressen laten opvragen die alleen van binnenuit bereikbaar zijn (localhost,
het interne netwerk, de metadata-dienst van de hoster). Daarom:

- alleen http(s), zonder inlog in de link, op een gewone poort;
- de hostnaam moet naar een openbaar adres wijzen (álle adressen worden bekeken);
- de verbinding gaat naar precies het adres dat is gecontroleerd, zodat de
  naam tussen controle en ophalen niet ergens anders heen kan wijzen;
- doorverwijzingen volgen we zelf, en elke stap krijgt dezelfde controle;
- de pagina mag niet groter zijn dan MAX_BYTES en moet HTML zijn.

Foutmeldingen zijn voor de bezoeker bedoeld: er staan geen adressen of
technische details in.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from curl_cffi import CurlOpt
from curl_cffi.requests import AsyncSession as CurlSession

MAX_URL_LENGTH = 2000
MAX_REDIRECTS = 5
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 15
ALLOWED_PORTS = {80, 443, 8080}
HTML_TYPES = ("text/html", "application/xhtml+xml")

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


class FetchError(Exception):
    """Ophalen mislukt. `status` is de HTTP-status voor ons eigen antwoord."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


class UnsafeUrlError(FetchError):
    """De link mag niet worden opgehaald."""

    def __init__(self, message: str = "Deze link kunnen we niet openen. Plak de link van een openbare receptpagina."):
        super().__init__(message, status=400)


@dataclass(frozen=True)
class Target:
    url: str
    host: str
    port: int
    address: str  # het gecontroleerde IP-adres waar de verbinding heen gaat


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str]  # namen in kleine letters
    body: bytes
    charset: str | None = None


# ── Controleren ──────────────────────────────────────────────────────────────

def is_public_address(value: str) -> bool:
    """Is dit een adres op het openbare internet?"""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    # ::ffff:127.0.0.1 is gewoon 127.0.0.1
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    if address.version == 4 and address in _CGNAT:
        return False
    return address.is_global and not address.is_multicast


def _resolve(host: str, port: int) -> list[str]:
    """Alle adressen waar een hostnaam naar wijst. Los, zodat tests hem kunnen vervangen."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


async def validate_url(url: str) -> Target:
    """Controleert de link en geeft terug waar we heen mogen verbinden."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeUrlError()

    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        raise UnsafeUrlError() from None

    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrlError()
    if parts.username or parts.password:
        raise UnsafeUrlError()
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in ALLOWED_PORTS:
        raise UnsafeUrlError()

    host = parts.hostname
    try:
        ipaddress.ip_address(host)
        addresses = [host]  # er staat al een IP-adres in de link
    except ValueError:
        try:
            addresses = await asyncio.get_running_loop().run_in_executor(None, _resolve, host, port)
        except OSError:
            raise FetchError("Deze website kunnen we niet vinden. Controleer de link.") from None

    if not addresses or not all(is_public_address(address) for address in addresses):
        raise UnsafeUrlError()

    return Target(url=parts.geturl(), host=host, port=port, address=addresses[0])


# ── Ophalen ──────────────────────────────────────────────────────────────────

async def _get(target: Target) -> Reply:
    """Eén verzoek, zonder doorverwijzingen te volgen. Los, zodat tests hem kunnen vervangen."""
    address = f"[{target.address}]" if ":" in target.address else target.address
    # Verbind met het adres dat we hebben gecontroleerd, niet met wat de naam nu oplevert.
    pin = {CurlOpt.RESOLVE: [f"{target.host}:{target.port}:{address}"]}
    async with CurlSession(impersonate="chrome131", curl_options=pin) as session:
        response = await session.get(target.url, allow_redirects=False, timeout=TIMEOUT, stream=True)
        try:
            headers = {name.lower(): value for name, value in response.headers.items()}
            declared = headers.get("content-length", "")
            if declared.isdigit() and int(declared) > MAX_BYTES:
                raise FetchError("Deze pagina is te groot om te lezen.")

            chunks, size = [], 0
            if not 300 <= response.status_code < 400:
                async for chunk in response.aiter_content():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise FetchError("Deze pagina is te groot om te lezen.")
                    chunks.append(chunk)
            return Reply(response.status_code, headers, b"".join(chunks), response.charset_encoding)
        finally:
            await response.aclose()


async def _scrapingbee(url: str, key: str) -> str:
    """Tweede poging via ScrapingBee als de site ons met een 403 weigert."""
    async with httpx.AsyncClient() as client:
        reply = await client.get(
            "https://app.scrapingbee.com/api/v1/",
            params={"api_key": key, "url": url, "render_js": "false"},
            timeout=30,
        )
    if reply.status_code >= 400 or len(reply.content) > MAX_BYTES:
        raise FetchError("Deze website laat zich niet uitlezen. Probeer een recept van een andere site.")
    return reply.text


def _decode(reply: Reply) -> str:
    for encoding in (reply.charset, "utf-8"):
        if not encoding:
            continue
        try:
            return reply.body.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return reply.body.decode("utf-8", errors="replace")


async def fetch_html(url: str, *, scrapingbee_key: str | None = None) -> str:
    """Haalt de HTML van een receptpagina op. Gooit FetchError met een melding voor de bezoeker."""
    target = await validate_url(url)

    for _ in range(MAX_REDIRECTS + 1):
        try:
            reply = await _get(target)
        except FetchError:
            raise
        except Exception:  # noqa: BLE001 - elke verbindingsfout krijgt dezelfde melding
            # Bewust geen details: de foutmelding van de verbinding kan adressen bevatten.
            raise FetchError("Deze website reageert niet. Probeer het later nog eens.") from None

        if 300 <= reply.status < 400 and reply.headers.get("location"):
            target = await validate_url(urljoin(target.url, reply.headers["location"]))
            continue
        break
    else:
        raise FetchError("Deze link verwijst te vaak door.")

    if reply.status == 403 and scrapingbee_key:
        return await _scrapingbee(target.url, scrapingbee_key)
    if reply.status in (404, 410):
        raise FetchError("Deze pagina bestaat niet (meer). Controleer de link.", status=422)
    if reply.status >= 400:
        raise FetchError("Deze website laat zich niet uitlezen. Probeer een recept van een andere site.")

    content_type = reply.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type and content_type not in HTML_TYPES:
        raise FetchError("Deze link is geen webpagina met een recept.", status=422)

    return _decode(reply)
