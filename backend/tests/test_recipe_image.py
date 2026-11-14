"""De receptfoto: alleen een gewone http(s)-link komt in het antwoord."""

import pytest

from main import recipe_image_url

PAGE = "https://www.voorbeeld.nl/recepten/lasagne"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://cdn.voorbeeld.nl/foto.jpg", "https://cdn.voorbeeld.nl/foto.jpg"),
        ("  https://cdn.voorbeeld.nl/foto.jpg ", "https://cdn.voorbeeld.nl/foto.jpg"),
        ("/media/foto.jpg", "https://www.voorbeeld.nl/media/foto.jpg"),
        ("//cdn.voorbeeld.nl/foto.jpg", "https://cdn.voorbeeld.nl/foto.jpg"),
        ("", None),
        (None, None),
        (["https://cdn.voorbeeld.nl/foto.jpg"], None),
        ("javascript:alert(1)", None),
        ("data:image/png;base64,AAAA", None),
        ("https://cdn.voorbeeld.nl/" + "a" * 2000, None),
    ],
)
def test_recipe_image_url(value, expected):
    assert recipe_image_url(value, PAGE) == expected
