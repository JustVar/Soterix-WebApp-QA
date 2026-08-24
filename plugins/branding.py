"""Company branding for the generated report pages.

Two PNGs under assets/branding/ carry the logo (see the README there):
logo-wide.png for page headers, logo-square.png for the browser tab icon.
Replace the files to change the logo everywhere; the pages embed the bytes
at build time, so they stay self-contained and older reports keep the logo
they were built with. A missing file simply leaves the page unbranded.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

BRAND_DIR = Path('assets') / 'branding'
WIDE_LOGO = BRAND_DIR / 'logo-wide.png'
SQUARE_LOGO = BRAND_DIR / 'logo-square.png'
COMPANY = 'Soterix Systems'


@lru_cache(maxsize=4)
def _data_uri(path: str) -> str:
    """The file as a PNG data URI, or '' when it is not there."""
    p = Path(path)
    try:
        return 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
    except OSError:
        return ''


def favicon_link() -> str:
    """The <link rel="icon"> tag for a page head, or '' without a square logo."""
    uri = _data_uri(str(SQUARE_LOGO))
    return f'<link rel="icon" type="image/png" href="{uri}">' if uri else ''


def header_logo(height_px: int = 44) -> str:
    """The <img> for a page header, or '' without a wide logo."""
    uri = _data_uri(str(WIDE_LOGO))
    if not uri:
        return ''
    return (f'<img class="brand" src="{uri}" alt="{escape(COMPANY)}" '
            f'height="{height_px}" style="height:{height_px}px;width:auto">')
