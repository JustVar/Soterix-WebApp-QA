"""Event Wall display tests (special local-access login) - HELD.

The live Event Wall is its own UI experience, separate from both the
regular app (Views/Events pages included) and the wall's admin
configuration surface (test_event_wall_config.py). Per Justin,
08/13/2026: a user with local access enabled logs in, selects a site,
and the wall appears - a different experience from the regular app.

Everything here holds as explicit skips until that special account is
provisioned for automation. Activating this suite needs:
- the local-access account's credentials in config/env (its own
  email/password env vars, never the regular QA account),
- the site-select entry flow probed and mapped,
- the wall's own markers measured (the regular app's locators do not
  apply to this UI).
"""
import pytest


class TestEventWallDisplay:
    """Held tests for the live Event Wall display experience."""

    @pytest.mark.ui
    @pytest.mark.event_wall
    @pytest.mark.event_wall_display
    def test_event_wall_event_images(self):
        """The live wall displays event images for the selected site."""
        # oracle: none by design - an explicit hold until the wall's
        # special local-access login is provisioned for automation
        pytest.skip(
            "The event wall display requires the special local-access "
            "login (log in, select a site, the wall appears); the "
            "regular QA account only covers configuration"
        )
