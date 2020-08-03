## Infrastructure Dependency visualization

![Python package](https://github.com/ludwigm/infrastructure-graph/workflows/Build%20and%20Test%20Python%20package/badge.svg)

This tool is looking at CloudFormation Export/Imports and visualizes them. It can additionally abstract and group dependencies at a higher level based on Tags attached on the involved CloudFormation tags.

In its default configuration it is looking for the tags `ServiceName/Service` , `ComponentName/Component`and expects a stack naming scheme like the following:

```
reco-dev-storeloader-task-rfystorage
<project>-<env>-<component_name>
```

This things can be changed and need to be changed if you want to apply it in other accounts.

This tool additionally looks for upstream external dependencies which are not in the targeted AWS account. It does that by looking for CloudFormation parameter descriptions with metadata embedded. The following is one example:
```
Parameters:
  ...
  SnowflakeAccount:
    Type: String
    Description: "The snowflake account name which is used to connect to. | team=Data,service=Snowflake"
```

It generates GraphViz output in the `output` folder. Other additionally interesting information about the stacks is displayed in the stdout and also exported as JSON.

# Installation

If you don't want to clone the repo it is also possible to install this tool via Pypi. I recommend pipx instead of pip to not clutter your local python environment:

```
pip install aws-infra-graph
pipx install aws-infra-graph
```


# Configuration

Rename the `config.hocon.template` to `config.hocon` and adapt if you have external downstream dependencies depending on your services.
Names need to match up with discovered service names.
Additionally it is also possible to specify internal manual dependencies like manully create infrastructure components.
In the configuration it is also possible to configure for which CloudFormation tags the higher level grouping is done.
Instead of having a config in your current folder you can also use `infra-graph init` which creates a config in `~/.config/aws-infra-graph/config.hocon`

# How to execute

In case you cloned the source the following is needed:

```
brew install graphviz # depends on the availability of the dot tool
poetry install
poetry shell
```

The following commands work now either in your poetry venv or if you installed the software before via pip/pipx.
```
infra-graph --help
infra-graph init
infra-graph export
open output/
```

Heavy operations like gathering data from AWS are cached to disk. In case you want to re-gather the data add the `--refresh` flag.

# Usage

```
Usage: infra-graph [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  export  Gather data about the infra and visualize them
  init    Initialize config after installation
```

```
Usage: infra-graph export [OPTIONS]

  Gather data about the infra and visualize them

Options:
  -e, --env TEXT             On which environment to run this task. e.g. dev,
                             stg, prd  [default: dev]

  -t, --project-name TEXT    Project/Team name is expected of part of the
                             resource name and need to be specified here or
                             taken from config

  -r, --refresh              In case of disc cached result clear them
                             beforehand

  -c, --cluster-stack-graph  Should the results of the stack graph be
                             clustered by service?

  -o, --output-folder TEXT   To which folder to export the generated files
  --help                     Show this message and exit.
```
