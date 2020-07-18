#! /usr/bin/env python

# Core Library
import os
import re
import csv
import time
import logging
from typing import Any, Dict, List, Iterable, Optional, DefaultDict
from collections import defaultdict

# Third party
import boto3
import jmespath
from colorama import Fore, Style, init
from graphviz import Digraph
from botocore.exceptions import ClientError
from boto3_type_annotations import cloudformation

# First party
from aws_infra_dependencies.model import (
    StackInfo,
    StackExport,
    StackParameter,
    ExternalDependency,
)
from aws_infra_dependencies.config import InfraGraphConfig, load_config

init(autoreset=True)

logger = logging.getLogger()
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)

IMPORTANT_STACK_DEPENDENCY_TRESHOLD = 4


class InfraGraphExporter:
    config: InfraGraphConfig
    output_folder: str
    env: str
    project_name: str
    cfn_client: cloudformation.Client

    def __init__(
        self,
        env: str,
        project_name: Optional[str] = None,
        config_path="./config.hocon",
        output_folder="./output",
    ):
        self.config = load_config(config_path)
        self.cfn_client = boto3.client("cloudformation")
        self.output_folder = output_folder
        self.env = env
        self.project_name = (
            project_name if project_name else self.config.default_project
        )
        # Replace with your own tag you want to group on to aggregate on higher level
        self.service_tag_search = jmespath.compile("[?Key==`ServiceName`]|[0]|Value")
        self.service_tag2_search = jmespath.compile(
            "[?Key==`Service`]|[0]|Value"
        )  # TODO align in infra

    def export(self):
        stack_infos = list(self._gather_stacks())
        self._print_stack_infos(stack_infos)
        exports = list(self._gather_and_filter_exports(stack_infos))
        imported_exports = [
            export for export in exports if len(export.importing_stacks) > 0
        ]
        self._print_export_infos(imported_exports)
        self._visualize(imported_exports, stack_infos)
        self._visualize_services(imported_exports, stack_infos)
        logger.info(f"\nGraph exports finished in {self.output_folder} folder")

    def _print_export_infos(self, exports: List[StackExport]):
        logger.info("\n")
        logger.info(f"{Fore.BLUE}Export details:")
        for export in exports:
            logger.info(
                f"{Style.BRIGHT}{export.export_name}:{export.export_value} [Stack: {export.exporting_stack_name}]"
            )
            for importing_stack in export.importing_stacks:
                logger.info(f"\t{importing_stack}")

        logger.info(f"{Fore.BLUE}Export details with service names:")
        for export in exports:
            if (
                len(export.importing_services) == 1
                and export.export_service == export.importing_services[0]
            ):
                logger.info(
                    f"{Style.BRIGHT}{export.export_name} [Service: {export.export_service}] -> only reflexive dependency"
                )
            else:
                logger.info(
                    f"{Style.BRIGHT}{export.export_name} [Service: {export.export_service}]"
                )
                for importing_service in export.importing_services:
                    logger.info(f"\t{importing_service}")

    def _enrich_service_name(
        self, exports_enriched: List[StackExport], stack_infos: List[StackInfo]
    ) -> Iterable[StackExport]:
        grouped_by_stack = {}
        for stack_info in stack_infos:
            if stack_info.service_name is not None:
                grouped_by_stack[stack_info.stack_name] = stack_info.service_name

        for export in exports_enriched:
            service_name = grouped_by_stack[export.exporting_stack_name]
            importing_services = [
                grouped_by_stack[importing_stack]
                for importing_stack in export.importing_stacks
                if grouped_by_stack.get(importing_stack) is not None
            ]
            yield StackExport(
                export_name=export.export_name,
                exporting_stack_name=export.exporting_stack_name,
                export_value=export.export_value,
                export_service=service_name,
                importing_stacks=export.importing_stacks,
                importing_services=importing_services,
            )

    def _print_stack_infos(self, stack_infos: List[StackInfo]):
        logger.info("\n")
        logger.info(f"{Fore.BLUE}Stacks without service name:")
        grouped_by_service: DefaultDict[str, List[str]] = defaultdict(list)
        for stack_info in stack_infos:
            if stack_info.service_name is None:
                logger.info(stack_info)
            else:
                grouped_by_service[stack_info.service_name].append(
                    stack_info.stack_name
                )

        logger.info("\n")

        logger.info(f"{Fore.BLUE}Stacks grouped by service name:")
        for service, stacks in grouped_by_service.items():
            logger.info(f"{Style.BRIGHT}\t{service}:")
            for stack in stacks:
                logger.info(f"\t\t{stack}")

        logger.info("\n")

        logger.info(f"{Fore.BLUE}Stacks parameters:")
        for stack_info in stack_infos:
            logger.info(f"{Style.BRIGHT}\t{stack_info.stack_name}:")
            for param in stack_info.parameters:
                description = f"[{param.description}]" if param.description else ""
                logger.info(f"\t\t{param.name}: {param.value} {description}")

        logger.info("\n")

    def _visualize_services(
        self,
        exports_with_service_names: List[StackExport],
        stack_infos: List[StackInfo],
    ):
        stacks_graph = Digraph(
            "StacksGraph",
            node_attr={"shape": "box", "style": "filled", "fillcolor": "grey"},
        )
        edge_set = set()
        for export in exports_with_service_names:
            for importing_service in export.importing_services:
                if export.export_service != importing_service:  # no reflexive
                    edge_set.add((export.export_service, importing_service))

        for export_service, importing_service in edge_set:
            stacks_graph.edge(export_service, importing_service)

        edge_set_external = set()
        node_set_external = set()

        for stack in stack_infos:
            for parameter in stack.parameters:
                if parameter.external_dependency is not None:
                    external_service_name = parameter.external_dependency.service_name
                    # stacks_graph.node(external_service_name, _attributes={"fillcolor": "red"})
                    # stacks_graph.edge(external_service_name, stack.service_name)
                    node_set_external.add(external_service_name)
                    edge_set_external.add((external_service_name, stack.service_name))

        for node in node_set_external:
            stacks_graph.node(node, _attributes={"fillcolor": "red"})

        for from_node, to_node in edge_set_external:
            stacks_graph.edge(from_node, to_node)

        # TODO deduplicate
        upstream_dependencies = self.config.projects[
            self.project_name
        ].upstream_dependencies

        for service_name, dependencies in upstream_dependencies.items():
            for dependency in dependencies:
                upstream_service = dependency.service
                stacks_graph.node(upstream_service, _attributes={"fillcolor": "blue"})
                stacks_graph.edge(service_name, upstream_service)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-services.gv"
        )

    def _visualize(
        self, exports_enriched: List[StackExport], stack_infos: List[StackInfo]
    ):  # TODO already filter before
        stacks_graph = Digraph(
            "StacksGraph",
            node_attr={"shape": "box", "style": "filled", "fillcolor": "grey"},
        )
        edge_set = set()
        node_set_important = set()
        node_set_all = set()
        node_set_has_downstream = set()

        for export in exports_enriched:
            node_set_all.add(export.exporting_stack_name)
            node_set_has_downstream.add(export.exporting_stack_name)
            for importing_stack in export.importing_stacks:
                edge_set.add((export.exporting_stack_name, importing_stack))
                node_set_all.add(importing_stack)

            if len(export.importing_stacks) > IMPORTANT_STACK_DEPENDENCY_TRESHOLD:
                node_set_important.add(export.exporting_stack_name)

        node_set_leafs = node_set_all - node_set_has_downstream
        logger.debug(f"node_set_important: {node_set_important}")
        logger.debug(f"node_set_leafs: {node_set_leafs}")

        for exporting_stack_name in node_set_important:
            node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "orange"})

        for exporting_stack_name in node_set_leafs:
            node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "green"})

        for exporting_stack_name, importing_stack in edge_set:
            from_node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            to_node = importing_stack.replace(f"{self.project_name}-{self.env}-", "")
            stacks_graph.edge(from_node, to_node)

        edge_set_external = set()
        node_set_external = set()

        for stack in stack_infos:
            for parameter in stack.parameters:
                if parameter.external_dependency is not None:
                    external_service_name = parameter.external_dependency.service_name
                    stack_name = stack.stack_name.replace(
                        f"{self._get_stack_prefix()}-", ""
                    )
                    node_set_external.add(external_service_name)
                    edge_set_external.add((external_service_name, stack_name))

        for node in node_set_external:
            stacks_graph.node(node, _attributes={"fillcolor": "red"})

        for from_node, to_node in edge_set_external:
            stacks_graph.edge(from_node, to_node)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-stacks.gv"
        )

    def _gather_stacks(self) -> Iterable[StackInfo]:
        paginator = self.cfn_client.get_paginator("list_stacks")
        # self.cfn_client.list_stacks() # TODO remove
        pages = paginator.paginate(
            StackStatusFilter=[
                "CREATE_IN_PROGRESS",
                "CREATE_COMPLETE",
                "ROLLBACK_COMPLETE",
                "DELETE_FAILED",
                "UPDATE_IN_PROGRESS",
                "UPDATE_COMPLETE",
                "UPDATE_ROLLBACK_FAILED",
                "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
                "UPDATE_ROLLBACK_COMPLETE",
                "REVIEW_IN_PROGRESS",
            ]
        )

        for page in pages:
            stacks = page["StackSummaries"]
            logger.debug(f"Nr of stacks in page: {len(stacks)}")
            for stack in stacks:
                stack_name = stack["StackName"]
                if stack_name.startswith(f"{self.project_name}-{self.env}"):
                    stack_detail_results = self.cfn_client.describe_stacks(
                        StackName=stack_name
                    )
                    stack_template_details_result = self.cfn_client.get_template_summary(
                        StackName=stack_name
                    )
                    stack_details = stack_detail_results["Stacks"][0]
                    stack_tags = stack_details["Tags"]
                    logger.debug(f"stack: {stack_name}")

                    parameters = self._extract_parameters(
                        stack_details, stack_template_details_result
                    )
                    service_name = self.service_tag_search.search(stack_tags)
                    if service_name is None:
                        service_name = self.service_tag2_search.search(stack_tags)
                    yield StackInfo(
                        stack_name=stack_name,
                        service_name=service_name,
                        parameters=parameters,
                    )
                    time.sleep(0.1)  # avoid throttling

    def _extract_parameters(
        self, stack_details: Dict, stack_template_details: Dict
    ) -> List[StackParameter]:
        params: Dict[str, StackParameter] = {}

        if "Parameters" not in stack_details:
            return []

        for parameter in stack_details["Parameters"]:
            name = parameter["ParameterKey"]
            value = parameter["ParameterValue"]
            params[name] = StackParameter(name=name, value=value)

        for parameter in stack_template_details["Parameters"]:
            # print(parameter)
            name = parameter["ParameterKey"]
            description = parameter.get("Description")
            # TODO exceptions
            external_dep = None
            if description and "|" in description:
                metadata_part = description.split("|")[1].strip()
                metadata = list(
                    [row for row in csv.reader([metadata_part], delimiter=",")]
                )[0]
                metadata_transformed = {
                    metadata_entry.split("=")[0]: metadata_entry.split("=")[1]
                    for metadata_entry in metadata
                }
                external_dep = ExternalDependency(
                    team_name=metadata_transformed["team"],
                    service_name=metadata_transformed["service"],
                )
                logger.info(f"{Fore.YELLOW}{external_dep}")

            params[name] = StackParameter(
                name=params[name].name,
                value=params[name].value,
                description=description,
                external_dependency=external_dep,
            )

        return list(params.values())

    def _gather_and_filter_exports(self, stacks: List[StackInfo]) -> List[StackExport]:
        exports_raw = self._gather_raw_exports()
        exports = list(self._extract_exports(exports_raw))
        logger.info(f"{Style.BRIGHT}Number of exports gathered: {len(exports)}")
        exports_enriched = list(self._match_exports_with_imports(exports))
        logger.info(
            f"{Style.BRIGHT}Number of import-enriched exports gathered: {len(exports_enriched)}"
        )
        exports_with_service_names = list(
            self._enrich_service_name(exports_enriched, stacks)
        )
        logger.info(
            f"{Style.BRIGHT}Number of import-enriched exports with service names gathered: {len(exports_with_service_names)}"
        )
        return exports_with_service_names

    def _get_stack_prefix(self) -> str:
        return f"{self.project_name}-{self.env}"

    def _extract_exports(self, raw_exports: List[Dict]) -> Iterable[StackExport]:
        for export in raw_exports:
            stack_id = export["ExportingStackId"]
            match = re.search(".*/(.*)/.*", stack_id)
            if match:
                stack = match.group(1)
                name = export["Name"]
                value = export["Value"]

                if stack.startswith(self._get_stack_prefix()):
                    yield StackExport(
                        export_name=name, exporting_stack_name=stack, export_value=value
                    )

    def _gather_raw_exports(self) -> List[Dict[Any, Any]]:
        should_paginate = True
        next_token = None
        exports: List[Dict[Any, Any]] = []
        logger.debug("Gather exports started")
        while should_paginate:
            logger.debug("Gather exports")  # TODO investigate pagniators
            result = (
                self.cfn_client.list_exports(NextToken=next_token)
                if next_token
                else self.cfn_client.list_exports()
            )
            next_token = result.get("NextToken", None)
            exports.extend(result["Exports"])
            if not next_token:
                should_paginate = False
        logger.debug("Gathered all exports")
        return exports

    def _match_exports_with_imports(
        self, exports: List[StackExport]
    ) -> Iterable[StackExport]:
        for export in exports:
            export_name = export.export_name
            should_paginate = True
            next_token = None
            imports: List[str] = []
            try:
                while should_paginate:
                    logger.debug(
                        f"Gather import stacks for export name: {export_name}"
                    )  # TODO investigate pagniators
                    result = (
                        self.cfn_client.list_imports(
                            ExportName=export_name, NextToken=next_token
                        )
                        if next_token
                        else self.cfn_client.list_imports(ExportName=export_name)
                    )
                    next_token = result.get("NextToken", None)
                    imports.extend(result["Imports"])
                    if not next_token:
                        should_paginate = False
            except ClientError as e:
                if "is not imported by any stack" in str(e):
                    continue
                else:
                    raise

            yield StackExport(
                export_name=export_name,
                exporting_stack_name=export.exporting_stack_name,
                export_value=export.export_value,
                importing_stacks=imports,
            )
