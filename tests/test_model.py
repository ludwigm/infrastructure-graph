# Third party
import pytest
from pyexpect import expect

# First party
from aws_infra_graph.model import StackParameter, ExternalDependency

test_external_dep = ExternalDependency(
    team_name="team_name", service_name="service_name"
)


class TestModel:
    @pytest.mark.parametrize("team_name", ["team"])
    @pytest.mark.parametrize("service_name", ["service"])
    def test_model_external_dependency(self, team_name, service_name):
        """Models :: ExternalDependency :: model can be created"""
        model = ExternalDependency(team_name=team_name, service_name=service_name)
        expect(model).to_exist()

    @pytest.mark.parametrize("name", ["name"])
    @pytest.mark.parametrize("value", ["value"])
    @pytest.mark.parametrize("description", ["description"])
    @pytest.mark.parametrize("external_dependency", [test_external_dep])
    def test_model_stack_parameter(self, name, value, description, external_dependency):
        """Models :: StackParameter :: the model can be created"""
        model = StackParameter(
            name=name,
            value=value,
            description=description,
            external_dependency=external_dependency,
        )
        expect(model).to_exist()
