"""Het ophalen van receptpagina's: welke links mogen, en wat er gebeurt als het misgaat."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import safe_fetch
from safe_fetch import (
    FetchError,
    Reply,
    UnsafeUrlError,
    fetch_html,
    is_public_address,
    validate_url,
)

PUBLIC = "93.184.216.34"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    table = {
        "recepten.example": [PUBLIC],
        "intern.example": ["10.0.0.5"],
        "half.example": [PUBLIC, "192.168.1.10"],
        "localhost": ["127.0.0.1"],
    }

    def resolve(host, port):
        if host not in table:
            raise OSError("onbekend")
        return table[host]

    monkeypatch.setattr(safe_fetch, "_resolve", resolve)


def fake_get(monkeypatch, replies):
    """replies: url -> Reply. Houdt bij welke adressen zijn opgevraagd."""
    seen = []

    async def get(target):
        seen.append(target)
        return replies[target.url]

    monkeypatch.setattr(safe_fetch, "_get", get)
    return seen


def html(body=b"<html>recept</html>", status=200, **headers):
    return Reply(status, {"content-type": "text/html; charset=utf-8", **headers}, body, "utf-8")


# ── Welke links mogen ────────────────────────────────────────────────────────

def test_openbare_link_mag():
    target = run(validate_url("https://recepten.example/pasta"))
    assert (target.host, target.port, target.address) == ("recepten.example", 443, PUBLIC)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://recepten.example/x",
    "javascript:alert(1)",
    "https://gebruiker:geheim@recepten.example/",
    "https://recepten.example:22/",
    "https://recepten.example:6379/",
    "http://localhost/",
    "http://127.0.0.1/",
    "http://10.1.2.3/",
    "http://192.168.0.1/",
    "http://172.16.5.5/",
    "http://169.254.169.254/latest/meta-data/",
    "http://100.64.0.1/",
    "http://0.0.0.0/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://[fd00::1]/",
    "http://[fe80::1]/",
    "https://intern.example/",
    "https://half.example/",
    "https:///geen-host",
    "",
    "https://recepten.example/" + "a" * 2100,
])
def test_onveilige_link_wordt_geweigerd(url):
    with pytest.raises(UnsafeUrlError) as error:
        run(validate_url(url))
    assert error.value.status == 400


def test_onbekende_website_geeft_nette_melding():
    with pytest.raises(FetchError) as error:
        run(validate_url("https://bestaat-niet.example/"))
    assert "onbekend" not in error.value.message


@pytest.mark.parametrize(("address", "public"), [
    (PUBLIC, True), ("8.8.8.8", True), ("2606:4700:4700::1111", True),
    ("127.0.0.1", False), ("10.0.0.1", False), ("169.254.169.254", False),
    ("224.0.0.1", False), ("::1", False), ("geen-adres", False),
])
def test_is_public_address(address, public):
    assert is_public_address(address) is public


# ── Ophalen ──────────────────────────────────────────────────────────────────

def test_pagina_wordt_opgehaald(monkeypatch):
    seen = fake_get(monkeypatch, {"https://recepten.example/pasta": html("<html>é</html>".encode())})
    assert run(fetch_html("https://recepten.example/pasta")) == "<html>é</html>"
    assert seen[0].address == PUBLIC


def test_doorverwijzing_wordt_gevolgd_en_gecontroleerd(monkeypatch):
    fake_get(monkeypatch, {
        "http://recepten.example/pasta": Reply(301, {"location": "/pasta/"}, b""),
        "http://recepten.example/pasta/": html(b"ok"),
    })
    assert run(fetch_html("http://recepten.example/pasta")) == "ok"


@pytest.mark.parametrize("location", [
    "http://127.0.0.1/admin", "http://intern.example/", "http://169.254.169.254/", "file:///etc/passwd",
])
def test_doorverwijzing_naar_binnen_wordt_geweigerd(monkeypatch, location):
    fake_get(monkeypatch, {"https://recepten.example/x": Reply(302, {"location": location}, b"")})
    with pytest.raises(UnsafeUrlError):
        run(fetch_html("https://recepten.example/x"))


def test_te_veel_doorverwijzingen(monkeypatch):
    fake_get(monkeypatch, {"https://recepten.example/x": Reply(302, {"location": "/x"}, b"")})
    with pytest.raises(FetchError) as error:
        run(fetch_html("https://recepten.example/x"))
    assert "verwijst te vaak door" in error.value.message


def test_geen_html_wordt_geweigerd(monkeypatch):
    fake_get(monkeypatch, {"https://recepten.example/x.pdf": Reply(200, {"content-type": "application/pdf"}, b"%PDF")})
    with pytest.raises(FetchError) as error:
        run(fetch_html("https://recepten.example/x.pdf"))
    assert error.value.status == 422


def test_foutstatus_van_de_site(monkeypatch):
    fake_get(monkeypatch, {"https://recepten.example/x": html(status=500)})
    with pytest.raises(FetchError) as error:
        run(fetch_html("https://recepten.example/x"))
    assert error.value.status == 502


@pytest.mark.parametrize("status", [404, 410])
def test_pagina_bestaat_niet(monkeypatch, status):
    fake_get(monkeypatch, {"https://recepten.example/weg": html(status=status)})
    with pytest.raises(FetchError) as error:
        run(fetch_html("https://recepten.example/weg"))
    assert error.value.status == 422
    assert "bestaat niet" in error.value.message


def test_403_zonder_sleutel_is_een_fout(monkeypatch):
    fake_get(monkeypatch, {"https://recepten.example/x": html(status=403)})
    with pytest.raises(FetchError):
        run(fetch_html("https://recepten.example/x"))


def test_403_met_sleutel_gaat_via_scrapingbee(monkeypatch):
    fake_get(monkeypatch, {"https://recepten.example/x": html(status=403)})
    calls = []

    async def bee(url, key):
        calls.append((url, key))
        return "<html>via bee</html>"

    monkeypatch.setattr(safe_fetch, "_scrapingbee", bee)
    assert run(fetch_html("https://recepten.example/x", scrapingbee_key="sleutel")) == "<html>via bee</html>"
    assert calls == [("https://recepten.example/x", "sleutel")]


def test_verbindingsfout_lekt_geen_details(monkeypatch):
    async def boom(target):
        raise RuntimeError("Failed to connect to 10.0.0.5 port 443")

    monkeypatch.setattr(safe_fetch, "_get", boom)
    with pytest.raises(FetchError) as error:
        run(fetch_html("https://recepten.example/x"))
    assert "10.0.0.5" not in error.value.message
    assert "Failed" not in error.value.message
