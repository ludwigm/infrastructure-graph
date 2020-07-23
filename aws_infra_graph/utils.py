# Core Library
import os
import pickle
import logging
from typing import List

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


def file_cached(cachefile):
    """
    A function that creates a decorator which will use "cachefile" for caching
    the results of the decorated function "fn". Does not regard function params
    """

    def decorator(fn):
        def wrapped(*args, **kwargs):
            # if cache exists -> load it and return its content
            if os.path.exists(cachefile):
                with open(cachefile, "rb") as cachehandle:
                    logger.info(f"using cached result from '{cachefile}'")
                    return pickle.load(cachehandle)

            # execute the function with all arguments passed
            res = fn(*args, **kwargs)

            # write to cache file
            with open(cachefile, "wb") as cachehandle:
                logger.info(f"saving result to cache '{cachefile}'")
                pickle.dump(res, cachehandle)

            return res

        return wrapped

    return decorator


def build_tag_search_patterns(tags: List[str]):
    return [jmespath.compile(f"[?Key==`{tag}`]|[0]|Value") for tag in tags]
