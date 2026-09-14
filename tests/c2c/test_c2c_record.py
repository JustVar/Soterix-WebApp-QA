"""C2C Hardware Tests - Recording management and SD card storage.

Read-only: the test reads the RECORD pages and changes nothing on the
camera.
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage

# measured 09/14/2026 on BC-5V-1 10.2.0.137 and MS-20V-1 10.2.0.135; the
# other models by the test's pass on every unit (register row 58). The
# recorded devices and cards follow the model's
# sd_cards in tests/data/c2c_models.yaml: two devices per card, RECORDn on
# card (n mod cards) + 1.
TARGET_STREAM_OPTIONS = ["None", "Main stream", "Sub stream"]
# a storage figure as the page prints it: '476.5GB'
SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMGT]B)$")
UNIT_GB = {"KB": 1 / 1024 / 1024, "MB": 1 / 1024, "GB": 1.0, "TB": 1024.0}


def _gigabytes(figure: str) -> float:
    """'476.5GB' -> 476.5; raises on a figure the page never prints."""
    match = SIZE_RE.match(figure)
    assert match, f"not a storage figure: {figure!r}"
    return float(match.group(1)) * UNIT_GB[match.group(2)]


class TestC2CRecord:
    """Recording management and SD card storage pages."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_record_management_and_sd_card_status(self):
        """Verify recording management and SD card status.

        Steps:
        1. Open Setup > RECORD > MANAGEMENT.
           Expected: The RECORD MANAGEMENT page opens and the Target stream list offers None, Main stream and Sub stream.
        2. Read the Recorded devices table.
           Expected: Two recorded devices per SD card slot of the model are listed (RECORD0 and RECORD1 on one slot, RECORD0 to RECORD7 on four), each with File type MP4 and its own slot's card as Storage.
        3. Open RECORD > STORAGE and read the Storage list.
           Expected: Every SD card slot of the model is listed as mounted, with a size, a used percentage between 0 and 100, and an available space no larger than the size.
        """
        self.step_capture.mark(1, "Open RECORD > MANAGEMENT and read the Target stream list")
        self.camera.navigate_to_setup_section("RECORD")
        self.camera.navigate_to_setup_subsection("MANAGEMENT")
        expect(self.camera.heading("RECORD MANAGEMENT")).to_be_visible()
        # the select is found by an option it offers (page-object rule:
        # names and values differ by firmware, option texts do not)
        target_stream = self.camera.select_with_option("Main stream")
        expect(target_stream).to_be_visible()
        options = target_stream.locator("option").all_inner_texts()
        assert options == TARGET_STREAM_OPTIONS, (
            f"the Target stream list offers {options}, expected {TARGET_STREAM_OPTIONS}")

        self.step_capture.mark(2, "Read the Recorded devices table")
        slots = self.config["model_facts"].get("sd_cards")
        assert slots is not None, (
            f"tests/data/c2c_models.yaml gives no sd_cards for {self.config['model']}; measure and update the record")
        if slots == 0:
            pytest.skip(f"{self.config['model']} records no SD card slot (tests/data/c2c_models.yaml)")
        expected = {f"RECORD{n}": f"SD card {n % slots + 1}" for n in range(2 * slots)}
        rows = self.camera.wait_for_table_rows()
        # a row reads [name, enabled mark, file type, storage, continuous]
        devices = {row[0]: row for row in rows if row[0].startswith("RECORD")}
        assert sorted(devices) == sorted(expected), (
            f"the Recorded devices table lists {sorted(devices)}, expected {sorted(expected)} for {slots} card(s)")
        for name, row in devices.items():
            assert len(row) >= 4, f"{name} reads {row}; expected name, enabled, file type and storage cells"
            assert row[2] == "MP4", f"{name} reads {row}; expected File type MP4"
            assert row[3] == expected[name], f"{name} reads {row}; expected Storage {expected[name]}"

        self.step_capture.mark(3, "Open RECORD > STORAGE and read the Storage list")
        self.camera.navigate_to_setup_subsection("STORAGE")
        expect(self.camera.heading("STORAGE CONFIGURATION")).to_be_visible()
        rows = self.camera.wait_for_table_rows()
        # a row reads [name, mounted, size, used %, available, format]
        cards = {row[0]: row for row in rows if row[0].upper().startswith("SD CARD")}
        expected_cards = [f"SD card{n + 1}" for n in range(slots)]
        assert sorted(cards) == expected_cards, (
            f"{self.config['id']}: the Storage list names {sorted(cards)}, expected {expected_cards}")
        for name, row in cards.items():
            assert len(row) >= 5, f"{name} reads {row}; expected mounted, size, used and available cells"
            mounted, size, used, available = row[1:5]
            # a card that is not mounted is a device state for the lab, named here
            assert mounted == "Yes", (
                f"{self.config['id']}: {name} is not mounted ({row}); insert or format the card")
            assert used.endswith("%"), f"{name} used reads {used!r}, expected a percentage"
            assert 0 <= float(used.rstrip("%")) <= 100, f"{name} used reads {used!r}, expected 0-100%"
            assert _gigabytes(available) <= _gigabytes(size), (
                f"{name} available {available} exceeds its size {size}")
