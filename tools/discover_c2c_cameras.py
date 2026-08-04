#!/usr/bin/env python3
"""Discover C2C camera specs from the live devices and emit the test registry.

The C2C tests assert model, manufacturer, max resolution and max framerate
against what the camera reports, so those values have to come from the devices
themselves - a hand-typed registry silently rots the moment the lab re-addresses
or swaps hardware.

This logs into each camera's Setup > System Information page, scrapes the fields
the tests rely on, and writes a ready-to-use tests/data/c2c_cameras.yaml.

Usage:
    # Discover from an inventory CSV (model,serial,ip,mac,rtsp)
    python tools/discover_c2c_cameras.py --inventory c2c_inventory.csv

    # Or straight from a list of IPs
    python tools/discover_c2c_cameras.py --ips 10.2.0.116 10.2.0.117

    # Preview without writing the registry
    python tools/discover_c2c_cameras.py --ips 10.2.0.116 --dry-run

Credentials come from C2C_CAMERA_USER / C2C_CAMERA_PASS, defaulting to the
lab's shared login. Unreachable cameras are recorded as enabled: false with a
note, rather than being dropped - the lab rotates devices in and out.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

# Progress must be visible while this runs against a batch of cameras, so do
# not let stdout sit in a buffer when the output is redirected to a file.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except AttributeError:  # pragma: no cover - very old Python
    pass

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "tests" / "data" / "c2c_cameras.yaml"

USER = os.environ.get("C2C_CAMERA_USER", "root")
PASSWORD = os.environ.get("C2C_CAMERA_PASS", "***REMOVED***")

PROBE_TIMEOUT = 2.0
# Some cameras answer TCP promptly but are slow to render the setup UI, so the
# page-load budget is generous and tunable. C2C_NAV_TIMEOUT is in seconds.
NAV_TIMEOUT = int(float(os.environ.get("C2C_NAV_TIMEOUT", "45")) * 1000)
# Clicks target elements by id, so they either resolve immediately or not at
# all - a long timeout here just turns a missing page into a stall.
CLICK_TIMEOUT = 5000

# The setup UI's left nav uses stable element ids. Driving it by id instead of
# by visible text avoids matching against the "> SYSTEM" / "v VCA" expander
# prefixes, which silently fail and then burn a full navigation timeout.
NAV = {
    "system_info": ("system", "System_Information"),
    "firmware":    ("system", "firmware_update"),
    "plugins":     ("system", "Plug_in"),
    "licenses":    ("vca", "license"),
    "cloud":       ("soterix", "connect"),
}


def reachable(ip: str, port: int = 80) -> bool:
    """Quick TCP check so we do not wait out a full navigation timeout."""
    try:
        with socket.create_connection((ip, port), timeout=PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def slug(model: str, ident: str) -> str:
    """Stable, readable test id: model plus the serial.

    Deliberately excludes the IP. These cameras are re-addressed between
    batches, so an id built on the IP would churn every time and break any
    mapping keyed on it.
    """
    base = (model or "cam").strip().lower().replace(" ", "-").replace("/", "-")
    tail = (ident or "").strip().lower().replace(" ", "-")
    return f"{base}-{tail}" if tail else base


def open_setup(page, ip: str) -> None:
    """Load the camera's setup UI."""
    page.goto(
        f"http://{ip}/cgi-bin/admin/setup_main.cgi",
        wait_until="domcontentloaded",
        timeout=NAV_TIMEOUT,
    )
    page.wait_for_timeout(1500)


