"""
Several html2pdf4doc processes print at the same time and share one empty
ChromeDriver cache. All processes must succeed.

Before the fix, the processes unpacked the ChromeDriver in place. A process
could overwrite the ChromeDriver while another process was running it, which
failed with "Text file busy" on Linux.
"""

import os
import shutil
import subprocess
import sys

from pypdf import PdfReader

NUMBER_OF_PROCESSES = 4

html2pdf_command = sys.argv[1]
path_to_test_dir = sys.argv[2]

path_to_output_dir = os.path.join(path_to_test_dir, "Output")
path_to_cache_dir = os.path.join(path_to_output_dir, "cache")
path_to_input = os.path.join(path_to_test_dir, "index.html")

shutil.rmtree(path_to_cache_dir, ignore_errors=True)
os.makedirs(path_to_output_dir, exist_ok=True)

processes = []
for process_index_ in range(NUMBER_OF_PROCESSES):
    path_to_pdf = os.path.join(path_to_output_dir, f"index{process_index_}.pdf")
    if os.path.exists(path_to_pdf):
        os.remove(path_to_pdf)
    command = (
        f'{html2pdf_command} print --cache-dir "{path_to_cache_dir}" '
        f'"{path_to_input}" "{path_to_pdf}"'
    )
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append((process, path_to_pdf))

number_of_successes = 0
for process_, path_to_pdf_ in processes:
    output, _ = process_.communicate()
    if process_.returncode != 0:
        print(  # noqa: T201
            f"test: process failed with exit code {process_.returncode}:\n"
            + output.decode("utf-8", errors="replace")
        )
        continue
    reader = PdfReader(path_to_pdf_)
    assert reader.pages[0].extract_text() == "Hello world!"
    number_of_successes += 1

print(  # noqa: T201
    f"test: {number_of_successes} of {NUMBER_OF_PROCESSES} processes printed "
    "the PDF."
)
