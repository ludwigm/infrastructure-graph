from __future__ import annotations

# Core Library
import json
from typing import Dict, List

# Third party
from pydantic import BaseModel
from pyhocon.tool import HOCONConverter
from pyhocon.config_parser import ConfigFactory


class InfraGraphConfig(BaseModel):
    default_project: str
    projects: Dict[str, ProjectConfig]

    class Config:
        allow_population_by_field_name = True
        fields = {"default_project": "defaultProject"}


class ProjectConfig(BaseModel):
    upstream_dependencies: Dict[str, List[ManualDependency]]

    class Config:
        allow_population_by_field_name = True
        fields = {"upstream_dependencies": "upstreamDependencies"}


class ManualDependency(BaseModel):
    team: str
    service: str


def load_config(config_path: str) -> InfraGraphConfig:
    hocon_conf = ConfigFactory.parse_file(config_path)
    config_dict = json.loads(HOCONConverter.to_json(hocon_conf.get("infraGraph")))
    return InfraGraphConfig(**config_dict)


InfraGraphConfig.update_forward_refs()
ProjectConfig.update_forward_refs()
