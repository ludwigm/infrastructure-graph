## Infrastructure Dependency visualization

This tool is looking at CloudFormation Export/Imports and visualizes them. It can additionally abstract and group dependencies at a higher level based on Tags attached on the involved CloudFormation tags.

In its default configuration it is looking for the tags `ServiceName/Service` and expects a stack naming scheme like the following:

```
reco-dev-storeloader-task-rfystorage
<project>-<env>-<component_name>
```

This things can be changed and need to be changed if you want to apply it in other accounts.

It generates GraphViz output in the `output` folder. Other additionally interesting information about the stacks is displayed in the stdout.


# Configuration

Rename the `config.hocon.template` to `config.hocon` and adapt if you have external dependencies depending on your services. Names need to match up

# How to execute

```
# create venv
poetry install
poetry shell
export-graph --help
export-graph
open output/
```

# Usage

```
Usage: export-graph [OPTIONS]

Options:
  -e, --env TEXT           On which environment to run this task. e.g. dev,
                           stg, prd  [default: dev]

  -t, --project-name TEXT  Project/Team name is expected of part of the
                           resource name and need to be specified here or
                           taken from config

  --help                   Show this message and exit.
```
