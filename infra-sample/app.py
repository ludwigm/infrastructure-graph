#!/usr/bin/env python3

# Third party
from utils import generate_resource_name
from aws_cdk import core
from infra_sample.infra_sample_stack_1 import InfraSampleStack1
from infra_sample.infra_sample_stack_2 import InfraSampleStack2
from infra_sample.infra_sample_stack_3 import InfraSampleStack3

env = "dev"
project = "testproject1"
service_1 = "api"
service_2 = "etl"

# TODO require random substring for s3 buckets as globally unique
app = core.App()
InfraSampleStack1(app, generate_resource_name(project, env, service_1, "buckets"))
InfraSampleStack2(app, generate_resource_name(project, env, service_2, "buckets"))
InfraSampleStack3(app, generate_resource_name(project, env, service_2, "workflow"))

app.synth()