def nav_to(page, what: str) -> None:
    """Open a setup page by element id, expanding its section if needed.

    Nav markup is not identical across models - some cameras have no
    `ul#vca` wrapper even though they do have `li#license` - so the section
    id is a hint, not a requirement. Resolve the item's real parent from the
    DOM instead of assuming one, and never click a section that is already
    open (the header toggles, so that would hide the target).
    """
    section, item = NAV[what]
    target = page.locator(f"li#{item}").first
    if target.count() == 0:
        raise RuntimeError(f"no nav item li#{item} on this camera")

    if not target.is_visible():
        # Preferred: the documented section wrapper.
        wrapper = page.locator(f"ul#{section}")
        if wrapper.count():
            wrapper.first.click(timeout=CLICK_TIMEOUT)
        else:
            # Fall back to whatever list actually contains the item.
            page.evaluate(
                """(id) => {
                  const li = document.getElementById(id);
                  if (!li) return;
                  const ul = li.closest('ul');
                  if (ul) ul.click();
                }""",
                item,
            )
        target.wait_for(state="visible", timeout=CLICK_TIMEOUT)

    target.click(timeout=CLICK_TIMEOUT)
    page.wait_for_timeout(1200)


def _labelled_values(page) -> dict:
    """Map every two-column 'label | value' row on the page into a dict.

    Reading the tables wholesale is far less brittle than locating each label
    by text, and it picks up fields we did not think to ask for - which is the
    point of discovery.
    """
    return page.evaluate(r"""() => {
      const out = {};
      document.querySelectorAll('table tr').forEach(tr => {
        const cells = [...tr.querySelectorAll('td,th')]
          .map(c => (c.innerText || '').trim());
        if (cells.length >= 2 && cells[0] && cells[1]) {
          if (!(cells[0] in out)) out[cells[0]] = cells[1];
        }
      });
      return out;
    }""")


def scrape_system_info(page) -> dict:
    """Read Setup > SYSTEM > SYSTEM INFORMATION."""
    nav_to(page, "system_info")
    return _labelled_values(page)


def scrape_firmware(page) -> dict:
    """Read Setup > SYSTEM > FIRMWARE UPDATE - the current firmware version."""
    nav_to(page, "firmware")
    info = {k: v for k, v in _labelled_values(page).items()
            if re.search(r"(?i)version|firmware|build", k)}
    if not info:
        # Nothing labelled; fall back to a version-shaped token on the page.
        try:
            text = page.locator("body").inner_text(timeout=2000)
            m = re.search(r"(?i)firmware[^\n]*?(\d+\.\d[\w.\-]*)", text) \
                or re.search(r"\b\d+\.\d+\.\d+[\w.\-]*\b", text)
            if m:
                info["Version"] = m.group(1) if m.lastindex else m.group(0)
        except Exception:
            pass
    return info


def scrape_plugins(page) -> list[dict]:
    """Read Setup > SYSTEM > PLUG-IN - installed plugins and versions."""
    nav_to(page, "plugins")
    return _table_rows(page, ("name", "version", "status"))


def scrape_licenses(page) -> list[dict]:
    """Read Setup > VCA > LICENSE - the Activated License(s) table."""
    nav_to(page, "licenses")
    return _table_rows(page, ("assigned", "license"))


def scrape_cloud_state(page) -> str:
    """Read Setup > Soterix > CONNECT and classify the registration state.

    'waiting' is a real state, distinct from 'not_registered': the camera has
    been provisioned but has not completed registration with the cloud. For a
    certification record that difference is the whole point.
    """
    if page.locator("li#connect").count() == 0:
        # Unbranded VCA units have no Soterix Cloud section at all.
        return "unavailable"
    nav_to(page, "cloud")
    page.wait_for_timeout(2500)  # status resolves asynchronously
    text = page.locator("body").inner_text()
    if "Registered Cloud Address" in text:
        return "registered"
    if "Waiting for cloud registration" in text:
        return "waiting"
    if "I am not registered" in text:
        return "not_registered"
    return "unknown"


