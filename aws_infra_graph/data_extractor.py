#! /usr/bin/env python

# Core Library
import os
import re
import csv
import time
import logging
from typing import Any, Dict, List, Iterable, Optional, Protocol

# Third party
import boto3
import coloredlogs
from colorama import Style
from colorama.ansi import Fore
from botocore.exceptions import ClientError
from boto3_type_annotations import cloudformation

# First party
from aws_infra_graph.model import (
    StackInfo,
    StackExport,
    StackResource,
    StackParameter,
    ExternalDependency,
)
from aws_infra_graph.utils import file_cached, build_tag_search_patterns

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="[%(levelname)s] %(message)s", level=os.getenv("LOG_LEVEL", "INFO")
)
coloredlogs.install(
    level=os.getenv("LOG_LEVEL", "INFO"),
    fmt="[%(levelname)s] %(message)s",
    logger=logger,
)


class IDataExtractor(Protocol):
    def gather_and_filter_exports(self, stacks: List[StackInfo]) -> List[StackExport]:
        ...

    def gather_stacks(self) -> List[StackInfo]:
        ...


class DataExtractor:
    stack_prefix: str
    cfn_client: cloudformation.Client

    def __init__(
        self, stack_prefix: str, service_tags: List[str], component_tags: List[str]
    ) -> None:
        self.stack_prefix = stack_prefix
        self.cfn_client = boto3.client("cloudformation")
        self.service_tag_search_patterns = build_tag_search_patterns(service_tags)
        self.component_tag_search_patterns = build_tag_search_patterns(component_tags)

    @file_cached("gather_and_filter_exports.cache")
    def gather_and_filter_exports(self, stacks: List[StackInfo]) -> List[StackExport]:
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

    @file_cached("gather_stacks.cache")
    def gather_stacks(self) -> List[StackInfo]:
        logger.info(f"{Fore.BLUE}Gather data. Can take some minutes.")
        return list(self._gather_stacks_gen())

    def _gather_stacks_gen(self) -> Iterable[StackInfo]:
        paginator = self.cfn_client.get_paginator("list_stacks")
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
                if stack_name.startswith(self._get_stack_prefix()):
                    yield self._gather_stack_info(stack_name)
                    time.sleep(0.1)  # avoid throttling

    def _gather_stack_info(self, stack_name) -> StackInfo:
        stack_detail_results = self.cfn_client.describe_stacks(StackName=stack_name)
        stack_template_details_result = self.cfn_client.get_template_summary(
            StackName=stack_name
        )
        stack_resource_details = self.cfn_client.describe_stack_resources(
            StackName=stack_name
        )
        stack_details = stack_detail_results["Stacks"][0]
        stack_tags = stack_details["Tags"]
        logger.debug(f"stack: {stack_name}")
        resources = self._extract_resources(stack_resource_details["StackResources"])
        parameters = self._extract_parameters(
            stack_details, stack_template_details_result
        )
        service_name = self._get_service_name(stack_tags)
        component_name = self._get_component_name(stack_tags)
        return StackInfo(
            stack_name=stack_name,
            service_name=service_name,
            component_name=component_name,
            parameters=parameters,
            resources=resources,
        )

    @staticmethod
    def _extract_resources(resource_details: Dict):
        return [
            StackResource(
                logical_id=resource_detail["LogicalResourceId"],
                physical_id=resource_detail.get("PhysicalResourceId"),
                resource_type=resource_detail["ResourceType"],
            )
            for resource_detail in resource_details
        ]

    def _get_service_name(self, stack_tags) -> Optional[str]:
        return next(
            (
                result
                for pattern in self.service_tag_search_patterns
                if (result := pattern.search(stack_tags)) is not None
            ),
            None,
        )

    def _get_component_name(self, stack_tags) -> Optional[str]:
        return next(
            (
                result
                for pattern in self.component_tag_search_patterns
                if (result := pattern.search(stack_tags)) is not None
            ),
            None,
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

    @staticmethod
    def _extract_parameters(
        stack_details: Dict, stack_template_details: Dict
    ) -> List[StackParameter]:
        params: Dict[str, StackParameter] = {}

        if "Parameters" not in stack_details:
            return []

        for parameter in stack_details["Parameters"]:
            name = parameter["ParameterKey"]
            value = parameter["ParameterValue"]
            params[name] = StackParameter(name=name, value=value)

        for parameter in stack_template_details["Parameters"]:
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

            params[name] = StackParameter(
                name=params[name].name,
                value=params[name].value,
                description=description,
                external_dependency=external_dep,
            )

        return list(params.values())

    def _get_stack_prefix(self) -> str:
        return self.stack_prefix

    def _extract_exports(self, raw_exports: List[Dict]) -> Iterable[StackExport]:
        return [
            extracted_export
            for export in raw_exports
            if (extracted_export := self._extract_export(export))
        ]

    def _extract_export(self, raw_export: Dict):
        stack_id = raw_export["ExportingStackId"]
        match = re.search(".*/(.*)/.*", stack_id)
        if match:
            stack = match.group(1)
            name = raw_export["Name"]
            value = raw_export["Value"]

            if stack.startswith(self._get_stack_prefix()):
                return StackExport(
                    export_name=name, exporting_stack_name=stack, export_value=value
                )

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

    @staticmethod
    def _enrich_service_name(
        exports_enriched: List[StackExport], stack_infos: List[StackInfo]
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
