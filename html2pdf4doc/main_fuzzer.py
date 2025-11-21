import argparse
import contextlib
import datetime
import os.path
import random
import shutil
import sys
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from time import time
from typing import Iterator, List

from faker import Faker
from lxml import etree, html


@contextlib.contextmanager
def measure_performance(title: str) -> Iterator[None]:
    time_start = time()
    yield
    time_end = time()

    time_diff = time_end - time_start
    padded_name = f"{title} ".ljust(60, ".")
    padded_time = f" {time_diff:0.2f}".rjust(6, ".")
    print(f"{padded_name}{padded_time}s", flush=True)  # noqa: T201


def mutate_and_print(path_to_input_file: str, path_to_root: str) -> bool:
    assert os.path.isfile(path_to_input_file), path_to_input_file
    assert os.path.isdir(path_to_root), path_to_root
    if not os.path.abspath(path_to_root):
        path_to_root = os.path.abspath(path_to_root)

    text = open(path_to_input_file, encoding="utf-8").read()

    # Parse HTML into DOM
    tree = html.fromstring(text)

    # Pick a random element
    elems = tree.xpath("//p | //td")
    if elems:
        for _i in range(25):
            node = random.choice(elems)

            print("Mutating node:", node.tag, flush=True)  # noqa: T201

            n_sentences = random.randint(1, 100)

            fake = Faker()
            extra_text = fake.text(max_nb_chars=10 * n_sentences)

            node.text = extra_text

    # Serialize back to HTML
    mutated_html = etree.tostring(
        tree, pretty_print=False, method="html", encoding="unicode"
    )

    # Save next to input file
    path_to_mut_html = path_to_input_file + ".mut.html"
    path_to_mut_pdf = path_to_input_file + ".mut.html.pdf"
    with open(path_to_mut_html, "w", encoding="utf-8") as f:
        f.write(mutated_html)

    print("Wrote mutated file:", path_to_mut_html, flush=True)  # noqa: T201

    paths_to_print = [(path_to_mut_html, path_to_mut_pdf)]

    cmd: List[str] = [
        sys.executable,
        "-m",
        "html2pdf4doc.main",
        "print",
        "--strict",
    ]

    for path_to_print_ in paths_to_print:
        cmd.append(path_to_print_[0])
        cmd.append(path_to_print_[1])

    relative_path_to_mut_html = Path(path_to_mut_html).relative_to(path_to_root)
    path_to_mut_output = f"output/{relative_path_to_mut_html}"

    def copy_files_if_needed() -> None:
        if os.path.isdir(path_to_mut_output):
            return

        shutil.rmtree("output", ignore_errors=True)
        Path("output").mkdir(parents=True, exist_ok=True)

        shutil.copytree(
            "html2pdf4doc", "output/html2pdf4doc", dirs_exist_ok=True
        )

        shutil.rmtree(path_to_mut_output, ignore_errors=True)
        Path(path_to_mut_output).mkdir(parents=True, exist_ok=True)

        shutil.copytree(path_to_root, path_to_mut_output, dirs_exist_ok=True)

    def copy_mutated_file() -> None:
        relative_path_to_mut_html = Path(path_to_mut_html).relative_to(
            path_to_root
        )

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path_to_mut_html_out = os.path.join(
            path_to_mut_output,
            f"{relative_path_to_mut_html}.{timestamp}.html",
        )
        shutil.copy(path_to_mut_html, path_to_mut_html_out)

        path_to_mut_pdf_out = os.path.join(
            path_to_mut_output,
            f"{relative_path_to_mut_html}.{timestamp}.pdf",
        )
        shutil.copy(path_to_mut_pdf, path_to_mut_pdf_out)

        print(  # noqa: T201
            f"Saved failed mutated HTML as:\n"
            f"HTML: {path_to_mut_html_out}\n"
            f"PDF: {path_to_mut_pdf_out}"
        )

    with measure_performance(
        "html2pdf4doc_fuzzer: printing HTML to PDF using HTML2PDF and Chrome Driver"
    ):
        try:
            _: CompletedProcess[bytes] = run(
                cmd, capture_output=False, check=True, bufsize=1
            )
        except CalledProcessError as called_process_error_:
            print(called_process_error_)  # noqa: T201

            copy_files_if_needed()

            copy_mutated_file()

            return False
        except TimeoutExpired:
            raise TimeoutError from None
    return True


def fuzz_test(
    *, path_to_input_file: str, path_to_root: str, total_mutations: int = 20
) -> None:
    shutil.rmtree("output", ignore_errors=True)
    Path("output").mkdir(parents=True, exist_ok=True)

    success_count, failure_count = 0, 0
    for i in range(1, total_mutations + 1):
        print(  # noqa: T201
            f"html2pdf4doc_fuzzer print cycle #{i}/{total_mutations} — "
            f"So far: 🟢{success_count} / 🔴{failure_count}",
            flush=True,
        )
        success = mutate_and_print(path_to_input_file, path_to_root)
        if success:
            success_count += 1
        else:
            failure_count += 1

    assert total_mutations > 0
    success_rate_percent = (success_count / total_mutations) * 100

    print(  # noqa: T201
        f"html2pdf4doc_fuzzer: finished {'✅' if failure_count == 0 else '❌'} — "
        f"Success rate: {success_count}/{total_mutations} ({success_rate_percent}%)",
        flush=True,
    )

    if failure_count > 0:
        sys.exit(1)


def main() -> None:
    # To avoid UnicodeEncodeError on Windows when printing emojis.
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    parser = argparse.ArgumentParser()

    parser.add_argument("input_file", type=str, help="TODO")
    parser.add_argument("root_path", type=str, help="TODO")
    parser.add_argument(
        "--total-mutations",
        type=int,
        choices=range(1, 1001),
        required=True,
        help="An integer between 1 and 1000",
    )

    args = parser.parse_args()

    path_to_input_file = args.input_file
    path_to_root = args.root_path
    total_mutations = args.total_mutations

    fuzz_test(
        path_to_input_file=path_to_input_file,
        path_to_root=path_to_root,
        total_mutations=total_mutations,
    )


if __name__ == "__main__":
    main()
