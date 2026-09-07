import unittest
from types import SimpleNamespace

from app.modules.consent.model import ConsentStatus
from app.modules.consent.service import is_confirmed_consent


class ConsentServiceTest(unittest.TestCase):
    def test_confirmed_consent_is_active(self) -> None:
        self.assertTrue(is_confirmed_consent(SimpleNamespace(consent_status=ConsentStatus.confirmed)))

    def test_revoked_or_missing_consent_is_not_active(self) -> None:
        self.assertFalse(is_confirmed_consent(SimpleNamespace(consent_status=ConsentStatus.revoked)))
        self.assertFalse(is_confirmed_consent(None))


if __name__ == "__main__":
    unittest.main()
