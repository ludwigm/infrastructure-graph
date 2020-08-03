#! /usr/bin/env python

# Core Library
import os
import logging
import collections
from typing import Set, Dict, List, Tuple, Counter, Optional, FrozenSet, DefaultDict
from collections import defaultdict
from dataclasses import dataclass

# Third party
import coloredlogs
from colorama import Fore, Style, init
from graphviz import Digraph

# First party
from aws_infra_graph.model import StackInfo, DataExport, StackExport
from aws_infra_graph.utils import SYSTEM_CACHE_ROOT
from aws_infra_graph.config import (
    InfraGraphConfig,
    ManualDependency,
    ManualInternalDependency,
    load_config,
)
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

Node = str
NodeSet = Set[Node]
EdgeSet = Set[Tuple[Node, Node]]


@dataclass
class NodeAndEdgesStackGraph:
    edges: EdgeSet
    edges_external: EdgeSet
    all_nodes: NodeSet
    important_nodes: NodeSet
    nodes_with_downstream_deps: NodeSet
    leaf_nodes: NodeSet
    external_nodes: NodeSet


@dataclass
class NodeAndEdgesServiceGraph:
    edges: EdgeSet
    external_edges: EdgeSet
    manual_downstream_edges: EdgeSet
    manual_internal_edges: EdgeSet
    internal_nodes: NodeSet
    external_nodes: NodeSet
    manual_downstream_nodes: NodeSet
    manual_internal_nodes: NodeSet


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
        output_folder: str,
        project_name: str,
        config_path: str = "./config.hocon",
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

    def export(self, refresh: bool, cluster_stack_graph: bool):
        if refresh:
            self.delete_caches()
        stack_infos = self.data_extractor.gather_stacks()
        self._print_stack_infos(stack_infos)
        statistics = self._get_statictics(stack_infos)
        self._print_statistics(statistics)
        exports = self.data_extractor.gather_and_filter_exports(stack_infos)
        imported_exports = [
            export for export in exports if len(export.importing_stacks) > 0
        ]
        self._print_export_infos(imported_exports)
        self._visualize_stacks(imported_exports, stack_infos, cluster_stack_graph)
        self._visualize_services(imported_exports, stack_infos)
        self._create_data_export(stack_infos, statistics, exports)
        logger.info(f"\nGraph and data exports finished in {self.output_folder} folder")

    @staticmethod
    def delete_caches():
        if not SYSTEM_CACHE_ROOT.exists():
            return

        files = (
            x
            for x in SYSTEM_CACHE_ROOT.iterdir()
            if x.is_file() and str(x).endswith(".cache")
        )
        for file in files:
            logger.info(f"Removing {str(file)}")
            file.unlink()

    def _create_data_export(
        self,
        stack_infos: List[StackInfo],
        statistics: Counter[str],
        stack_exports: List[StackExport],
    ):
        export = DataExport(
            stacks=stack_infos,
            resource_statistics=dict(statistics.most_common()),
            stack_exports=stack_exports,
        )
        with open(f"{self.output_folder}/export.json", "w") as write_file:
            write_file.write(export.json(indent=2))

    @staticmethod
    def _get_statictics(stack_infos: List[StackInfo]) -> Counter:
        counts: Counter[str] = collections.Counter()
        for stack_info in stack_infos:
            for resource in stack_info.resources:
                counts[resource.resource_type.replace("AWS::", "")] += 1
        return counts

    @staticmethod
    def _print_statistics(statistics):
        logger.info("\n")
        logger.info(f"{Fore.BLUE}Resource Statistics:")
        for resource_type, count in statistics.most_common():
            logger.info(f"\t{resource_type}: {count} resources")
        logger.info("\n")

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

        logger.info(f"{Fore.BLUE}Stacks resources:")
        for stack_info in stack_infos:
            logger.info(f"{Style.BRIGHT}\t{stack_info.stack_name}:")
            for resource in stack_info.resources:
                logger.info(
                    f"\t\t[{resource.resource_type}] {resource.logical_id}: {resource.physical_id}"
                )

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

        # TODO deduplicate
        downstream_dependencies = self.config.projects[
            self.project_name
        ].downstream_dependencies

        internal_manual_dependencies = self.config.projects[
            self.project_name
        ].internal_manual_dependencies

        nodes_and_edges = self._retrieve_nodes_and_edges_for_service_graph(
            exports_with_service_names,
            stack_infos,
            downstream_dependencies,
            internal_manual_dependencies,
        )

        for node in nodes_and_edges.internal_nodes:
            stacks_graph.node(node, label=f'<<font point-size="17">{node}</font>>')

        for export_service, importing_service in nodes_and_edges.edges:
            stacks_graph.edge(export_service, importing_service)

        for node in nodes_and_edges.external_nodes:  # TODO add team name
            stacks_graph.node(
                node,
                _attributes={"fillcolor": "tomato"},
                label=f'<<font point-size="19">{node}</font>>',
            )

        for from_node, to_node in nodes_and_edges.external_edges:
            stacks_graph.edge(from_node, to_node)

        for node in nodes_and_edges.manual_downstream_nodes:
            stacks_graph.node(
                node,
                _attributes={"fillcolor": "skyblue"},
                label=f'<<font point-size="19">{node}</font>>',
            )

        for from_node, to_node in nodes_and_edges.manual_downstream_edges:
            stacks_graph.edge(from_node, to_node)

        for node in nodes_and_edges.manual_internal_nodes:
            stacks_graph.node(
                node,
                _attributes={"fillcolor": "grey68", "style": "dotted, filled"},
                label=f'<<font point-size="17">{node}</font>>',
            )

        for from_node, to_node in nodes_and_edges.manual_internal_edges:
            stacks_graph.edge(from_node, to_node)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-services.gv"
        )

    def _visualize_stacks(
        self,
        exports_enriched: List[StackExport],
        stack_infos: List[StackInfo],
        should_cluster: bool,
    ) -> None:  # TODO already filter before
        stacks_graph = Digraph(
            "StacksGraph",
            node_attr={"shape": "box", "style": "filled", "fillcolor": "grey"},
        )
        stacks_graph.attr(
            rankdir="LR", label="Stack Dependencies", labelloc="t", fontsize="20"
        )

        stacks_service_names: Dict[str, Optional[str]] = {
            self._remove_stack_prefix(stack.stack_name): stack.service_name
            for stack in stack_infos
        }

        nodes_and_edges = self._retrieve_nodes_and_edges_for_stacks_graph(
            exports_enriched, stack_infos
        )

        logger.debug(f"node_set_important: {nodes_and_edges.important_nodes}")
        logger.debug(f"node_set_leafs: {nodes_and_edges.leaf_nodes}")

        if should_cluster:
            partitioned_node_set_all = self._partition_node_set(
                nodes_and_edges.all_nodes, stacks_service_names
            )
            for service, nodes in partitioned_node_set_all:
                if service:
                    with stacks_graph.subgraph(name=f"cluster_{service}") as subgraph:
                        subgraph.attr(label=service)
                        for node in nodes:
                            subgraph.node(
                                node,
                                _attributes={
                                    "fillcolor": self._determine_node_color(
                                        node,
                                        nodes_and_edges.important_nodes,
                                        nodes_and_edges.leaf_nodes,
                                    )
                                },
                            )
                else:
                    for node in nodes:
                        stacks_graph.node(
                            node,
                            _attributes={
                                "fillcolor": self._determine_node_color(
                                    node,
                                    nodes_and_edges.important_nodes,
                                    nodes_and_edges.leaf_nodes,
                                )
                            },
                        )
        else:
            for node in nodes_and_edges.all_nodes:
                stacks_graph.node(
                    node,
                    _attributes={
                        "fillcolor": self._determine_node_color(
                            node,
                            nodes_and_edges.important_nodes,
                            nodes_and_edges.leaf_nodes,
                        )
                    },
                )

        for from_node, to_node in nodes_and_edges.edges:
            stacks_graph.edge(from_node, to_node)

        for node in nodes_and_edges.external_nodes:
            stacks_graph.node(node, _attributes={"fillcolor": "tomato"})

        for from_node, to_node in nodes_and_edges.edges_external:
            stacks_graph.edge(from_node, to_node)

        stacks_graph.render(
            format="png", filename=f"{self.output_folder}/export-stacks.gv"
        )

    @staticmethod
    def _retrieve_nodes_and_edges_for_service_graph(
        exports: List[StackExport],
        stack_infos: List[StackInfo],
        downstream_dependencies: Dict[str, List[ManualDependency]],
        internal_manual_dependencies: Dict[str, List[ManualInternalDependency]],
    ) -> NodeAndEdgesServiceGraph:
        edge_set = set()
        node_set_internal = set()
        edge_set_external = set()
        node_set_external = set()
        manual_downstream_nodes = set()
        manual_downstream_edges = set()
        manual_internal_nodes = set()
        manual_internal_edges = set()
        for export in exports:
            for importing_service in export.importing_services:
                if export.export_service != importing_service:  # no reflexive
                    exporting_service = export.export_service or "Unknown"
                    edge_set.add((exporting_service, importing_service))
                    node_set_internal.add(exporting_service)
                    node_set_internal.add(importing_service)

        for stack in stack_infos:
            for parameter in stack.parameters:
                if parameter.external_dependency is not None:
                    external_service_name = parameter.external_dependency.service_name
                    internal_service_name = stack.service_name or "Unknown"
                    node_set_external.add(external_service_name)
                    edge_set_external.add(
                        (external_service_name, internal_service_name)
                    )

        for service_name, dependencies in downstream_dependencies.items():
            for dependency in dependencies:
                downstream_service = dependency.service
                manual_downstream_nodes.add(downstream_service)
                manual_downstream_edges.add((service_name, downstream_service))

        for service_name, internal_dependencies in internal_manual_dependencies.items():
            for internal_dependency in internal_dependencies:
                upstream_service = internal_dependency.service
                manual_internal_nodes.add(upstream_service)
                manual_internal_edges.add((upstream_service, service_name))

        return NodeAndEdgesServiceGraph(
            edges=edge_set,
            external_edges=edge_set_external,
            manual_downstream_edges=manual_downstream_edges,
            manual_internal_edges=manual_internal_edges,
            internal_nodes=node_set_internal,
            external_nodes=node_set_external,
            manual_internal_nodes=manual_internal_nodes,
            manual_downstream_nodes=manual_downstream_nodes,
        )

    def _retrieve_nodes_and_edges_for_stacks_graph(
        self, exports_enriched: List[StackExport], stack_infos: List[StackInfo]
    ) -> NodeAndEdgesStackGraph:
        edge_set = set()
        node_set_important = set()
        node_set_all = set()
        node_set_has_downstream = set()
        edge_set_external = set()
        node_set_external = set()

        for export in exports_enriched:
            exporting_stack_name_short = self._remove_stack_prefix(
                export.exporting_stack_name
            )
            node_set_all.add(exporting_stack_name_short)
            node_set_has_downstream.add(exporting_stack_name_short)
            for importing_stack in export.importing_stacks:
                importing_stack_short = self._remove_stack_prefix(importing_stack)
                edge_set.add((exporting_stack_name_short, importing_stack_short))
                node_set_all.add(importing_stack_short)
                logger.info(importing_stack)

            if len(export.importing_stacks) > IMPORTANT_STACK_DEPENDENCY_TRESHOLD:
                node_set_important.add(exporting_stack_name_short)

        for stack in stack_infos:
            for parameter in stack.parameters:
                if parameter.external_dependency is not None:
                    external_service_name = parameter.external_dependency.service_name
                    stack_name = self._remove_stack_prefix(stack.stack_name)
                    node_set_all.add(stack_name)
                    node_set_external.add(external_service_name)
                    edge_set_external.add((external_service_name, stack_name))

        node_set_leafs = node_set_all - node_set_has_downstream

        return NodeAndEdgesStackGraph(
            edges=edge_set,
            edges_external=edge_set_external,
            all_nodes=node_set_all,
            important_nodes=node_set_important,
            nodes_with_downstream_deps=node_set_has_downstream,
            leaf_nodes=node_set_leafs,
            external_nodes=node_set_external,
        )

    def _determine_node_color(
        self, current_node: str, node_set_important: Set[str], node_set_leafs: Set[str]
    ):
        if current_node in node_set_important:
            return "orange"
        elif current_node in node_set_leafs:
            return "green"
        else:
            return "gray"

    def _remove_stack_prefix(self, stack_name: str):
        return stack_name.replace(f"{self.stack_prefix}-", "")

    @staticmethod
    def _partition_node_set(
        nodes: Set[str], stacks_service_names: Dict[str, Optional[str]]
    ) -> Set[Tuple[Optional[str], FrozenSet[str]]]:
        partitioned_map: Dict[Optional[str], Set[str]] = defaultdict(set)
        for node in nodes:
            partitioned_map[stacks_service_names.get(node)].add(node)

        return {(key, frozenset(value)) for key, value in partitioned_map.items()}
