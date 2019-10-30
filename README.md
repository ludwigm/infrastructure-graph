## Infrastructure Dependency visualization

This tool is looking at CloudFormation Export/Imports and visualizes them. It can additionally abstract dependencies at a higher level based on Tags attached on the involved CloudFormation tags.

In its default configuration it is looking for the tags `ServiceName/Service` and expects a stack naming scheme like the following: 

```
reco-dev-storeloader-task-rfystorage
```

This things can be changed and need to be changed if you want to apply it in other accounts

# How to execute

```
# create venv
pip install -r requirements.txt
./export-graph.py
open output/
```