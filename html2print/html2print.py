# mypy: disable-error-code="no-untyped-call,no-untyped-def"
import argparse
import atexit
import base64
import os.path
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy
from time import sleep
from typing import Dict, List, Optional

import requests
from requests import Response
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.download_manager import WDMDownloadManager
from webdriver_manager.core.driver import Driver
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.core.file_manager import FileManager
from webdriver_manager.core.http import HttpClient
from webdriver_manager.core.os_manager import OperationSystemManager

__version__ = "0.0.3"

DEFAULT_CACHE_DIR = os.path.join(Path.home(), ".html2print", "chromedriver")

# HTML2PDF.js prints unicode symbols to console. The following makes it work on
# Windows which otherwise complains:
# UnicodeEncodeError: 'charmap' codec can't encode characters in position 129-130: character maps to <undefined>
# How to make python 3 print() utf8
# https://stackoverflow.com/questions/3597480/how-to-make-python-3-print-utf8
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf8", closefd=False)


class HTML2Print_HTTPClient(HttpClient):
    def get(self, url, params=None, **kwargs) -> Response:
        last_error: Optional[Exception] = None
        for attempt in range(1, 3):
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


class HTML2Print_CacheManager(DriverCacheManager):
    def __init__(self, file_manager: FileManager, path_to_cache_dir: str):
        super().__init__(file_manager=file_manager)
        self.path_to_cache_dir: str = path_to_cache_dir

    def find_driver(self, driver: Driver):
        path_to_cached_chrome_driver_dir = os.path.join(
            self.path_to_cache_dir, "chromedriver"
        )

        os_type = self.get_os_type()
        browser_type = driver.get_browser_type()
        browser_version = self._os_system_manager.get_browser_version_from_os(
            browser_type
        )
        assert browser_version is not None, browser_version

        path_to_cached_chrome_driver_dir = os.path.join(
            path_to_cached_chrome_driver_dir, browser_version, os_type
        )
        path_to_cached_chrome_driver = os.path.join(
            path_to_cached_chrome_driver_dir, "chromedriver"
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
        path_to_downloaded_chrome_driver = super().find_driver(driver)
        if path_to_downloaded_chrome_driver is None:
            print(  # noqa: T201
                f"html2pdf: could not get a downloaded ChromeDriver: "
                f"{path_to_cached_chrome_driver}"
            )
            return None

        print(  # noqa: T201
            f"html2pdf: saving chromedriver to StrictDoc's local cache: "
            f"{path_to_downloaded_chrome_driver} -> {path_to_cached_chrome_driver}"
        )
        Path(path_to_cached_chrome_driver_dir).mkdir(
            parents=True, exist_ok=True
        )
        copy(path_to_downloaded_chrome_driver, path_to_cached_chrome_driver)

        return path_to_cached_chrome_driver


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

    class Done(Exception):
        pass

    datetime_start = datetime.today()

    logs: List[Dict[str, str]] = []
    try:
        while True:
            logs = driver.get_log("browser")
            for entry_ in logs:
                if "HTML2PDF4DOC time" in entry_["message"]:
                    print("success: HTML2PDF completed its job.")  # noqa: T201
                    raise Done
            if (datetime.today() - datetime_start).total_seconds() > 60:
                raise TimeoutError
            sleep(0.5)
    except Done:
        pass
    except TimeoutError:
        print(  # noqa: T201
            "error: could not receive a successful completion status from HTML2PDF."
        )
        sys.exit(1)

    print("html2pdf: JS logs from the print session:")  # noqa: T201
    print('"""')  # noqa: T201
    for entry in logs:
        print(entry)  # noqa: T201
    print('"""')  # noqa: T201

    #
    # Execute Print command with ChromeDriver.
    #
    print("html2pdf: executing print command with ChromeDriver.")  # noqa: T201
    result = driver.execute_cdp_cmd("Page.printToPDF", calculated_print_options)

    data = base64.b64decode(result["data"])
    return data


def get_chrome_driver(path_to_cache_dir: str) -> str:
    cache_manager = HTML2Print_CacheManager(
        file_manager=FileManager(os_system_manager=OperationSystemManager()),
        path_to_cache_dir=path_to_cache_dir,
    )

    http_client = HTML2Print_HTTPClient()
    download_manager = WDMDownloadManager(http_client)
    path_to_chrome = ChromeDriverManager(
        download_manager=download_manager, cache_manager=cache_manager
    ).install()
    return path_to_chrome


def create_webdriver(chromedriver: Optional[str], path_to_cache_dir: str):
    if chromedriver is None:
        path_to_chrome = get_chrome_driver(path_to_cache_dir)
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
    # By default, all driver binaries are saved to user.home/.wdm folder.
    # You can override this setting and save binaries to project.root/.wdm.
    os.environ["WDM_LOCAL"] = "1"

    parser = argparse.ArgumentParser(description="HTML2Print printer script.")

    parser.add_argument(
        "-v", "--version", action="version", version=__version__
    )

    command_subparsers = parser.add_subparsers(title="command", dest="command")
    command_subparsers.required = True

    #
    # Get driver command.
    #
    command_parser_get_driver = command_subparsers.add_parser(
        "get_driver",
        help="Check if ChromeDriver already exists locally. If not, download it.",
        description="",
    )
    command_parser_get_driver.add_argument(
        "--cache-dir",
        type=str,
        help="Optional path to a cache directory whereto the ChromeDriver is downloaded.",
    )

    #
    # Print command.
    #
    command_parser_print = command_subparsers.add_parser(
        "print",
        help="Main print command",
        description="",
    )
    command_parser_print.add_argument(
        "--chromedriver",
        type=str,
        help="Optional chromedriver path. Downloaded if not given.",
    )
    command_parser_print.add_argument(
        "--cache-dir",
        type=str,
        help="Optional path to a cache directory whereto the ChromeDriver is downloaded.",
    )
    command_parser_print.add_argument(
        "paths", nargs="+", help="Paths to input HTML file."
    )

    args = parser.parse_args()

    path_to_cache_dir: str
    if args.command == "get_driver":
        path_to_cache_dir = (
            args.cache_dir
            if args.cache_dir is not None
            else (DEFAULT_CACHE_DIR)
        )

        path_to_chrome = get_chrome_driver(path_to_cache_dir)
        print(f"html2pdf: ChromeDriver available at path: {path_to_chrome}")  # noqa: T201
        sys.exit(0)

    elif args.command == "print":
        paths: List[str] = args.paths

        path_to_cache_dir = (
            args.cache_dir
            if args.cache_dir is not None
            else (DEFAULT_CACHE_DIR)
        )
        driver = create_webdriver(args.chromedriver, path_to_cache_dir)

        @atexit.register
        def exit_handler():
            print("html2pdf: exit handler: quitting the ChromeDriver.")  # noqa: T201
            driver.quit()

        assert len(paths) % 2 == 0, (
            f"Expecting an even number of input/output path arguments: {paths}."
        )
        for current_pair_idx in range(0, 2, len(paths)):
            path_to_input_html = paths[current_pair_idx]
            path_to_output_pdf = paths[current_pair_idx + 1]

            assert os.path.isfile(path_to_input_html), path_to_input_html

            path_to_output_pdf_dir = os.path.dirname(path_to_output_pdf)
            Path(path_to_output_pdf_dir).mkdir(parents=True, exist_ok=True)

            url = Path(os.path.abspath(path_to_input_html)).as_uri()

            pdf_bytes = get_pdf_from_html(driver, url)
            with open(path_to_output_pdf, "wb") as f:
                f.write(pdf_bytes)
    else:
        print("html2pdf: unknown command.")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
