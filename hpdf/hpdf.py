# mypy: disable-error-code="no-untyped-call,no-untyped-def"
import argparse
import atexit
import base64
import os
import os.path
import platform
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Optional, List

import requests
from requests import Response
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

__version__ = "0.0.1"

from webdriver_manager.core.os_manager import OperationSystemManager, ChromeType

# HTML2PDF.js prints unicode symbols to console. The following makes it work on
# Windows which otherwise complains:
# UnicodeEncodeError: 'charmap' codec can't encode characters in position 129-130: character maps to <undefined>
# How to make python 3 print() utf8
# https://stackoverflow.com/questions/3597480/how-to-make-python-3-print-utf8
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf8", closefd=False)


def send_http_get_request(url, params=None, **kwargs) -> Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        print(  # noqa: T201
            f"html2pdf: sending GET request attempt {attempt}: {url}"
        )
        try:
            return requests.get(url, params, timeout=(5, 5), **kwargs)
        except requests.exceptions.ConnectTimeout as connect_timeout_:
            last_error = connect_timeout_
        except requests.exceptions.ReadTimeout as read_timeout_:
            last_error = read_timeout_
        except Exception as exception_:
            raise AssertionError(
                "html2pdf: unknown exception", exception_
            ) from None
    print(  # noqa: T201
        f"html2pdf: "
        f"failed to get response for URL: {url} with error: {last_error}"
    )


def get_chrome_version():
    os_manager = OperationSystemManager(os_type=None)
    version = os_manager.get_browser_version_from_os(ChromeType.GOOGLE)
    return version


def download_chromedriver(chrome_major_version, os_type: str, path_to_driver_cache_dir, path_to_cached_chrome_driver):
    url = f"https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
    response = send_http_get_request(url).json()

    matching_versions = [item for item in response['versions'] if
                         item['version'].startswith(chrome_major_version)]

    if not matching_versions:
        raise Exception(
            f"No compatible ChromeDriver found for Chrome version {chrome_major_version}")

    latest_version = (matching_versions[-1])

    driver_url: str
    chrome_downloadable_versions = latest_version["downloads"]["chromedriver"]
    for chrome_downloadable_version_ in chrome_downloadable_versions:
        print(chrome_downloadable_version_)
        if chrome_downloadable_version_["platform"] == os_type:
            driver_url = chrome_downloadable_version_["url"]
            break
    else:
        raise RuntimeError(f"Could not find a downloadable URL from downloadable versions: {chrome_downloadable_versions}")

    print(f"html2pdf: downloading ChromeDriver from: {driver_url}")
    response = send_http_get_request(driver_url)

    Path(path_to_driver_cache_dir).mkdir(parents=True, exist_ok=True)
    zip_path = os.path.join(path_to_driver_cache_dir, "chromedriver.zip")
    print(f"html2pdf: saving downloaded ChromeDriver to path: {zip_path}")
    with open(zip_path, 'wb') as file:
        file.write(response.content)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(path_to_driver_cache_dir)

    if platform.system() == "Windows":
        path_to_cached_chrome_driver += ".exe"
    print(f"html2pdf: ChromeDriver downloaded to: {path_to_cached_chrome_driver}")
    return path_to_cached_chrome_driver


def find_driver(path_to_cache_dir: str):
    chrome_version = get_chrome_version()
    chrome_major_version = chrome_version.split('.')[0]

    print(f"html2pdf: Installed Chrome version: {chrome_version}")

    system_map = {
        "Windows": "win32",
        "Darwin": "mac-arm64" if platform.machine() == "arm64" else "mac-x64",
        "Linux": "linux64"
    }
    os_type = system_map[platform.system()]
    print(f"html2pdf: OS system: {platform.system()}, OS type: {os_type}.")

    path_to_cached_chrome_driver_dir = os.path.join(
        path_to_cache_dir, chrome_major_version
    )
    path_to_cached_chrome_driver = os.path.join(
        path_to_cached_chrome_driver_dir, f"chromedriver-{os_type}", "chromedriver"
    )

    if os.path.isfile(path_to_cached_chrome_driver):
        print(  # noqa: T201
            f"html2pdf: ChromeDriver exists in the local cache: "
            f"{path_to_cached_chrome_driver}"
        )
        return path_to_cached_chrome_driver
    print(  # noqa: T201
        f"html2pdf: ChromeDriver does not exist in the local cache: "
        f"{path_to_cached_chrome_driver}"
    )

    path_to_downloaded_chrome_driver = download_chromedriver(chrome_major_version, os_type, path_to_cached_chrome_driver_dir, path_to_cached_chrome_driver)
    assert os.path.isfile(path_to_downloaded_chrome_driver)
    os.chmod(path_to_downloaded_chrome_driver, 0o755)

    return path_to_downloaded_chrome_driver


def get_inches_from_millimeters(mm: float) -> float:
    return mm / 25.4


