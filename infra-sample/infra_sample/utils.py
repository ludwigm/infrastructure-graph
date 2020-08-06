# Core Library
from typing import Optional


def generate_resource_name(
    project: str, env: str, service: str, component: str, suffix: Optional[str] = None
):
    resource_name = f"{project}-{env}-{service}-{component}"
    if suffix:
        resource_name += f"-{suffix}"
    return resource_name
