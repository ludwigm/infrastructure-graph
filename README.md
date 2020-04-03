## Infrastructure Dependency visualization

This tool is looking at CloudFormation Export/Imports and visualizes them. It can additionally abstract dependencies at a higher level based on Tags attached on the involved CloudFormation tags.

In its default configuration it is looking for the tags `ServiceName/Service` and expects a stack naming scheme like the following: 

```
reco-dev-storeloader-task-rfystorage
```

This things can be changed and need to be changed if you want to apply it in other accounts


# Configuration

Rename the `config.hocon.template` to `config.hocon` and adapt if you have external dependencies depending on your services. Names need to match up

# How to execute

```
# create venv
pip install -r requirements.txt
./export-graph.py
open output/
```