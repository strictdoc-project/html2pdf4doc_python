# html2pdf4doc_python

html2pdf4doc_python is the Python wrapper/CLI for the
[html2pdf4doc](https://github.com/mettta/html2pdf) JavaScript
library that prints HTML pages into PDFs using Chrome/Chromedriver.

This repository focuses strictly on the Python-side automation layer. The
rendering logic remains in the JS core.

## Installation

1. Install Google Chrome (or Chrome for Testing) on the machine that will run the CLI.

2. Install the package from PyPI:

```bash
pip install html2pdf4doc
```

Python 3.8+ is required.

See also: the Ubuntu-based container `Dockerfile` and the GitHub CI files found
in the `.github/workflows` folder.

## Usage

TBD

## Developer guide

### Getting started

1\. (Optional) Create and activate a virtual environment 

```
python -m venv .venv && source .venv/bin/activate
```

2\. Install the dependencies

```
git clone https://github.com/strictdoc-project/html2pdf4doc_python.git
cd html2pdf4doc_python

# Bootstrap minimal Python dependencies: Invoke and TOML.
pip install invoke toml

# Install all Python dependencies and update the submodule with the html2pdf4doc.js.
invoke bootstrap
```

3\. The JS library is maintained in a Git submodule `submodules/html2pdf`.

When the submodule is updated after a release or during the development, rebuild
the JS library, i.e., regenerate the `html2pdf4doc.min.js`:

```
invoke build
```

4\. To validate changes, use the following commands:

```
invoke lint
invoke test  # Normal tests.
invoke test-fuzz  # More robust testing.
```

## License

The project is distributed under the Apache License 2.0 (see `LICENSE`).
