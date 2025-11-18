# Invoke is broken on Python 3.11
# https://github.com/pyinvoke/invoke/issues/833#issuecomment-1293148106
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec

import invoke  # pylint: disable=wrong-import-position
from invoke import task  # pylint: disable=wrong-import-position

# Specifying encoding because Windows crashes otherwise when running Invoke
# tasks below:
# UnicodeEncodeError: 'charmap' codec can't encode character '\ufffd'
# in position 16: character maps to <undefined>
# People say, it might also be possible to export PYTHONIOENCODING=utf8 but this
# seems to work.
# FIXME: If you are a Windows user and expert, please advise on how to do this
# properly.
sys.stdout = open(  # pylint: disable=consider-using-with
    1, "w", encoding="utf-8", closefd=False, buffering=1
)


def run_invoke(
    context,
    cmd,
    environment: Optional[dict] = None,
    warn: bool = False,
    pty: bool = False,
) -> invoke.runners.Result:
    def one_line_command(string):
        return re.sub("\\s+", " ", string).strip()

    return context.run(
        one_line_command(cmd),
        env=environment,
        hide=False,
        warn=warn,
        pty=pty,
        echo=True,
    )


@task(default=True)
def list_tasks(context):
    clean_command = """
        invoke --list
    """
    run_invoke(context, clean_command)


@task
def bootstrap(context):
    run_invoke(context, "git submodule update --init --recursive")
    run_invoke(context, "pip install -r requirements.development.txt")


@task(aliases=["b"])
def build(context):
    run_invoke(
        context, "cd submodules/html2pdf && npm install && npm run build"
    )
    # Windows can't do slashes for this one.
    if not os.path.isdir(os.path.join("html2pdf4doc", "html2pdf4doc_js")):
        run_invoke(
            context,
            """
            cd html2pdf4doc && mkdir html2pdf4doc_js
            """,
        )
    run_invoke(
        context,
        """
        cp submodules/html2pdf/dist/bundle.js html2pdf4doc/html2pdf4doc_js/html2pdf4doc.min.js
        """,
    )


@task
def format_readme(context):
    run_invoke(
        context,
        """
    prettier
        --write --print-width 80 --prose-wrap always --parser=markdown
        README.md
    """,
    )


@task
def get_chrome_driver(
    context,
):
    run_invoke(
        context,
        """
        python -m html2pdf4doc.main get_driver
    """,
    )


@task
def lint_ruff_format(context):
    result: invoke.runners.Result = run_invoke(
        context,
        """
            ruff
                format
                *.py
                html2pdf4doc/
                tests/integration/
        """,
    )
    # Ruff always exits with 0, so we handle the output.
    if "reformatted" in result.stdout:
        print("invoke: ruff format found issues")  # noqa: T201
        result.exited = 1
        raise invoke.exceptions.UnexpectedExit(result)


@task(aliases=["lr"])
def lint_ruff(context):
    run_invoke(
        context,
        """
            ruff check *.py html2pdf4doc/ --fix --cache-dir build/ruff
        """,
    )


@task(aliases=["lm"])
def lint_mypy(context):
    # These checks do not seem to be useful:
    # - import
    # - misc
    run_invoke(
        context,
        """
            mypy html2pdf4doc/
                --show-error-codes
                --disable-error-code=import
                --disable-error-code=misc
                --cache-dir=build/mypy
                --strict
                --python-version=3.9
        """,
    )


@task(aliases=["l"])
def lint(context):
    lint_ruff_format(context)
    lint_ruff(context)
    lint_mypy(context)


@task(aliases=["ti"])
def test_integration(
    context,
    focus=None,
    full=False,
    debug=False,
):
    clean_itest_artifacts(context)

    get_chrome_driver(context)

    html2pdf_exec = "python3 -m html2pdf4doc.main"

    focus_or_none = f"--filter {focus}" if focus else ""
    debug_opts = "-vv --show-all" if debug else ""

    full = full or _is_full_ci_test()
    param_full_test = "--param HTML2PDF4DOC_FULL_TEST=1" if full else ""

    # For now, the --threads are set to 1 because running tests parallelized
    # will result in race conditions between Web Driver Manager downloading
    # ChromeDriver.
    itest_command = f"""
        lit
        --threads 1
        --param HTML2PDF4DOC_EXEC="{html2pdf_exec}"
        {param_full_test}
        -v
        {debug_opts}
        {focus_or_none}
        tests/integration
    """

    run_invoke(context, itest_command)


