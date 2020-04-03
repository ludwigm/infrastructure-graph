from dataclasses import dataclass, field
from typing import List

@dataclass
class ExternalDependency:
    team_name: str
    service_name: str
    # parameter_name: str
    # importing_stack: str

@dataclass 
class StackParameter:
    name: str
    value: str
    description: str = None
    external_dependency: ExternalDependency = None

@dataclass
class StackInfo:
    stack_name: str
    service_name: str
    parameters: List[StackParameter] = field(default_factory=list) # TODO

@dataclass
class StackExport:
    export_name: str
    export_value: str
    exporting_stack_name: str
    importing_stacks: List[str] = field(default_factory=list)
    export_service: str = None
    importing_services: List[str] = field(default_factory=list)