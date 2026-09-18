"""Pins for deploy/spartan1/nginx_port80_redirect.py: it edits a live nginx file, so it changes only what it knows."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('nginx_port80_redirect', ROOT / 'deploy/spartan1/nginx_port80_redirect.py')
redirect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(redirect)

SITE = """server {
\tlisten 80 default_server;
\tserver_name _;
\tlocation ~ ^/qa-runs/.*/\\. {
\t\tdeny all;
\t\treturn 404;
\t}

\tlocation /qa-runs/ {
\t\talias /data/qa/runs/;
\t\tauth_basic "Soterix QA runs";
\t\tautoindex on;
\t}
\tlocation = / {
\t\treturn 301 https://$host:8443/assettracker/;
\t}
\tlocation / {
\t\treturn 301 https://$host:8443$request_uri;
\t}
}
"""


def test_the_two_archive_blocks_become_one_redirect_and_the_rest_stays():
    """The alias and the basic auth leave port 80; the asset tracker's two redirects are untouched."""
    new = redirect.rewrite(SITE)
    assert 'alias /data/qa/runs/' not in new
    assert 'auth_basic' not in new
    assert new.count('location /qa-runs/ {') == 1
    assert 'return 301 https://$host:8444$request_uri;' in new
    assert 'return 301 https://$host:8443/assettracker/;' in new
    assert 'return 301 https://$host:8443$request_uri;' in new
    assert new.count('{') == new.count('}')


def test_a_second_run_changes_nothing():
    """The script is safe to run again: a file with the redirect comes back as it is."""
    once = redirect.rewrite(SITE)
    assert redirect.rewrite(once) == once


def test_a_file_it_does_not_know_is_refused():
    """No archive block, or a block with a nested brace, returns None and the caller leaves the file alone."""
    assert redirect.rewrite('server {\n\tlisten 80;\n}\n') is None
    nested = SITE.replace('\t\tautoindex on;\n', '\t\tif ($x) {\n\t\t\treturn 403;\n\t\t}\n')
    assert redirect.rewrite(nested) is None