def _table_rows(page, cols: tuple[str, ...]) -> list[dict]:
    """Return data rows from the table whose header matches `cols`.

    These pages carry more than one table - the LICENSE page shows an
    "Activate License" form before the "Activated License(s)" listing - so
    picking the first table silently yields the wrong one (or nothing). Match
    on the header instead.
    """
    return page.evaluate(
        r"""(cols) => {
          const want = cols.map(c => c.toLowerCase());
          const tables = [...document.querySelectorAll('table')];
          for (const t of tables) {
            const rows = [...t.querySelectorAll('tr')];
            if (rows.length < 2) continue;
            const head = [...rows[0].querySelectorAll('td,th')]
              .map(c => (c.innerText || '').trim().toLowerCase());
            // Header must contain every column we asked for.
            if (!want.every(w => head.some(h => h === w))) continue;
            const idx = want.map(w => head.findIndex(h => h === w));
            const out = [];
            for (const tr of rows.slice(1)) {
              const cells = [...tr.querySelectorAll('td,th')]
                .map(c => (c.innerText || '').trim());
              if (!cells.length) continue;
              const rec = {};
              cols.forEach((c, i) => { rec[c] = cells[idx[i]] ?? ''; });
              if (Object.values(rec).some(v => v)) out.push(rec);
            }
            return out;
          }
          return [];
        }""",
        list(cols),
    )


def discover_one(browser, cam: dict) -> dict:
    """Return the registry entry for one camera, reachable or not."""
    ip = cam["ip"]
    entry = {
        "id": cam.get("id") or slug(cam.get("model", ""), ip),
        "ip": ip,
        "user": USER,
        "password": PASSWORD,
    }
    for k in ("mac", "serial", "rtsp"):
        if cam.get(k):
            entry[k] = cam[k]

    if not reachable(ip):
        entry["enabled"] = False
        entry["note"] = "unreachable at discovery time - no TCP connect on :80"
        entry["model"] = cam.get("model") or "UNKNOWN"
        return entry

    context = browser.new_context(
        http_credentials={"username": USER, "password": PASSWORD},
        ignore_https_errors=True,
    )
    try:
        page = context.new_page()
        open_setup(page, ip)
        info = scrape_system_info(page)
        # QC data for the certification record. Each is best-effort: a camera
        # missing one page should still yield everything else.
        # Per-sensor firmware lives on System Information, separate from the
        # main firmware version - worth recording for a QC certificate.
        sensors = info.get("Sensor version")
        if sensors:
            # Rows read "Sensor 1<tab>2025.06.30_A15.3.3". Every camera lists
            # three slots regardless of how many sensors it has, so keep only
            # the ones actually reporting a version - bare labels are noise.
            populated = []
            for line in sensors.splitlines():
                parts = [p.strip() for p in re.split(r"\t+", line) if p.strip()]
                if len(parts) >= 2:
                    populated.append(f"{parts[0]}: {parts[1]}")
            if populated:
                entry["sensor_versions"] = populated

        for key, fn in (("firmware", lambda: scrape_firmware(page)),
                        ("plugins", lambda: scrape_plugins(page)),
                        ("licenses", lambda: scrape_licenses(page)),
                        ("cloud_state", lambda: scrape_cloud_state(page))):
            try:
                entry[key] = fn()
            except Exception as e:
                entry[key] = None
                entry.setdefault("warnings", []).append(f"{key}: {type(e).__name__}")
        entry["enabled"] = True
        entry["model"] = info.get("Model name") or cam.get("model") or "UNKNOWN"
        entry["manufacturer"] = info.get("Manufacturer") or "UNKNOWN"
        entry["branding"] = branding_of(info.get("Manufacturer"))
        if entry["branding"] != "soterix":
            # These cameras are built by VCA and branded for Soterix, and the
            # lab also holds unbranded VCA units. A unit still reporting the
            # OEM name is usually not a C2C target, but early branded
            # iterations exist - so flag for a human rather than decide.
            entry["enabled"] = False
            entry["note"] = (
                f"reports manufacturer '{entry['manufacturer']}', not "
                f"'{SOTERIX_MANUFACTURER}'. Confirm whether this is an OEM lab "
                f"unit or an early Soterix-branded iteration, then set "
                f"enabled: true if it should be certified."
            )

        # Lens count drives the multi-lens licence assertions, so read it from
        # the device rather than inferring it from the model name.
        lenses = probe_lens_count(ip)
        if lenses:
            entry["lens_count"] = lenses
            entry["lens_count_source"] = "rtsp"
        else:
            # Leave the caller's assumption in place but make it explicit that
            # nothing verified it - a multi-sensor recorded as single-lens
            # would silently assert the wrong licence count.
            entry["lens_count_source"] = "ASSUMED - not verified"
            entry.setdefault("warnings", []).append(
                "lens count NOT verified: RTSP on :554 did not answer, so "
                "lens_count is an assumption. Re-run once RTSP is up.")
        entry["max_resolution"] = info.get("Max resolution") or "UNKNOWN"
        # "30 fps" -> 30
        fr = (info.get("Max framerate") or "").split()
        entry["max_framerate"] = int(fr[0]) if fr and fr[0].isdigit() else None
        if info.get("Serial number"):
            entry["serial"] = info["Serial number"]
        if info.get("MAC address") and not entry.get("mac"):
            entry["mac"] = info["MAC address"]
        if info.get("ONVIF"):
            # The page renders "Version: 24.06 Profile: S, T, M"; the test
            # interpolates this into /Version.*{v}.*Profile/, so store just
            # the version number, not the whole sentence.
            m = re.search(r"(\d+\.\d+)", info["ONVIF"])
            entry["onvif_version"] = m.group(1) if m else info["ONVIF"]
            profiles = re.search(r"Profile:\s*(.+)$", info["ONVIF"])
            if profiles:
                entry["onvif_profiles"] = profiles.group(1).strip()
        # Prefer the identity the device reports over the inventory guess.
        if entry.get("serial"):
            entry["id"] = slug(entry.get("model", ""), entry["serial"])
        entry["features"] = {
            "audio": info.get("Audio"),
            "optical_zoom": info.get("Optical zoom"),
            "digital_zoom": info.get("Digital zoom"),
            "ptz": info.get("PTZ"),
            "ai": info.get("AI"),
            "alarm_in": info.get("Alarm in"),
            "relay_out": info.get("Relay out"),
            "cds": info.get("Photo resistor(CDS)"),
        }
        entry["_raw"] = info
    except Exception as e:
        entry["enabled"] = False
        entry["note"] = f"reachable but discovery failed: {type(e).__name__}: {e}"
        entry["model"] = cam.get("model") or "UNKNOWN"
    finally:
        context.close()
    return entry


