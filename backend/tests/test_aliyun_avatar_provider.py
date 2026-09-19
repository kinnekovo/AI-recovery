import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from app.integrations.aliyun_avatar import provider


class AliyunAvatarProviderTest(unittest.TestCase):
    def test_disabled_feature_never_counts_as_configured(self) -> None:
        with patch.object(provider, "get_settings", return_value=SimpleNamespace(aliyun_avatar_enabled=False, aliyun_avatar_instance_id="instance")):
            self.assertFalse(provider.is_configured())

    def test_portrait_upload_is_a_9_by_16_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            Image.new("RGB", (1600, 800), "white").save(source)
            rendered = provider._portrait_9x16(str(source))
            try:
                with Image.open(rendered) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.size, (720, 1280))
            finally:
                rendered.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
