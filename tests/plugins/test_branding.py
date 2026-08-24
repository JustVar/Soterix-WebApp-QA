"""Unit tests for plugins/branding.py."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import branding  # noqa: E402

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 16


def test_favicon_and_header_embed_the_files(tmp_path, monkeypatch):
    """Both tags embed the PNG bytes as a data URI when the files exist."""
    (tmp_path / 'logo-square.png').write_bytes(PNG)
    (tmp_path / 'logo-wide.png').write_bytes(PNG)
    monkeypatch.setattr(branding, 'SQUARE_LOGO', tmp_path / 'logo-square.png')
    monkeypatch.setattr(branding, 'WIDE_LOGO', tmp_path / 'logo-wide.png')
    branding._data_uri.cache_clear()
    assert branding.favicon_link().startswith('<link rel="icon" type="image/png" href="data:image/png;base64,')
    img = branding.header_logo(40)
    assert 'data:image/png;base64,' in img
    assert 'height:40px' in img
    assert 'Soterix Systems' in img


def test_missing_files_leave_the_page_unbranded(tmp_path, monkeypatch):
    """A missing logo file yields an empty tag, never an error."""
    monkeypatch.setattr(branding, 'SQUARE_LOGO', tmp_path / 'none.png')
    monkeypatch.setattr(branding, 'WIDE_LOGO', tmp_path / 'none.png')
    branding._data_uri.cache_clear()
    assert branding.favicon_link() == ''
    assert branding.header_logo() == ''


def test_repo_assets_are_present():
    """The committed branding files exist and are PNGs."""
    for p in (branding.WIDE_LOGO, branding.SQUARE_LOGO):
        assert (REPO_ROOT / p).read_bytes().startswith(b'\x89PNG'), p
