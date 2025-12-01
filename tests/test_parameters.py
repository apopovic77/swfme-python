"""
Unit tests for Parameter System
"""

import pytest
from swfme.core.parameters import (
    Parameter,
    InputParameter,
    OutputParameter,
    ParameterSet,
    ParameterPhase
)


class TestParameter:
    """Test Parameter base class"""

    def test_parameter_creation(self):
        """Test creating a parameter"""
        param = Parameter("test_param", int, required=True, description="Test parameter")

        assert param.name == "test_param"
        assert param.param_type == int
        assert param.required is True
        assert param.description == "Test parameter"
        assert param.value is None
        assert param.phase == ParameterPhase.INIT

    def test_parameter_value_assignment(self):
        """Test assigning values to parameters"""
        param = Parameter("count", int)

        param.value = 42
        assert param.value == 42

    def test_parameter_type_validation(self):
        """Test type validation"""
        param = Parameter("count", int)

        # Valid assignment
        param.value = 100
        assert param.value == 100

        # Invalid assignment should raise TypeError
        with pytest.raises(TypeError):
            param.value = "not an int"

    def test_parameter_optional(self):
        """Test optional parameters"""
        param = Parameter("optional", str, required=False)

        # None should be allowed for optional
        param.value = None
        assert param.value is None

        # But type checking still applies for non-None values
        with pytest.raises(TypeError):
            param.value = 123

    def test_parameter_lock(self):
        """Test parameter locking"""
        param = Parameter("locked", int)
        param.value = 10

        # Lock parameter
        param.lock()
        assert param.phase == ParameterPhase.RUNTIME

        # Should raise error when trying to modify
        with pytest.raises(RuntimeError):
            param.value = 20

        # Unlock
        param.unlock()
        param.value = 30
        assert param.value == 30

    def test_parameter_validation(self):
        """Test parameter validation"""
        required_param = Parameter("required", int, required=True)
        optional_param = Parameter("optional", int, required=False)

        # Required param without value should raise
        with pytest.raises(ValueError):
            required_param.validate()

        # Required param with value should pass
        required_param.value = 10
        assert required_param.validate() is True

        # Optional param without value should pass
        assert optional_param.validate() is True

    def test_parameter_to_dict(self):
        """Test parameter serialization"""
        param = Parameter("test", int, required=True, description="Test")
        param.value = 42

        data = param.to_dict()

        assert data["name"] == "test"
        assert data["type"] == "int"
        assert data["value"] == 42
        assert data["required"] is True
        assert data["description"] == "Test"


class TestInputOutputParameters:
    """Test InputParameter and OutputParameter"""

    def test_input_parameter(self):
        """Test InputParameter"""
        input_param = InputParameter("input", str, required=True)

        assert isinstance(input_param, Parameter)
        input_param.value = "test input"
        assert input_param.value == "test input"

    def test_output_parameter(self):
        """Test OutputParameter"""
        output_param = OutputParameter("output", int)

        assert isinstance(output_param, Parameter)
        output_param.value = 100
        assert output_param.value == 100


class TestParameterSet:
    """Test ParameterSet"""

    def test_parameter_set_creation(self):
        """Test creating a parameter set"""
        params = ParameterSet()

        assert len(params._parameters) == 0

    def test_add_parameter(self):
        """Test adding parameters"""
        params = ParameterSet()

        param1 = Parameter("param1", int)
        param2 = Parameter("param2", str)

        params.add(param1)
        params.add(param2)

        assert "param1" in params
        assert "param2" in params
        assert len(params._parameters) == 2

    def test_get_parameter(self):
        """Test getting parameters"""
        params = ParameterSet()
        param = Parameter("test", int)
        params.add(param)

        retrieved = params.get("test")
        assert retrieved is param

        # Non-existent parameter
        assert params.get("nonexistent") is None

    def test_dict_access(self):
        """Test dictionary-style access"""
        params = ParameterSet()
        param = Parameter("test", int)
        params.add(param)

        # Get
        assert params["test"] is param

        # KeyError for non-existent
        with pytest.raises(KeyError):
            _ = params["nonexistent"]

    def test_validate_all(self):
        """Test validating all parameters"""
        params = ParameterSet()

        param1 = Parameter("required1", int, required=True)
        param2 = Parameter("required2", str, required=True)
        param3 = Parameter("optional", bool, required=False)

        params.add(param1)
        params.add(param2)
        params.add(param3)

        # Should fail - required params not set
        with pytest.raises(ValueError):
            params.validate_all()

        # Set required params
        param1.value = 10
        param2.value = "test"

        # Should pass
        assert params.validate_all() is True

    def test_lock_unlock_all(self):
        """Test locking/unlocking all parameters"""
        params = ParameterSet()

        param1 = Parameter("param1", int)
        param2 = Parameter("param2", str)

        param1.value = 10
        param2.value = "test"

        params.add(param1)
        params.add(param2)

        # Lock all
        params.lock_all()

        with pytest.raises(RuntimeError):
            param1.value = 20

        with pytest.raises(RuntimeError):
            param2.value = "changed"

        # Unlock all
        params.unlock_all()

        param1.value = 30
        param2.value = "changed"

        assert param1.value == 30
        assert param2.value == "changed"

    def test_to_dict(self):
        """Test serializing parameter set"""
        params = ParameterSet()

        param1 = Parameter("param1", int)
        param1.value = 10

        param2 = Parameter("param2", str)
        param2.value = "test"

        params.add(param1)
        params.add(param2)

        data = params.to_dict()

        assert "param1" in data
        assert "param2" in data
        assert data["param1"]["value"] == 10
        assert data["param2"]["value"] == "test"
