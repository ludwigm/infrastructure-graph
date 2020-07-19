# Third party
from pyexpect import expect

# First party
from aws_infra_dependencies import __version__


def test_version():
    """Basic :: Verify the version number can be read"""
    expect(__version__).to_equal("0.1.0")
