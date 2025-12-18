import os
from pathlib import Path

__version__ = "0.0.25"

PATH_TO_HTML2PDF4DOC_PY = os.path.join(
    os.path.dirname(os.path.join(__file__)),
    "main.py",
)
PATH_TO_HTML2PDF4DOC_JS = os.path.join(
    os.path.dirname(os.path.join(__file__)),
    "html2pdf4doc_js",
    "html2pdf4doc.min.js",
)

DEFAULT_CACHE_DIR = os.path.join(Path.home(), ".html2pdf4doc", "chromedriver")

PATH_TO_CHROME_DRIVER_DEBUG_LOG = "/tmp/chromedriver.log"