def _rtsp_digest(method: str, uri: str, challenge: str) -> str:
    """Build an RTSP Digest Authorization header."""
    d = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    realm, nonce, qop = d.get("realm", ""), d.get("nonce", ""), d.get("qop")
    ha1 = hashlib.md5(f"{USER}:{realm}:{PASSWORD}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    if qop:
        nc, cnonce = "00000001", "abcdef01"
        resp = hashlib.md5(
            f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode()).hexdigest()
        return (f'Digest username="{USER}", realm="{realm}", nonce="{nonce}", '
                f'uri="{uri}", response="{resp}", qop=auth, nc={nc}, '
                f'cnonce="{cnonce}"')
    resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
    return (f'Digest username="{USER}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp}"')


def rtsp_describe(ip: str, path: str, timeout: float = 4.0) -> int | None:
    """RTSP status for DESCRIBE of one stream path, or None if unreachable."""
    uri = f"rtsp://{ip}:554/{path}"
    try:
        sock = socket.create_connection((ip, 554), timeout=timeout)
        sock.settimeout(timeout)
        with sock:
            sock.sendall(f"DESCRIBE {uri} RTSP/1.0\r\nCSeq: 1\r\n"
                         f"Accept: application/sdp\r\n\r\n".encode())
            resp = sock.recv(4096).decode("utf-8", "replace")
            code = int(re.search(r"RTSP/1\.0 (\d+)", resp).group(1))
            if code == 401:
                ch = re.search(r"WWW-Authenticate:\s*(Digest.*)", resp, re.I)
                if ch:
                    auth = _rtsp_digest("DESCRIBE", uri, ch.group(1))
                    sock.sendall(f"DESCRIBE {uri} RTSP/1.0\r\nCSeq: 2\r\n"
                                 f"Authorization: {auth}\r\n"
                                 f"Accept: application/sdp\r\n\r\n".encode())
                    resp = sock.recv(8192).decode("utf-8", "replace")
                    code = int(re.search(r"RTSP/1\.0 (\d+)", resp).group(1))
            return code
    except Exception:
        return None


def probe_lens_count(ip: str, max_lenses: int = 8) -> int:
    """Count a camera's lenses by enumerating its RTSP stream paths.

    Streams are addressed as channel{lens}_{stream}: a single-lens camera
    serves channel1_1 only, a four-lens multi-sensor serves channel1_1
    through channel4_1. Note that the bare channel{N} form counts *streams*
    (a one-lens camera answers channel1..3 for its three encoder streams), so
    it must not be used for this.

    Returns 0 when RTSP is unavailable - the caller should treat that as
    "unknown", not as "no lenses".
    """
    count = 0
    for i in range(1, max_lenses + 1):
        if rtsp_describe(ip, f"channel{i}_1") == 200:
            count += 1
        else:
            break
    return count


def arp_macs() -> dict:
    """Map IP -> MAC from the OS ARP cache (populated by the scan itself)."""
    macs: dict[str, str] = {}
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                             timeout=20).stdout
    except Exception:
        return macs
    for line in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F][0-9a-fA-F][-:]"
                      r"(?:[0-9a-fA-F]{2}[-:]){4}[0-9a-fA-F]{2})", line)
        if m:
            macs[m.group(1)] = m.group(2).upper().replace("-", ":")
    return macs


