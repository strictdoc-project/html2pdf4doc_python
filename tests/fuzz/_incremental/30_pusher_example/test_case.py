import os

from html2pdf4doc.main_fuzzer import fuzz_test, rewrite_js_path_to_local, \
    MutationType
from tests.fuzz.conftest import create_build_folder, FuzzConfig, create_failed_mutants_folder

PATH_TO_THIS_FOLDER = os.path.dirname(__file__)

def test(fuzz_config: FuzzConfig):
    build_folder = create_build_folder(PATH_TO_THIS_FOLDER)

    path_to_system_under_test = os.path.join(
        build_folder,
        "case_001.html"
    )

    with open(path_to_system_under_test, "r", encoding="utf-8") as f:
        html_text = f.read()
    html_text = rewrite_js_path_to_local(html_text)
    with open(path_to_system_under_test, "w", encoding="utf-8") as f:
        f.write(html_text)

    fuzz_test(
        path_to_input_file=path_to_system_under_test,
        path_to_root=build_folder,
        path_to_failed_mutants_dir=create_failed_mutants_folder(PATH_TO_THIS_FOLDER),
        total_mutations=fuzz_config.total_mutations,
        mutation_type=MutationType.INCREMENTAL,
        strict_mode_2=fuzz_config.strict_mode_2,
    )
