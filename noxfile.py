# Third party
import nox
from nox.sessions import Session


@nox.session(python=False, name="unit-tests")
def unit_tests(session: Session) -> None:
    session.run(
        "pytest",
        "--mocha",
        "--cov=./aws_infra_dependencies",
        "--cov-report",
        "html:tests/reports/coverage-html",
        "--cov-report",
        "xml:tests/reports/coverage.xml",
        "--cov-report",
        "term",
        "--ignore=docs/",
        "--durations=3",
    )


@nox.session(python=False, name="static-code-analysis")
def static_code_analysis(session: Session) -> None:
    session.run("pytest", "--lint-only", "--black", "--flake8", "--mypy", "--mccabe")