def looks_like_camera(ip: str) -> bool:
    """True if the host answers /cgi-bin/index.cgi with a camera auth challenge.

    Must be a 401/403 carrying a WWW-Authenticate header. A plain 200 is not
    enough: the NexaiQ application servers run an SPA whose nginx returns 200
    for every path, so accepting 200 classified 51 hosts as cameras when the
    subnet holds roughly 29.
    """
    try:
        urllib.request.urlopen(f"http://{ip}/cgi-bin/index.cgi", timeout=4)
        return False  # 200 on a CGI path with no auth - an SPA catch-all
    except urllib.error.HTTPError as e:
        if e.code not in (401, 403):
            return False
        return bool(e.headers.get("WWW-Authenticate"))
    except Exception:
        return False


# Cameras built by VCA and branded for Soterix report this manufacturer. The
# lab also holds unbranded VCA units, which are NOT C2C test targets - the
# System Information "Manufacturer" field is what separates them, since both
# share the same OEM MAC prefix.
SOTERIX_MANUFACTURER = "SOTERIX SYSTEMS"


def branding_of(manufacturer: str | None) -> str:
    """Classify a discovered camera as Soterix-branded or not."""
    if not manufacturer:
        return "unknown"
    return ("soterix" if manufacturer.strip().upper() == SOTERIX_MANUFACTURER
            else "unbranded")


