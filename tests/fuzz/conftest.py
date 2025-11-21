import datetime
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

PATH_TO_TESTS_FUZZ_FOLDER = os.path.dirname(__file__)


@dataclass
class FuzzConfig:
    strict_mode_2: bool
    total_mutations: bool


def pytest_addoption(parser):
    parser.addoption(
        "--fuzz-strict2",
        action="store_true",
        help="Enables Strict mode (level 2).",
    )
    parser.addoption(
        "--fuzz-total-mutations",
        action="store",
        type=int,
        choices=range(1, 1001),
        default=10,
        help="Total number of mutations to perform (1-1000)"
    )

@pytest.fixture
def fuzz_config(request):
    return FuzzConfig(
        strict_mode_2=request.config.getoption("--fuzz-strict2"),
        total_mutations=request.config.getoption("--fuzz-total-mutations")
    )


def create_build_folder(test_folder: str) -> str:
    assert os.path.isdir(test_folder), test_folder
    assert os.path.isabs(test_folder), test_folder

    relative_path_to_test_folder = Path(test_folder).relative_to(PATH_TO_TESTS_FUZZ_FOLDER)

    # IMPORTANT: The number of nested folders matches the number of nesting
    #            in the tests/fuzz/* test folders. Otherwise, the html2pdf4doc.js
    #            will not be found in either of tests/fuzz/* or build/tests_fuzz/*.
    build_folder = os.path.join(
        "build",
        "tests_fuzz",
        relative_path_to_test_folder
    )

    shutil.copytree(test_folder, build_folder)

    return build_folder


def create_failed_mutants_folder(test_folder: str) -> str:
    assert os.path.isdir(test_folder), test_folder
    assert os.path.isabs(test_folder), test_folder

    relative_path_to_test_folder = Path(test_folder).relative_to(PATH_TO_TESTS_FUZZ_FOLDER)

    mutants_folder = os.path.join(
        "build",
        "tests_fuzz_failed_mutants",
        datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
        relative_path_to_test_folder
    )

    return mutants_folder
