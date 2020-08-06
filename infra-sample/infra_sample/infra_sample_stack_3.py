# Third party
from utils import generate_resource_name
from aws_cdk import core, aws_ssm
from aws_cdk.core import Fn, Tag, CfnParameter


class InfraSampleStack3(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        env = "dev"
        project = "testproject1"
        service = "etl"

        component = "workflow"
        Tag.add(self, "Service", service)
        Tag.add(self, "Component", component)

        param_dwh = CfnParameter(
            self,
            "ParamDWH",
            type="String",
            description="The domain of the DWH to connect to. | team=data,service=dwh",
            default="fakedwh.host",
        )

        value_raw = "import: ${value_to_import}, param: ${param_dwh}"
        value = Fn.sub(
            value_raw,
            {
                "value_to_import": Fn.import_value(
                    generate_resource_name(project, env, service, "buckets", "bucketb")
                ),
                "param_dwh": Fn.ref(param_dwh.logical_id),
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