@task(aliases=["tf"])
def test_fuzz(
    context,
    focus=None,
    total_mutations: int = 10,
    output=False,
    strict2: bool = False,
):
    """
    Run fuzz/mutation tests.
    """

    test_reports_dir = "build/test_reports"

    Path(test_reports_dir).mkdir(parents=True, exist_ok=True)

    focus_argument = f"-k {focus}" if focus is not None else ""
    long_argument = (
        f"--fuzz-total-mutations={total_mutations}" if total_mutations else ""
    )
    strict2_argument = "--fuzz-strict2" if strict2 else ""
    output_argument = "--capture=no" if output else ""

    run_invoke(
        context,
        """
            rm -rf build/tests_fuzz
        """,
    )

    run_invoke(
        context,
        f"""
            pytest
            {focus_argument}
            {long_argument}
            {strict2_argument}
            {output_argument}
            -o cache_dir=build/tests_fuzz_cache
            tests/fuzz/
        """,
    )


@task(aliases=["t"])
def test(context):
    test_integration(context)


@task
def clean_itest_artifacts(context):
    # https://unix.stackexchange.com/a/689930/77389
    find_command = """
        git clean -dfX tests/integration/
    """
    # The command sometimes exits with 1 even if the files are deleted.
    # warn=True ensures that the execution continues.
    run_invoke(context, find_command, warn=True)


@task
def package(context):
    build(context)

    run_invoke(
        context,
        """
            rm -rfv dist/
        """,
    )
    run_invoke(
        context,
        """
            python3 -m build
        """,
    )
    run_invoke(
        context,
        """
            twine check dist/*
        """,
    )


@task
def release(context, test_pypi=False, username=None, password=None):
    """
    A release can be made to PyPI or test package index (TestPyPI):
    https://pypi.org/project/html2pdf4doc/
    https://test.pypi.org/project/html2pdf4doc/
    """

    # When a username is provided, we also need password, and then we don't use
    # tokens set up on a local machine.
    assert username is None or password is not None

    package(context)

    repository_argument_or_none = (
        ""
        if username
        else (
            "--repository html2pdf4doc_test"
            if test_pypi
            else "--repository html2pdf4doc_release"
        )
    )
    user_password = f"-u{username} -p{password}" if username is not None else ""

    # The token is in a core developer's .pypirc file.
    # https://test.pypi.org/manage/account/token/
    # https://packaging.python.org/en/latest/specifications/pypirc/#pypirc
    run_invoke(
        context,
        f"""
            twine upload dist/html2pdf4doc-*.tar.gz dist/html2pdf4doc-*.whl
                {repository_argument_or_none}
                {user_password}
        """,
    )


@task(aliases=["bd"])
def build_docker(
    context,
    image: str = "html2pdf4doc:latest",
    no_cache: bool = False,
    source="pypi",
):
    no_cache_argument = "--no-cache" if no_cache else ""
    run_invoke(
        context,
        f"""
        docker build .
            --build-arg HTML2PDF4DOC_SOURCE={source}
            -t {image}
            {no_cache_argument}
        """,
    )


@task(aliases=["rd"])
def run_docker(
    context, image: str = "html2pdf4doc:latest", command: Optional[str] = None
):
    command_argument = (
        f'/bin/bash -c "{command}"' if command is not None else ""
    )

    run_invoke(
        context,
        f"""
        docker run
            --name html2pdf4doc
            --rm
            -it
            -e HOST_UID=$(id -u) -e HOST_GID=$(id -g)
            -v "$(pwd):/data:rw"
            {image}
            {command_argument}
        """,
        pty=True,
    )


@task(aliases=["td"])
def test_docker(context, image: str = "html2pdf4doc:latest"):
    run_invoke(
        context,
        """
        mkdir -p output/ && chmod 777 output/
        """,
    )
    run_docker(
        context,
        image=image,
        command=(
            "cd tests/integration/01_hello_world && html2pdf4doc print index.html /data/output/index.pdf"
        ),
    )


def _is_full_ci_test() -> bool:
    """
    Determine whether @full_test was requested in a GitHub CI run.
    Returns True if the tag is found in PR body/title or commit message.
    Returns False for local runs or when tag not found.
    """

    if "@full_test" in _get_last_commit_message_or_empty():
        print("[is_full_ci_test] @full_test found in the last commit message.")  # noqa: T201
        return True

    event_name = os.getenv("GITHUB_EVENT_NAME")
    event_path = os.getenv("GITHUB_EVENT_PATH")

    # No GitHub env (e.g. local run).
    if not event_name or not event_path or not Path(event_path).exists():
        print(  # noqa: T201
            "[is_full_ci_test] No GitHub environment detected — running in local mode."
        )
        return False

    if event_name == "schedule":
        "[is_full_ci_test] Detected scheduled run."
        return True

    try:
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
    except Exception as e:
        print(  # noqa: T201
            f"[is_full_ci_test] Failed to parse event file: {e}"
        )
        return False

    tag = "@full_test"

    # Check PR body.
    if event_name == "pull_request":
        pr = event.get("pull_request", {})
        body = (pr.get("body") or "").lower()

        if tag in body:
            print(  # noqa: T201
                "[is_full_ci_test] Detected @full_test in PR title."
            )
            return True

    print("[is_full_ci_test] @full_test not found.")  # noqa: T201
    return False


def _get_last_commit_message_or_empty() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().lower()
    except Exception:
        return ""
