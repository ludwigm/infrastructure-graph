# Third party
from utils import generate_resource_name
from aws_cdk import core, aws_s3, aws_ssm
from aws_cdk.core import Fn, Tag, RemovalPolicy


class InfraSampleStack1(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        env = "dev"
        project = "testproject1"
        service = "api"

        component = "buckets"
        Tag.add(self, "Service", service)
        Tag.add(self, "Component", component)

        bucket_a = aws_s3.Bucket(
            self,
            "BucketA",
            bucket_name=generate_resource_name(
                project, env, service, component, "bucketa"
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        bucket_b = aws_s3.Bucket(
            self,
            "BucketB",
            bucket_name=generate_resource_name(
                project, env, service, component, "bucketb"
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        value = Fn.sub(
            "test: ${value_to_import}",
            {
                "value_to_import": Fn.import_value(
                    generate_resource_name(project, env, "etl", component, "bucketb")
                )
            },
        )
        aws_ssm.StringParameter(
            self,
            "SSMParam",
            parameter_name=generate_resource_name(
                project, env, service, component, "ssmparam"
            ),
            string_value=value,
        )

        core.CfnOutput(
            self,
            id="OutputBucketA",
            value=bucket_a.bucket_name,
            export_name=generate_resource_name(
                project, env, service, component, "bucketa"
            ),
        )

        core.CfnOutput(
            self,
            id="OutputBucketB",
            value=bucket_b.bucket_name,
            export_name=generate_resource_name(
                project, env, service, component, "bucketb"
            ),
        )
