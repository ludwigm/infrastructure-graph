# Core Library
import os
import pickle
import logging

logger = logging.getLogger()
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)


def file_cached(cachefile):
    """
    A function that creates a decorator which will use "cachefile" for caching the results of the decorated function "fn".
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
