# Core Library
from typing import List
from collections import Counter

# Third party
from pyexpect import expect

# First party
from aws_infra_graph.model import (
    StackInfo,
    StackExport,
    StackResource,
    StackParameter,
    ExternalDependency,
)
from aws_infra_graph.graph_exporter import InfraGraphExporter

EXPECTED_OUTPUT_FILES = {
    "export.json",
    "export-services.gv",
    "export-services.gv.png",
    "export-stacks.gv",
    "export-stacks.gv.png",
}


class FakeDataExtractor:
    def __init__(
        self, stack_infos: List[StackInfo], stack_exports: List[StackExport]
    ) -> None:
        self.stack_infos = stack_infos
        self.stack_exports = stack_exports

    def gather_and_filter_exports(self, stacks: List[StackInfo]) -> List[StackExport]:
        return self.stack_exports

    def gather_stacks(self) -> List[StackInfo]:
        return self.stack_infos


class TestGraph:
    def test_export_empty(self, tmp_path):
        """Graph :: can be exported without failure even if empty"""

        # GIVEN an empty infra
        stack_infos = []
        stack_exports = []
        graph_exporter = InfraGraphExporter(
            "dev",
            "testTeam",
            "tests/test_config.hocon",
            str(tmp_path),
            FakeDataExtractor(stack_infos, stack_exports),
        )

        # WHEN i try to export it
        graph_exporter.export(refresh=True, cluster_stack_graph=False)

        # THEN it should create output files
        resulting_files = {file.name for file in tmp_path.iterdir()}
        expect(resulting_files).to_equal(EXPECTED_OUTPUT_FILES)

    def test_export_filled(self, tmp_path):
        """Graph :: can be exported without failure with contents"""

        # GIVEN an filed infra
        stack_infos = [
            StackInfo(
                stack_name="dev-teamName-api",
                service_name="api",
                component_name="service",
                resources=[],
            ),
            StackInfo(
                stack_name="dev-teamName-etl",
                service_name="etl",
                component_name="task",
                parameters=[
                    StackParameter(
                        name="datawarehouseHost",
                        value="fake",
                        external_dependency=ExternalDependency("data", "Snowflake"),
                    )
                ],
                resources=[],
            ),
        ]
        stack_exports = [
            StackExport(
                export_name="etl-data-path",
                export_value="fake",
                exporting_stack_name="dev-teamName-etl",
                importing_stacks=["dev-teamName-api"],
                importing_services=["api"],
                export_service="etl",
            )
        ]
        graph_exporter = InfraGraphExporter(
            "dev",
            "testTeam",
            "tests/test_config.hocon",
            str(tmp_path),
            FakeDataExtractor(stack_infos, stack_exports),
        )

        # WHEN i try to export it
        graph_exporter.export(refresh=True, cluster_stack_graph=False)

        # THEN it should create output files
        resulting_files = {file.name for file in tmp_path.iterdir()}
        expect(resulting_files).to_equal(EXPECTED_OUTPUT_FILES)
        with open(tmp_path / "export-services.gv") as file:
            contents = file.read()
            # AND the expected dependencies to be in the output
            expect(contents).to_contain("Snowflake -> etl")
            expect(contents).to_contain("etl -> api")
            expect(contents).to_contain("api -> ExternalService")

    def test_partition_node_set(self):
        """Graph :: can partition a node set by service name"""

        # GIVEN
        nodes = {"a", "b", "c", "d", "e"}
        stacks_service_names = {
            "a": "service1",
            "b": "service1",
            "c": None,
            "d": "service2",
            "e": "service2",
        }

        # WHEN
        result = InfraGraphExporter._partition_node_set(nodes, stacks_service_names)

        # THEN
        expected = set(
            [
                ("service1", frozenset({"a", "b"})),
                (None, frozenset({"c"})),
                ("service2", frozenset({"d", "e"})),
            ]
        )
        expect(result).to_equal(expected)

    def test_resource_statistics(self):
        """Graph :: can gather count statistics of resource types"""
        # GIVEN
        stack_infos = [
            StackInfo(
                stack_name="dev-teamName-api",
                service_name="api",
                component_name="service",
                resources=[
                    StackResource(
                        logical_id="ResourceA",
                        physical_id="api-resource-a",
                        resource_type="AWS::IAM::Role",
                    ),
                    StackResource(
                        logical_id="ResourceB",
                        physical_id="api-resource-b",
                        resource_type="AWS::ECS::Service",
                    ),
                ],
            ),
            StackInfo(
                stack_name="dev-teamName-etl",
                service_name="etl",
                component_name="task",
                resources=[
                    StackResource(
                        logical_id="ResourceA",
                        physical_id="etl-resource-a",
                        resource_type="AWS::Logs::LogGroup",
                    ),
                    StackResource(
                        logical_id="ResourceB",
                        physical_id="etl-resource-b",
                        resource_type="AWS::ECS::Service",
                    ),
                ],
            ),
        ]

        # WHEN
        statistics = InfraGraphExporter._get_statictics(stack_infos)

        # THEN
        expect(statistics).to_equal(
            Counter({"Logs::LogGroup": 1, "ECS::Service": 2, "IAM::Role": 1})
        )
