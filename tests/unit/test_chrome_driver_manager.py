import io
import os
import subprocess
import sys
import tempfile
import zipfile
from typing import Any, Dict, Optional

import pytest
import requests

import html2pdf4doc.main as main_module
from html2pdf4doc.main import ChromeDriverManager, HPDError, HPDExitCode


class FailingChromeDriverManager(ChromeDriverManager):
    @staticmethod
    def get_chrome_version(
        chrome_binary: Optional[str] = None,
    ) -> Optional[str]:
        del chrome_binary
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


def test_get_chrome_version_probes_explicit_binary_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        del kwargs
        assert args[0] == ["/opt/my-chrome/chrome", "--version"]
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="Google Chrome for Testing 152.0.7977.82\n",
        )

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError(
            "OS auto-detection must not run when --chrome-binary is given"
        )

    monkeypatch.setattr("html2pdf4doc.main.subprocess.run", fake_run)
    monkeypatch.setattr(
        "html2pdf4doc.main.OperationSystemManager.get_browser_version_from_os",
        fail_if_called,
    )

    version = ChromeDriverManager.get_chrome_version("/opt/my-chrome/chrome")

    assert version == "152.0.7977.82"


def test_get_chrome_version_returns_none_when_binary_is_unusable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise FileNotFoundError("no such file")

    monkeypatch.setattr("html2pdf4doc.main.subprocess.run", fake_run)

    version = ChromeDriverManager.get_chrome_version("/does/not/exist")

    assert version is None


def test_get_chrome_driver_reports_the_bad_binary_path_when_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise FileNotFoundError("no such file")

    monkeypatch.setattr("html2pdf4doc.main.subprocess.run", fake_run)

    chrome_driver_manager = ChromeDriverManager()

    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(HPDError) as exc_info:
            chrome_driver_manager.get_chrome_driver(
                tmpdir, chrome_binary="/does/not/exist"
            )

    assert exc_info.value.exit_code == HPDExitCode.COULD_NOT_FIND_CHROME
    assert "/does/not/exist" in str(exc_info.value)


def _make_chromedriver_zip(file_names: Dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for file_name_, content_ in file_names.items():
            zip_file.writestr(file_name_, content_)
    return buffer.getvalue()


def _get_cache_paths(path_to_cache_dir: str) -> Dict[str, str]:
    path_to_driver_cache_dir = os.path.join(path_to_cache_dir, "151")
    return {
        "driver_cache_dir": path_to_driver_cache_dir,
        "driver": os.path.join(
            path_to_driver_cache_dir, "chromedriver-linux64", "chromedriver"
        ),
    }


def test_publish_chromedriver_to_empty_cache() -> None:
    zip_content = _make_chromedriver_zip(
        {"chromedriver-linux64/chromedriver": b"downloaded"}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _get_cache_paths(tmpdir)

        ChromeDriverManager._publish_chromedriver(
            zip_content, paths["driver_cache_dir"], paths["driver"]
        )

        with open(paths["driver"], "rb") as driver_file:
            assert driver_file.read() == b"downloaded"
        if sys.platform != "win32":
            assert os.access(paths["driver"], os.X_OK)
        # The temporary download folder is removed.
        assert os.listdir(paths["driver_cache_dir"]) == ["chromedriver-linux64"]


def test_publish_chromedriver_keeps_driver_cached_by_another_process() -> None:
    """
    Another process has cached the ChromeDriver while this process was
    downloading it. The cached ChromeDriver must stay untouched because the
    other process may be running it.
    """

    zip_content = _make_chromedriver_zip(
        {"chromedriver-linux64/chromedriver": b"downloaded"}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _get_cache_paths(tmpdir)
        os.makedirs(os.path.dirname(paths["driver"]))
        with open(paths["driver"], "wb") as driver_file:
            driver_file.write(b"cached by another process")

        ChromeDriverManager._publish_chromedriver(
            zip_content, paths["driver_cache_dir"], paths["driver"]
        )

        with open(paths["driver"], "rb") as driver_file:
            assert driver_file.read() == b"cached by another process"
        assert os.listdir(paths["driver_cache_dir"]) == ["chromedriver-linux64"]


def test_publish_chromedriver_replaces_leftover_folder_without_driver() -> None:
    zip_content = _make_chromedriver_zip(
        {"chromedriver-linux64/chromedriver": b"downloaded"}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _get_cache_paths(tmpdir)
        path_to_driver_dir = os.path.dirname(paths["driver"])
        os.makedirs(path_to_driver_dir)
        with open(
            os.path.join(path_to_driver_dir, "LICENSE.chromedriver"), "wb"
        ) as license_file:
            license_file.write(b"leftover")

        ChromeDriverManager._publish_chromedriver(
            zip_content, paths["driver_cache_dir"], paths["driver"]
        )

        with open(paths["driver"], "rb") as driver_file:
            assert driver_file.read() == b"downloaded"
        assert os.listdir(path_to_driver_dir) == ["chromedriver"]


def test_publish_chromedriver_raises_when_archive_has_no_driver() -> None:
    zip_content = _make_chromedriver_zip(
        {"chromedriver-linux64/LICENSE.chromedriver": b"license"}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        paths = _get_cache_paths(tmpdir)

        with pytest.raises(RuntimeError) as exc_info:
            ChromeDriverManager._publish_chromedriver(
                zip_content, paths["driver_cache_dir"], paths["driver"]
            )

        assert "chromedriver-linux64/chromedriver" in str(exc_info.value)
        assert os.listdir(paths["driver_cache_dir"]) == []
