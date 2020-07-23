from __future__ import annotations

# Core Library
import os
import sys
import json
import logging
import importlib.resources as pkg_resources
from typing import Dict, List
from pathlib import Path

# Third party
import coloredlogs
from pydantic import BaseModel
from pyhocon.tool import HOCONConverter
from pyhocon.config_parser import ConfigFactory

# First party
from aws_infra_graph import data

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)
coloredlogs.install(
    level=os.getenv("LOG_LEVEL", "INFO"),
    fmt="[%(levelname)s] %(message)s",
    logger=logger,
)

SYSTEM_CONFIG_ROOT = Path.home() / Path(".config/aws-infra-graph")


class InfraGraphConfig(BaseModel):
    default_project: str
    service_tags: List[str]
    component_tags: List[str]
    projects: Dict[str, ProjectConfig]

    class Config:
        allow_population_by_field_name = True
        fields = {
            "default_project": "defaultProject",
            "service_tags": "serviceTags",
            "component_tags": "componentTags",
        }


class ProjectConfig(BaseModel):
    downstream_dependencies: Dict[str, List[ManualDependency]]
    internal_manual_dependencies: Dict[str, List[ManualInternalDependency]]

    class Config:
        allow_population_by_field_name = True
        fields = {
            "downstream_dependencies": "downstreamDependencies",
            "internal_manual_dependencies": "internalManualDependencies",
        }


class ManualDependency(BaseModel):
    team: str
    service: str


class ManualInternalDependency(BaseModel):
    service: str


def init_config():
    config_root = SYSTEM_CONFIG_ROOT
    target_config = config_root / "config.hocon"
    template_body = pkg_resources.read_text(data, "config-empty.hocon")
    if not target_config.exists():
        logger.info(
            f"Bootstraping config {target_config} from template. Adapt to your needs afterwards"
        )
        if not config_root.exists():
            config_root.mkdir(parents=True)
        target_config.touch()
        with open(target_config, mode="w") as file:
            file.write(template_body)
    else:
        logger.info(
            f"Config {target_config} does already exist. Displaying current template if update is needed"
        )
        print(template_body)


def load_config(config_path: str) -> InfraGraphConfig:
    system_config_path = SYSTEM_CONFIG_ROOT / "config.hocon"
    config = Path(config_path)
    if config.exists():
        logger.info("Using local config")
        config_to_load = config
    elif system_config_path.exists():
        config_to_load = system_config_path
    else:
        logger.error(
            f"No config found to load. Run the `init` command or have a local config '{config_path} available'"
        )
        sys.exit(1)

    hocon_conf = ConfigFactory.parse_file(config_to_load)
    config_dict = json.loads(HOCONConverter.to_json(hocon_conf.get("infraGraph")))
    return InfraGraphConfig(**config_dict)


InfraGraphConfig.update_forward_refs()
ProjectConfig.update_forward_refs()
