import tempfile
from typing import Optional

import pytest

from html2pdf4doc.main import ChromeDriverManager, HPDError, HPDExitCode


class FailingChromeDriverManager(ChromeDriverManager):
    @staticmethod
    def get_chrome_version() -> Optional[str]:
        return None


def test_raises_error_when_cannot_detect_chrome() -> None:
    """
    This first unit test is not great but it is a good start anyway.
    """

    chrome_driver_manager = FailingChromeDriverManager()

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(Exception) as exc_info:
            _ = chrome_driver_manager.get_chrome_driver(tmpdir)

        assert exc_info.type is HPDError
        assert exc_info.value.exit_code == HPDExitCode.COULD_NOT_FIND_CHROME
