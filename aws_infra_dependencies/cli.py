#! /usr/bin/env python

# Core Library
import os
import logging

# Third party
import click
from colorama import Fore

# First party
from aws_infra_dependencies.graph_exporter import InfraGraphExporter

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
    help="On which environment to run this task. e.g. dev, stg, prd",
)
@click.option(
    "-t",
    "--project-name",
    "project_name",
    required=False,
    help="Project/Team name is expected of part of the resource name and need to be specified here or taken from config",
)
def export_infra_graph(env: str, project_name: str):
    logger.info(f"{Fore.BLUE}Starting infra export for {env}. Can take some minutes.")
    exporter = InfraGraphExporter(env, project_name)
    exporter.export()


if __name__ == "__main__":
    export_infra_graph()
