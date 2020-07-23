#! /usr/bin/env python

# Core Library
import os
import logging
from typing import List, Optional, DefaultDict
from pathlib import Path
from collections import defaultdict

# Third party
import coloredlogs
from colorama import Fore, Style, init
from graphviz import Digraph

# First party
from aws_infra_graph.model import StackInfo, StackExport
from aws_infra_graph.config import InfraGraphConfig, load_config
from aws_infra_graph.data_extractor import DataExtractor, IDataExtractor

init(autoreset=True)

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)
coloredlogs.install(
    level=os.getenv("LOG_LEVEL", "INFO"),
    fmt="[%(levelname)s] %(message)s",
    logger=logger,
)

IMPORTANT_STACK_DEPENDENCY_TRESHOLD = 4


class InfraGraphExporter:
    config: InfraGraphConfig
    data_extractor: IDataExtractor
    output_folder: str
    env: str
    project_name: str
    stack_prefix: str

    def __init__(
        self,
        env: str,
        project_name: Optional[str] = None,
        config_path: str = "./config.hocon",
        output_folder: str = "./output",
        data_extractor: Optional[IDataExtractor] = None,
    ):
        self.config = load_config(config_path)
        self.output_folder = output_folder
        self.env = env
        self.project_name = (
            project_name if project_name else self.config.default_project
        )
        self.stack_prefix = f"{self.project_name}-{self.env}"
        if not data_extractor:
            self.data_extractor = DataExtractor(
                self.stack_prefix,
                service_tags=self.config.service_tags,
                component_tags=self.config.component_tags,
            )
        else:
            self.data_extractor = data_extractor

    def export(self, refresh: bool):
        if refresh:
            self.delete_caches()
        stack_infos = self.data_extractor.gather_stacks()
        self._print_stack_infos(stack_infos)
        exports = self.data_extractor.gather_and_filter_exports(stack_infos)
        imported_exports = [
            export for export in exports if len(export.importing_stacks) > 0
        ]
        self._print_export_infos(imported_exports)
        self._visualize_stacks(imported_exports, stack_infos)
        self._visualize_services(imported_exports, stack_infos)
        logger.info(f"\nGraph exports finished in {self.output_folder} folder")

    @staticmethod
    def delete_caches():
        files = (
            x for x in Path(".").iterdir() if x.is_file() and str(x).endswith(".cache")
        )
        for file in files:
            logger.info(f"Removing {str(file)}")
            file.unlink()

    @staticmethod
    def _print_export_infos(exports: List[StackExport]) -> None:
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

    @staticmethod
    def _print_stack_infos(stack_infos: List[StackInfo]) -> None:
        logger.info("\n")
        logger.info(f"{Fore.BLUE}Stacks without service name:")
        grouped_by_service: DefaultDict[str, List[StackInfo]] = defaultdict(list)
        for stack_info in stack_infos:
            if stack_info.service_name is None:
                logger.info(stack_info)
            else:
                grouped_by_service[stack_info.service_name].append(stack_info)

        logger.info("\n")

        logger.info(f"{Fore.BLUE}Stacks grouped by service name:")
        for service, stacks in grouped_by_service.items():
            logger.info(f"{Style.BRIGHT}\t{service}:")
            for stack in stacks:
                logger.info(f"\t\t{stack.stack_name} [{stack.component_name}]")

        logger.info("\n")

        logger.info(f"{Fore.BLUE}Stacks parameters:")
        for stack_info in stack_infos:
            logger.info(f"{Style.BRIGHT}\t{stack_info.stack_name}:")
            for param in stack_info.parameters:
                description = f"[{param.description}]" if param.description else ""
                logger.info(f"\t\t{param.name}: {param.value} {description}")
                if param.external_dependency:
                    logger.info(f"\t\t{Fore.YELLOW}{param.external_dependency}")

        logger.info("\n")

    def _visualize_services(
        self,
        exports_with_service_names: List[StackExport],
        stack_infos: List[StackInfo],
    ) -> None:
        stacks_graph = Digraph(
            "StacksGraph",
            node_attr={"shape": "box", "style": "filled", "fillcolor": "grey"},
        )
        stacks_graph.attr(
            rankdir="LR", label="Service Dependencies", labelloc="t", fontsize="20"
        )
        edge_set = set()
        node_set_internal = set()
        for export in exports_with_service_names:
            for importing_service in export.importing_services:
                if export.export_service != importing_service:  # no reflexive
                    edge_set.add((export.export_service, importing_service))
                    node_set_internal.add(export.export_service)
                    node_set_internal.add(importing_service)

        for node in node_set_internal:
            # TODO does this really work?
            stacks_graph.node(node, label=f'<<font point-size="17">{node}</font>>')

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

        for node in node_set_external:  # TODO add team name
            stacks_graph.node(
                node,
                _attributes={"fillcolor": "tomato"},
                label=f'<<font point-size="19">{node}</font>>',
            )

        for from_node, to_node in edge_set_external:
            stacks_graph.edge(from_node, to_node)

        # TODO deduplicate
        downstream_dependencies = self.config.projects[
            self.project_name
        ].downstream_dependencies

        internal_manual_dependencies = self.config.projects[
            self.project_name
        ].internal_manual_dependencies

        for service_name, dependencies in downstream_dependencies.items():
            for dependency in dependencies:
                downstream_service = dependency.service
                stacks_graph.node(
                    downstream_service,
                    _attributes={"fillcolor": "skyblue"},
                    label=f'<<font point-size="19">{downstream_service}</font>>',
                )
                stacks_graph.edge(service_name, downstream_service)

        for service_name, internal_dependencies in internal_manual_dependencies.items():
            for internal_dependency in internal_dependencies:
                upstream_service = internal_dependency.service
                stacks_graph.node(
                    upstream_service,
                    _attributes={"fillcolor": "grey68", "style": "dotted, filled"},
                    label=f'<<font point-size="17">{upstream_service}</font>>',
                )
                stacks_graph.edge(upstream_service, service_name)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-services.gv"
        )

    # TODO try grouping by services where possible with subgraphs
    def _visualize_stacks(
        self, exports_enriched: List[StackExport], stack_infos: List[StackInfo]
    ) -> None:  # TODO already filter before
        stacks_graph = Digraph(
            "StacksGraph",
            node_attr={"shape": "box", "style": "filled", "fillcolor": "grey"},
        )
        stacks_graph.attr(
            rankdir="LR", label="Stack Dependencies", labelloc="t", fontsize="20"
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
            node = exporting_stack_name.replace(f"{self.stack_prefix}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "orange"})

        for exporting_stack_name in node_set_leafs:
            node = exporting_stack_name.replace(f"{self.stack_prefix}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "green"})

        for exporting_stack_name, importing_stack in edge_set:
            from_node = exporting_stack_name.replace(f"{self.stack_prefix}-", "")
            to_node = importing_stack.replace(f"{self.project_name}-{self.env}-", "")
            stacks_graph.edge(from_node, to_node)

        edge_set_external = set()
        node_set_external = set()

        for stack in stack_infos:
            for parameter in stack.parameters:
                if parameter.external_dependency is not None:
                    external_service_name = parameter.external_dependency.service_name
                    stack_name = stack.stack_name.replace(f"{self.stack_prefix}-", "")
                    node_set_external.add(external_service_name)
                    edge_set_external.add((external_service_name, stack_name))

        for node in node_set_external:
            stacks_graph.node(node, _attributes={"fillcolor": "tomato"})

        for from_node, to_node in edge_set_external:
            stacks_graph.edge(from_node, to_node)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-stacks.gv"
        )
