#! /usr/bin/env python

# Core Library
import os
import logging

# Third party
import click
import coloredlogs
from colorama import Fore

# First party
from aws_infra_graph.config import init_config
from aws_infra_graph.graph_exporter import InfraGraphExporter

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


@click.group("infra-graph")
def main():
    pass


@main.command("export", help="Gather data about the infra and visualize them")
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
@click.option(
    "-r",
    "--refresh",
    "refresh",
    is_flag=True,
    default=False,
    required=False,
    type=bool,
    help="In case of disc cached result clear them beforehand",
)
def export(env: str, project_name: str, refresh: bool):
    logger.info(f"{Fore.BLUE}Starting infra export for {env}. Can take some minutes.")
    exporter = InfraGraphExporter(env, project_name)
    exporter.export(refresh)


@main.command("init", help="Initialize config after installation")
def init():
    logger.info("Init config")
    init_config()