def scan_subnet(cidr: str) -> list[dict]:
    """Find cameras on a /24 without being told their addresses.

    This is the mode that matters for order batches: new devices arrive with
    DHCP addresses nobody has written down, so the tool has to go looking.
    """
    base = cidr.rsplit(".", 1)[0] if "/" not in cidr else cidr.split("/")[0].rsplit(".", 1)[0]
    hosts = [f"{base}.{i}" for i in range(1, 255)]
    print(f"scanning {base}.1-254 for cameras on :80 ...")

    def probe(ip):
        try:
            with socket.create_connection((ip, 80), timeout=PROBE_TIMEOUT):
                return ip
        except OSError:
            return None

    with ThreadPoolExecutor(max_workers=64) as ex:
        live = [r for r in ex.map(probe, hosts) if r]
    print(f"  {len(live)} host(s) listening on :80")

    with ThreadPoolExecutor(max_workers=16) as ex:
        cams = [ip for ip, ok in zip(live, ex.map(looks_like_camera, live), strict=False) if ok]
    print(f"  {len(cams)} look like cameras\n")

    macs = arp_macs()
    return [{"ip": ip, "mac": macs.get(ip, ""), "channels": 1} for ip in cams]


def load_inventory(path: Path) -> list[dict]:
    """Read model,serial,ip,mac,rtsp rows. Repeated IPs collapse to one camera
    with a channel count (multi-lens devices list one RTSP URL per lens)."""
    cams: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ip = (row.get("ip") or "").strip()
            if not ip:
                continue
            cam = cams.setdefault(ip, {
                "ip": ip,
                "model": (row.get("model") or "").strip(),
                "serial": (row.get("serial") or "").strip(),
                "mac": (row.get("mac") or "").strip(),
                "channels": 0,
            })
            if (row.get("rtsp") or "").strip():
                cam["channels"] += 1
    return list(cams.values())


