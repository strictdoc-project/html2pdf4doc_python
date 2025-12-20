import argparse
import contextlib
import datetime
import os.path
import random
import shutil
import sys
from enum import Enum
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from time import time
from typing import Iterator, List

from faker import Faker
from lxml import etree, html
from lxml.html import HtmlElement


@contextlib.contextmanager
def measure_performance(title: str) -> Iterator[None]:
    time_start = time()
    yield
    time_end = time()

    time_diff = time_end - time_start
    padded_name = f"{title} ".ljust(60, ".")
    padded_time = f" {time_diff:0.2f}".rjust(6, ".")
    print(f"{padded_name}{padded_time}s", flush=True)  # noqa: T201


def rewrite_js_path_to_local(html_text: str) -> str:
    tree = html.fromstring(html_text)
    for script in tree.xpath("//script[@src]"):
        src = script.get("src")
        if src.endswith("html2pdf4doc.min.js"):
            script.set("src", "html2pdf4doc.min.js")
    return str(html.tostring(tree, encoding="unicode"))


class MutationType(str, Enum):
    RANDOM = "random"
    INCREMENTAL = "incremental"

    @classmethod
    def all_as_str(cls) -> List[str]:
        return [t.value for t in cls]


def mutate_html_content(
    tree: HtmlElement, mutation_type: MutationType, mutation_cycle: int
) -> None:
    if mutation_type == MutationType.RANDOM:
        # Pick a random element.
        elems = tree.xpath("//p | //td")
        if elems:
            for _i in range(25):
                node = random.choice(elems)

                print("Mutating node:", node.tag, flush=True)  # noqa: T201

                n_sentences = random.randint(1, 100)

                fake = Faker()
                extra_text = fake.text(max_nb_chars=10 * n_sentences)

                node.text = extra_text
    elif mutation_type == MutationType.INCREMENTAL:
        elems = tree.xpath('//*[@id="html2pdf4doc_mutate_this"]')
        assert len(elems) == 1, (
            'Expected element with id="html2pdf4doc_mutate_this" to be found.'
        )

        filler_element = elems[0]
        filler_element.attrib["style"] = f"height: {mutation_cycle}px;"
    else:
        raise AssertionError("Must not reach here.")


def mutate_and_print(
    *,
    path_to_input_file: str,
    path_to_root: str,
    path_to_failed_mutants_dir: str,
    cycle: int,
    mutation_type: MutationType,
    strict_mode_2: bool = False,
) -> bool:
    assert os.path.isfile(path_to_input_file), path_to_input_file
    assert os.path.isdir(path_to_root), path_to_root
    assert 0 <= cycle <= 1000, cycle

    if not os.path.abspath(path_to_root):
        path_to_root = os.path.abspath(path_to_root)

    with open(path_to_input_file, encoding="utf-8") as input_file_:
        text = input_file_.read()

    # Parse HTML into DOM
    tree = html.fromstring(text)

    mutate_html_content(tree, mutation_type, cycle)

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
    if strict_mode_2:
        cmd.append("--strict2")

    for path_to_print_ in paths_to_print:
        cmd.append(path_to_print_[0])
        cmd.append(path_to_print_[1])

    path_to_mut_dir = os.path.dirname(path_to_mut_html)
    relative_path_to_mut_html = Path(path_to_mut_dir).relative_to(path_to_root)
    path_to_mut_output = os.path.join(
        path_to_failed_mutants_dir, relative_path_to_mut_html
    )

    def copy_files_if_needed() -> None:
        if os.path.isdir(path_to_mut_output):
            return

        Path(path_to_failed_mutants_dir).mkdir(parents=True, exist_ok=True)

        shutil.copytree(
            "html2pdf4doc",
            os.path.join(path_to_failed_mutants_dir, "html2pdf4doc"),
            dirs_exist_ok=True,
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

        if not os.path.isfile(path_to_mut_pdf):
            print(  # noqa: T201
                f"html2pdf4doc_fuzzer: warning: Mutated PDF is missing: {path_to_mut_pdf}"
            )
            return

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
    *,
    path_to_input_file: str,
    path_to_root: str,
    path_to_failed_mutants_dir: str,
    total_mutations: int = 20,
    mutation_type: MutationType = MutationType.RANDOM,
    strict_mode_2: bool = False,
) -> None:
    success_count, failure_count = 0, 0
    for i in range(1, total_mutations + 1):
        print(  # noqa: T201
            f"html2pdf4doc_fuzzer print cycle #{i}/{total_mutations} — "
            f"So far: 🟢{success_count} / 🔴{failure_count}",
            flush=True,
        )
        success = mutate_and_print(
            path_to_input_file=path_to_input_file,
            path_to_root=path_to_root,
            path_to_failed_mutants_dir=path_to_failed_mutants_dir,
            cycle=i,
            mutation_type=mutation_type,
            strict_mode_2=strict_mode_2,
        )
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
    parser.add_argument("path_to_failed_mutants_dir", type=str, help="TODO")
    parser.add_argument(
        "--total-mutations",
        type=int,
        required=True,
        help="An integer between 1 and 1000",
    )
    parser.add_argument(
        "--mutations",
        type=str,
        choices=MutationType.all_as_str(),
        help="Algorithm to use for mutations.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enables Strict mode (level 1).",
    )
    parser.add_argument(
        "--strict2",
        action="store_true",
        help="Enables Strict mode (level 2).",
    )
    args = parser.parse_args()

    path_to_input_file = args.input_file
    path_to_root = args.root_path
    path_to_failed_mutants_dir = args.path_to_failed_mutants_dir
    total_mutations = args.total_mutations
    assert 1 <= total_mutations <= 1000, total_mutations

    mutation_type = MutationType(args.mutations)

    strict_mode_2 = args.strict2

    fuzz_test(
        path_to_input_file=path_to_input_file,
        path_to_root=path_to_root,
        path_to_failed_mutants_dir=path_to_failed_mutants_dir,
        total_mutations=total_mutations,
        mutation_type=mutation_type,
        strict_mode_2=strict_mode_2,
    )


if __name__ == "__main__":
    main()