def get_pdf_from_html(driver, url) -> bytes:
    print(f"html2pdf: opening URL with ChromeDriver: {url}")  # noqa: T201

    driver.get(url)

    # https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-printToPDF
    calculated_print_options = {
        "landscape": False,
        "displayHeaderFooter": False,
        "printBackground": True,
        # This is an experimental feature that generates a document outline
        # (table of contents).
        "generateDocumentOutline": True,
        # Whether to prefer page size as defined by css. Defaults to
        # false, in which case the content will be scaled to fit the paper size.
        "preferCSSPageSize": True,
        # Paper width in inches. Defaults to 8.5 inches.
        "paperWidth": get_inches_from_millimeters(210),
        # Paper height in inches. Defaults to 11 inches.
        "paperHeight": get_inches_from_millimeters(297),
        # WIP: Changing the margin settings has no effect.
        # Top margin in inches. Defaults to 1cm (~0.4 inches).
        "marginTop": get_inches_from_millimeters(12),
        # Bottom margin in inches. Defaults to 1cm (~0.4 inches).
        "marginBottom": get_inches_from_millimeters(12),
        # Left margin in inches. Defaults to 1cm (~0.4 inches).
        "marginLeft": get_inches_from_millimeters(21),
        # Right margin in inches. Defaults to 1cm (~0.4 inches).
        "marginRight": get_inches_from_millimeters(21),
    }

    class Done(Exception): pass

    datetime_start = datetime.today()

    logs = None
    try:
        while True:
            logs = driver.get_log("browser")
            for entry_ in logs:
                if "HTML2PDF4DOC time" in entry_["message"]:
                    print("html2pdf: success: html2pdf.js completed its job.")
                    raise Done
            if (datetime.today() - datetime_start).total_seconds() > 60:
                raise TimeoutError
            sleep(0.5)
    except Done:
        pass
    except TimeoutError:
        print("error: could not receive a successful completion status from html2pdf.js.")
        sys.exit(1)

    print("html2pdf: JS logs from the print session:")  # noqa: T201
    print('"""')  # noqa: T201
    for entry in logs:
        print(entry)  # noqa: T201
    print('"""')  # noqa: T201

    print("html2pdf: executing print command with ChromeDriver.")  # noqa: T201
    result = driver.execute_cdp_cmd("Page.printToPDF", calculated_print_options)

    data = base64.b64decode(result["data"])
    return data


def create_webdriver(chromedriver: Optional[str], path_to_cache_dir: Optional[str]):
    print("html2pdf: creating ChromeDriver service.", flush=True)  # noqa: T201
    if chromedriver is None:
        path_to_chrome = find_driver(path_to_cache_dir)
    else:
        path_to_chrome = chromedriver
    print(f"html2pdf: ChromeDriver available at path: {path_to_chrome}")  # noqa: T201

    service = Service(path_to_chrome)

    webdriver_options = Options()
    webdriver_options.add_argument("start-maximized")
    webdriver_options.add_argument("disable-infobars")
    webdriver_options.add_argument("--headless")
    webdriver_options.add_argument("--disable-extensions")

    webdriver_options.add_experimental_option("useAutomationExtension", False)
    webdriver_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"]
    )

    # Enable the capturing of everything in JS console.
    webdriver_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    print("html2pdf: creating ChromeDriver.", flush=True)  # noqa: T201

    driver = webdriver.Chrome(
        options=webdriver_options,
        service=service,
    )
    driver.set_page_load_timeout(60)

    return driver


def main():
    parser = argparse.ArgumentParser(description="html2pdf printer script.")
    parser.add_argument(
        "--chromedriver",
        type=str,
        help="Optional chromedriver path. Downloaded if not given.",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        help="Optional path to a cache directory whereto the ChromeDriver is downloaded.",
    )
    parser.add_argument("paths", nargs='+', help="Paths to input HTML file.")
    args = parser.parse_args()

    paths: List[str] = args.paths

    path_to_cache_dir: str = (
        args.cache_dir
        if args.cache_dir is not None
        else (
            os.path.join(
                Path.home(), ".hpdf", "chromedriver"
            )
        )
    )
    Path(path_to_cache_dir).mkdir(parents=True, exist_ok=True)
    driver = create_webdriver(args.chromedriver, path_to_cache_dir)

    @atexit.register
    def exit_handler():
        print("html2pdf: exit handler: quitting the ChromeDriver.")  # noqa: T201
        driver.quit()

    for separate_path_pair_ in paths:
        path_to_input_html, path_to_output_pdf = separate_path_pair_.split(":")
        assert os.path.isfile(path_to_input_html), path_to_input_html

        path_to_output_pdf_dir = os.path.dirname(path_to_output_pdf)
        Path(path_to_output_pdf_dir).mkdir(parents=True, exist_ok=True)

        url = Path(os.path.abspath(path_to_input_html)).as_uri()

        pdf_bytes = get_pdf_from_html(driver, url)
        with open(path_to_output_pdf, "wb") as f:
            f.write(pdf_bytes)


if __name__ == "__main__":
    main()
