#! /usr/bin/env python

import click
import os
import logging
import boto3
import re
from typing import List
from boto3_type_annotations import cloudformation
from collections import defaultdict
from dataclasses import dataclass, field
from botocore.exceptions import ClientError
from graphviz import Digraph
import jmespath
import time

logger = logging.getLogger()
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)

IMPORTANT_STACK_DEPENDENCY_TRESHOLD = 4


@click.command()
@click.option(
    "-e",
    "--env",
    "env",
    default="dev",
    show_default=True,
    help="On which environment to run this task",
)
@click.option(
    "-t", "--team-name", "team_name", default="reco", show_default=True, help="TODO"
)
def export_infra_graph(env: str, team_name):
    logger.info(f"Starting infra export for {env}")
    exporter = InfraGraphExporter(env, team_name)
    exporter.export()

@dataclass
class StackInfo:
    stack_name: str
    service_name: str

@dataclass
class StackExport:
    export_name: str
    export_value: str
    exporting_stack_name: str
    importing_stacks: List[str] = field(default_factory=list)
    export_service: str = None
    importing_services: List[str] = field(default_factory=list)


class InfraGraphExporter:
    env: str
    team_name: str
    cfn_client: cloudformation.Client

    def __init__(self, env, team_name):
        self.cfn_client = boto3.client("cloudformation")
        self.env = env
        self.team_name = team_name
        # Replace with your own tag you want to group on to aggregate on higher level
        self.service_tag_search = jmespath.compile("[?Key==`ServiceName`]|[0]|Value")
        self.service_tag2_search = jmespath.compile("[?Key==`Service`]|[0]|Value") # TODO align in infra

    def export(self):
        stack_infos = list(self._gather_stacks())
        self._print_stack_infos(stack_infos)
        exports = list(self._gather_and_filter_exports())
        logger.info(f"Number of exports gathered: {len(exports)}")
        exports_enriched = list(self._gather_imports(exports))
        logger.info(f"Number of enriched exports gathered: {len(exports_enriched)}")

        logger.info("Export details")
        for export in exports_enriched:
            if len(export.importing_stacks) > 0: # TODO
                logger.info(
                    f"{export.exporting_stack_name}: {export.export_name} [{export.export_value}] -> {export.importing_stacks}"
                )

        self._visualize([export for export in exports_enriched if len(export.importing_stacks) > 0])

        exports_with_service_names = list(self._enrich_service_name(exports_enriched, stack_infos))

        logger.info("Export details with service names")
        for export in exports_with_service_names:
            if len(export.importing_stacks) > 0: # TODO
                logger.info( # TODO seperate or remove reflexive relationships
                    f"{export.export_name} [{export.export_service}] -> {export.importing_services}"
                )

        self._visualize_services([export for export in exports_with_service_names if len(export.importing_stacks) > 0])


    def _enrich_service_name(self, exports_enriched, stack_infos):
        grouped_by_stack = {}
        for stack_info in stack_infos:
            if stack_info.service_name is not None:
                grouped_by_stack[stack_info.stack_name] = stack_info.service_name

        for export in exports_enriched:
            service_name = grouped_by_stack[export.exporting_stack_name]
            importing_services = [grouped_by_stack[importing_stack] for importing_stack in export.importing_stacks if grouped_by_stack.get(importing_stack) is not None]
            yield StackExport(
                export_name=export.export_name,
                exporting_stack_name=export.exporting_stack_name,
                export_value=export.export_value,
                export_service=service_name,
                importing_stacks=export.importing_stacks,
                importing_services=importing_services
            )
        

    def _print_stack_infos(self, stack_infos: List[StackInfo]):
        logger.info("Stack without ServiceName:")
        grouped_by_service = defaultdict(list)
        for stack_info in stack_infos:
            if stack_info.service_name is None:
                logger.info(stack_info)
            else:
                grouped_by_service[stack_info.service_name].append(stack_info.stack_name)
                

        logger.info(grouped_by_service)


    def _visualize_services(self, exports_with_service_names):
        stacks_graph = Digraph('StacksGraph', node_attr={'shape': 'box', 'style': 'filled', 'fillcolor':'grey'})
        edge_set = set()
        for export in exports_with_service_names:
            for importing_service in export.importing_services:
                if export.export_service != importing_service: # no reflexive
                    edge_set.add((export.export_service, importing_service))

        for export_service, importing_service in edge_set:
            stacks_graph.edge(export_service, importing_service)

        stacks_graph.render(format="png", filename='output/export-services.gv')

    def _visualize(self, exports_enriched): # TODO already filter before
        stacks_graph = Digraph('StacksGraph', node_attr={'shape': 'box', 'style': 'filled', 'fillcolor':'grey'})
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
        logger.info(f"node_set_important: {node_set_important}")
        logger.info(f"node_set_leafs: {node_set_leafs}")
        
        for exporting_stack_name in node_set_important:
            node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "orange"})

        for exporting_stack_name in node_set_leafs:
            node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            stacks_graph.node(node, _attributes={"fillcolor": "green"})

        for exporting_stack_name, importing_stack in edge_set:
            from_node = exporting_stack_name.replace(f"{self._get_stack_prefix()}-", "")
            to_node = importing_stack.replace(f"{self.team_name}-{self.env}-", "")
            stacks_graph.edge(from_node, to_node)

        stacks_graph.render(format="png", filename='output/export-stacks.gv')

    def _gather_stacks(self):
        paginator = self.cfn_client.get_paginator('list_stacks')
        self.cfn_client.list_stacks()
        pages = paginator.paginate(StackStatusFilter=[
            "CREATE_IN_PROGRESS",
            'CREATE_COMPLETE',
            'ROLLBACK_COMPLETE',
            'DELETE_FAILED',
            'UPDATE_IN_PROGRESS',
            'UPDATE_COMPLETE',
            'UPDATE_ROLLBACK_FAILED',
            'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
            'UPDATE_ROLLBACK_COMPLETE',
            'REVIEW_IN_PROGRESS'])

        for page in pages:
            stacks = page['StackSummaries']
            logger.info(f"Nr of stacks in page: {len(stacks)}")
            for stack in stacks:
                stack_name = stack['StackName']
                if stack_name.startswith(f"{self.team_name}-{self.env}"):
                    stack_detail_results = self.cfn_client.describe_stacks(StackName=stack_name)
                    stack_details = stack_detail_results["Stacks"][0]
                    stack_tags = stack_details["Tags"]
                    logger.info(f"stack: {stack_name}")
                    service_name = self.service_tag_search.search(stack_tags)
                    if service_name is None:
                        service_name = self.service_tag2_search.search(stack_tags)
                    yield StackInfo(stack_name=stack_name, service_name=service_name)
                    time.sleep(0.1) # avoid throttling
        

    def _gather_and_filter_exports(self):
        exports = self._gather_exports()

        for export in exports:
            stack_id = export["ExportingStackId"]
            stack = re.search(".*/(.*)/.*", stack_id).group(1)
            name = export["Name"]
            value = export["Value"]

            if stack.startswith(self._get_stack_prefix()):
                yield StackExport(
                    export_name=name, exporting_stack_name=stack, export_value=value
                )

    def _get_stack_prefix(self):
        return f"{self.team_name}-{self.env}"

    def _gather_exports(self):
        should_paginate = True
        next_token = None
        exports = []
        logger.info("Gather exports started")
        while should_paginate:
            logger.info("Gather exports")  # TODO investigate pagniators
            result = (
                self.cfn_client.list_exports(NextToken=next_token)
                if next_token
                else self.cfn_client.list_exports()
            )
            next_token = result.get("NextToken", None)
            exports.extend(result["Exports"])
            if not next_token:
                should_paginate = False
        logger.info("Gathered all exports")
        return exports

    def _gather_imports(self, exports: List[StackExport]):
        for export in exports:
            export_name = export.export_name
            should_paginate = True
            next_token = None
            imports = []
            try:
                while should_paginate:
                    logger.info(
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


if __name__ == "__main__":
    export_infra_graph()
