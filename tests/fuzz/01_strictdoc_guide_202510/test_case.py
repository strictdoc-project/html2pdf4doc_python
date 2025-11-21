import os

from html2pdf4doc.main_fuzzer import fuzz_test
from tests.fuzz.conftest import create_build_folder, FuzzConfig

PATH_TO_THIS_FOLDER = os.path.dirname(__file__)

def test(fuzz_config: FuzzConfig):
    build_folder = create_build_folder(PATH_TO_THIS_FOLDER)

    fuzz_test(
        path_to_input_file=os.path.join(
            build_folder,
            "strictdoc/docs/strictdoc_01_user_guide-PDF.html"
        ),
        path_to_root=build_folder,
        total_mutations=fuzz_config.total_mutations
    )