def one_line(text: str, limit: int = 160) -> str:
    """Collapse text to a single line safe to emit as a YAML comment.

    Playwright errors are multi-line ("...Timeout exceeded.\\nCall log:\\n  -
    navigating to ..."). Emitted verbatim after a '#', only the first line is
    commented - the rest lands at column 0, where "Call log:" reads as a new
    top-level key and silently truncates the cameras list.
    """
    flat = " ".join(str(text).split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def to_yaml(entries: list[dict]) -> str:
    """Render the registry. Written by hand so the output keeps the comments
    and field order a human reader expects."""
    out = [
        "# C2C Camera Registry - GENERATED",
        f"# Produced by tools/discover_c2c_cameras.py on {datetime.now():%Y-%m-%d %H:%M}.",
        "#",
        "# Values under each camera were read from the device's",
        "# Setup > System Information page, not typed by hand. Re-run the tool",
        "# after the lab re-addresses or swaps hardware rather than editing here:",
        "#     python tools/discover_c2c_cameras.py --inventory <inventory.csv>",
        "#",
        "# enabled: false marks a camera that did not answer at discovery time,",
        "# or one whose branding needs confirming. Set it true once resolved and",
        "# re-run discovery to fill in the specs.",
        "#",
        "# Credentials are NOT stored here. The camera login comes from",
        "# C2C_CAMERA_USER / C2C_CAMERA_PASS (see .env.template).",
        "",
        "cameras:",
    ]
    for e in entries:
        out.append(f"  - id: {e['id']}")
        out.append(f"    enabled: {str(e.get('enabled', False)).lower()}")
        out.append(f"    ip: {e['ip']}")
        out.append(f"    user: {e['user']}")
        # No password here on purpose - conftest injects it from
        # C2C_CAMERA_PASS so the credential is not repeated once per camera
        # in a file that ships to both remotes.
        out.append(f"    model: {e.get('model', 'UNKNOWN')}")
        for key in ("serial", "mac"):
            if e.get(key):
                out.append(f"    {key}: {e[key]}")
        if e.get("manufacturer"):
            out.append(f"    manufacturer: {e['manufacturer']}")
        if e.get("max_resolution"):
            out.append(f"    max_resolution: {e['max_resolution']}")
        if e.get("max_framerate") is not None:
            out.append(f"    max_framerate: {e['max_framerate']}")
        lenses = e.get("lens_count", 1)
        src = e.get("lens_count_source")
        out.append(f"    lens_count: {lenses}" + (f"   # {one_line(src)}" if src and src != "rtsp" else ""))
        out.append(f"    multi_lens: {str(lenses > 1).lower()}")
        if lenses > 1:
            out.append(f"    total_lenses: {lenses}")
        out.append(f"    expected_license: {e.get('expected_license', 'ProAI 1ch')}")
        out.append(f"    expected_license_count: {e.get('expected_license_count', lenses)}")
        if e.get("onvif_version"):
            out.append(f'    onvif_version: "{e["onvif_version"]}"')
        if e.get("onvif_profiles"):
            out.append(f'    onvif_profiles: "{e["onvif_profiles"]}"')
        if e.get("cloud_state"):
            out.append(f"    cloud_state: {e['cloud_state']}   # as discovered")
        if e.get("sensor_versions"):
            out.append("    sensor_versions:   # as discovered")
            for s in e["sensor_versions"]:
                out.append(f"      - \"{one_line(s, 60)}\"")
        for key in ("firmware", "plugins", "licenses"):
            val = e.get(key)
            if not val:
                continue
            if key == "firmware":
                ver = "; ".join(str(v) for v in val.values())
                out.append(f'    firmware: "{ver}"   # as discovered')
            elif key == "plugins":
                out.append("    plugins:   # as discovered")
                for p in val:
                    out.append(f"      - name: {p.get('name')}")
                    out.append(f"        version: \"{p.get('version')}\"")
                    out.append(f"        status: {p.get('status')}")
            else:
                names = ", ".join(x.get("license", "") for x in val) or "none"
                out.append(f"    # licenses currently activated: {one_line(names)}")
        if e.get("features") and any(e["features"].values()):
            out.append("    features:")
            for k, v in e["features"].items():
                if v:
                    out.append(f"      {k}: {v}")
        if e.get("note"):
            out.append(f"    # {one_line(e['note'])}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--scan", metavar="CIDR",
                     help="Find cameras on a subnet, e.g. 10.2.0.0/24. Use this "
                          "for an order batch whose addresses nobody knows yet.")
    src.add_argument("--inventory", type=Path, help="CSV: model,serial,ip,mac,rtsp")
    src.add_argument("--ips", nargs="+", help="Explicit IP list")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="Print, do not write")
    ap.add_argument("--json", type=Path, help="Also dump raw scrape results here")
    args = ap.parse_args()

    if args.scan:
        cams = scan_subnet(args.scan)
    elif args.inventory:
        cams = load_inventory(args.inventory)
    else:
        cams = [{"ip": ip, "channels": 1} for ip in args.ips]
    print(f"discovering {len(cams)} camera(s) as {USER}...\n")

    from playwright.sync_api import sync_playwright

    entries = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for cam in sorted(cams, key=lambda c: [int(p) for p in c["ip"].split(".")]):
                cam["lens_count"] = max(1, cam.get("channels", 1))
                entry = discover_one(browser, cam)
                entry["lens_count"] = cam["lens_count"]
                entry["expected_license_count"] = cam["lens_count"]
                state = "OK " if entry.get("enabled") else "SKIP"
                print(f"  [{state}] {entry['ip']:12} {entry.get('model','?'):18} "
                      f"{entry.get('max_resolution','') or ''} "
                      f"{entry.get('note','')}")
                entries.append(entry)
        finally:
            browser.close()

    ok = sum(1 for e in entries if e.get("enabled"))
    print(f"\ndiscovered {ok}/{len(entries)} reachable")

    if args.json:
        args.json.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
        print(f"raw results -> {args.json}")

    for e in entries:
        e.pop("_raw", None)
    yaml_text = to_yaml(entries)

    if args.dry_run:
        print("\n--- would write ---\n")
        print(yaml_text)
    else:
        args.out.write_text(yaml_text, encoding="utf-8")
        print(f"registry -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
