# Core Library
import logging

# Third party
from _pytest.config.argparsing import Parser


def pytest_configure(config):
    """Flake8 is very verbose by default. Silence it."""
    logging.getLogger("flake8").setLevel(logging.WARNING)


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--lint-only",
        action="store_true",
        default=False,
        help="Only run linting checks",
    )


def pytest_collection_modifyitems(session, config, items) -> None:
    """Enhance pytest to allow for a linting only option"""
    if config.getoption("--lint-only"):
        lint_items = []
        for linter in ["flake8", "black", "mypy", "mccabe"]:
            if config.getoption(f"--{linter}"):
                lint_items.extend(
                    [item for item in items if item.get_closest_marker(linter)]
                )
        items[:] = lint_items
