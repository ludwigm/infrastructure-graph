# Core Library
import os
import pickle
import logging
from typing import List
from pathlib import Path

# Third party
import jmespath
import coloredlogs

# TODO simplify logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)
coloredlogs.install(
    level=os.getenv("LOG_LEVEL", "INFO"),
    fmt="[%(levelname)s] %(message)s",
    logger=logger,
)

SYSTEM_CACHE_ROOT = Path.home() / Path(".cache/aws-infra-graph")


def file_cached(cachefile):
    """
    A function that creates a decorator which will use "cachefile" for caching
    the results of the decorated function "fn". Does not regard function params
    """

    def decorator(fn):
        def wrapped(*args, **kwargs):
            cachefile_path = SYSTEM_CACHE_ROOT / Path(cachefile)
            if not SYSTEM_CACHE_ROOT.exists():
                SYSTEM_CACHE_ROOT.mkdir(parents=True)
            # if cache exists -> load it and return its content
            if cachefile_path.exists():
                with open(cachefile_path, "rb") as cachehandle:
                    logger.info(f"using cached result from '{cachefile_path}'")
                    return pickle.load(cachehandle)

            # execute the function with all arguments passed
            res = fn(*args, **kwargs)

            # write to cache file
            with open(cachefile_path, "wb") as cachehandle:
                logger.info(f"saving result to cache '{cachefile_path}'")
                pickle.dump(res, cachehandle)

            return res

        return wrapped

    return decorator


def build_tag_search_patterns(tags: List[str]):
    return [jmespath.compile(f"[?Key==`{tag}`]|[0]|Value") for tag in tags]
