import tempfile
from typing import Any, Dict, Optional

import pytest
import requests

import html2pdf4doc.main as main_module
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


def test_send_http_get_request_uses_ssl_verification_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: Dict[str, Any] = {}

    def fake_get(*args: Any, **kwargs: Any) -> requests.Response:
        del args
        captured_kwargs.update(kwargs)
        return requests.Response()

    monkeypatch.setattr("html2pdf4doc.main.requests.get", fake_get)

    ChromeDriverManager.send_http_get_request("https://example.com")

    assert captured_kwargs["verify"] is True


def test_send_http_get_request_can_disable_ssl_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: Dict[str, Any] = {}

    def fake_get(*args: Any, **kwargs: Any) -> requests.Response:
        del args
        captured_kwargs.update(kwargs)
        return requests.Response()

    monkeypatch.setattr("html2pdf4doc.main.requests.get", fake_get)

    ChromeDriverManager.send_http_get_request(
        "https://example.com", verify_ssl=False
    )

    assert captured_kwargs["verify"] is False


def test_send_http_get_request_warns_once_when_ssl_check_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> requests.Response:
        del args, kwargs
        return requests.Response()

    monkeypatch.setattr("html2pdf4doc.main.requests.get", fake_get)
    monkeypatch.setattr(
        main_module, "SSL_CHECK_DISABLED_WARNING_PRINTED", False
    )

    ChromeDriverManager.send_http_get_request(
        "https://example.com", verify_ssl=False
    )
    ChromeDriverManager.send_http_get_request(
        "https://example.com", verify_ssl=False
    )

    captured = capsys.readouterr()
    assert captured.err.count("--disable-ssl-check") == 1


def test_send_http_get_request_does_not_warn_when_ssl_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> requests.Response:
        del args, kwargs
        return requests.Response()

    monkeypatch.setattr("html2pdf4doc.main.requests.get", fake_get)
    monkeypatch.setattr(
        main_module, "SSL_CHECK_DISABLED_WARNING_PRINTED", False
    )

    ChromeDriverManager.send_http_get_request("https://example.com")

    captured = capsys.readouterr()
    assert captured.err == ""


def test_send_http_get_request_reports_ssl_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(*args: Any, **kwargs: Any) -> requests.Response:
        del args, kwargs
        raise requests.exceptions.SSLError("certificate verify failed")

    monkeypatch.setattr("html2pdf4doc.main.requests.get", fake_get)

    with pytest.raises(RuntimeError) as exc_info:
        ChromeDriverManager.send_http_get_request("https://example.com")

    assert "--disable-ssl-check" in str(exc_info.value)
