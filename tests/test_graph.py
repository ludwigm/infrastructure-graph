# Core Library
from typing import List

# Third party
from pyexpect import expect

# First party
from aws_infra_dependencies.model import (
    StackInfo,
    StackExport,
    StackParameter,
    ExternalDependency,
)
from aws_infra_dependencies.graph_exporter import InfraGraphExporter

EXPECTED_OUTPUT_FILES = {
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
        graph_exporter.export(refresh=True)

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
        graph_exporter.export(refresh=True)

        # THEN it should create output files
        resulting_files = {file.name for file in tmp_path.iterdir()}
        expect(resulting_files).to_equal(EXPECTED_OUTPUT_FILES)
        with open(tmp_path / "export-services.gv") as file:
            contents = file.read()
            # AND the expected dependencies to be in the output
            expect(contents).to_contain("Snowflake -> etl")
            expect(contents).to_contain("etl -> api")
            expect(contents).to_contain("api -> ExternalService")
