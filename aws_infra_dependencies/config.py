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


def load_config(config_path: str) -> InfraGraphConfig:
    hocon_conf = ConfigFactory.parse_file(config_path)
    config_dict = json.loads(HOCONConverter.to_json(hocon_conf.get("infraGraph")))
    return InfraGraphConfig(**config_dict)


InfraGraphConfig.update_forward_refs()
ProjectConfig.update_forward_refs()
