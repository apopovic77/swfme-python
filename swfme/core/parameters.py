"""
Parameter System for sWFME

Type-safe input/output parameters for processes.
Inspired by the original sWFME C# implementation (2010).
"""

from typing import Any, Optional, Type, get_origin, get_args
from enum import Enum


class ParameterPhase(Enum):
    """Parameter lifecycle phase"""
    INIT = "init"  # During process initialization
    RUNTIME = "runtime"  # During process execution


class Parameter:
    """
    Base class for process parameters with type safety.

    Features:
    - Type validation at assignment
    - Optional/Required distinction
    - Lifecycle phase tracking
    - Metadata support

    Example:
        >>> param = Parameter("user_id", int, required=True)
        >>> param.value = 123
        >>> param.value = "abc"  # Raises TypeError
    """

    def __init__(
        self,
        name: str,
        param_type: Type,
        required: bool = True,
        default: Any = None,
        description: str = ""
    ):
        self.name = name
        self.param_type = param_type
        self.required = required
        self.description = description
        self._value: Optional[Any] = default
        self._locked = False
        self.phase = ParameterPhase.INIT

    @property
    def value(self) -> Any:
        """Get parameter value"""
        return self._value

    @value.setter
    def value(self, val: Any):
        """
        Set parameter value with type validation.

        Raises:
            TypeError: If value doesn't match declared type
            RuntimeError: If parameter is locked
        """
        if self._locked:
            raise RuntimeError(f"Parameter '{self.name}' is locked and cannot be modified")

        # Allow None for optional parameters
        if val is None and not self.required:
            self._value = None
            return

        # Type validation
        if not self._validate_type(val):
            raise TypeError(
                f"Parameter '{self.name}' expects type {self.param_type}, "
                f"got {type(val).__name__}"
            )

        self._value = val

    def _validate_type(self, val: Any) -> bool:
        """
        Validate value against declared type.
        Supports basic types, generics, and union types.
        """
        # Handle None
        if val is None:
            return not self.required

        # Simple type check
        if isinstance(self.param_type, type):
            return isinstance(val, self.param_type)

        # Handle generic types (List[int], Dict[str, Any], etc.)
        origin = get_origin(self.param_type)
        if origin is not None:
            # For now, just check the origin type (List, Dict, etc.)
            # Full generic validation would be more complex
            return isinstance(val, origin)

        # Fallback: accept anything for complex types
        return True

    def lock(self):
        """Lock parameter to prevent further modifications"""
        self._locked = True
        self.phase = ParameterPhase.RUNTIME

    def unlock(self):
        """Unlock parameter to allow modifications"""
        self._locked = False

    def is_set(self) -> bool:
        """Check if parameter has a value"""
        return self._value is not None

    def validate(self) -> bool:
        """
        Validate parameter state.

        Returns:
            True if parameter is valid

        Raises:
            ValueError: If required parameter is not set
        """
        if self.required and self._value is None:
            raise ValueError(f"Required parameter '{self.name}' is not set")
        return True

    def to_dict(self) -> dict:
        """Convert parameter to dictionary representation"""
        return {
            "name": self.name,
            "type": self.param_type.__name__ if isinstance(self.param_type, type) else str(self.param_type),
            "value": self._value,
            "required": self.required,
            "description": self.description,
            "phase": self.phase.value,
            "locked": self._locked
        }

    def __repr__(self) -> str:
        return f"Parameter(name='{self.name}', type={self.param_type.__name__}, value={self._value})"


class InputParameter(Parameter):
    """
    Input parameter for a process.

    Input parameters are set before process execution and are
    typically locked during execution to prevent modification.

    Example:
        >>> input_param = InputParameter("filename", str, required=True)
        >>> input_param.value = "data.csv"
    """

    def __init__(
        self,
        name: str,
        param_type: Type,
        required: bool = True,
        default: Any = None,
        description: str = ""
    ):
        super().__init__(name, param_type, required, default, description)


class OutputParameter(Parameter):
    """
    Output parameter for a process.

    Output parameters are set during process execution and represent
    the results of the process.

    Example:
        >>> output_param = OutputParameter("result", int)
        >>> output_param.value = 42
    """

    def __init__(
        self,
        name: str,
        param_type: Type,
        required: bool = True,
        default: Any = None,
        description: str = ""
    ):
        super().__init__(name, param_type, required, default, description)


class ParameterSet:
    """
    Container for multiple parameters with dictionary-like access.

    Example:
        >>> params = ParameterSet()
        >>> params.add(InputParameter("user_id", int))
        >>> params["user_id"].value = 123
        >>> params.get("user_id")  # Returns Parameter object
    """

    def __init__(self):
        self._parameters: dict[str, Parameter] = {}

    def add(self, parameter: Parameter):
        """Add a parameter to the set"""
        self._parameters[parameter.name] = parameter

    def get(self, name: str) -> Optional[Parameter]:
        """Get parameter by name"""
        return self._parameters.get(name)

    def __getitem__(self, name: str) -> Parameter:
        """Dictionary-style access"""
        if name not in self._parameters:
            raise KeyError(f"Parameter '{name}' not found")
        return self._parameters[name]

    def __setitem__(self, name: str, parameter: Parameter):
        """Dictionary-style assignment"""
        self._parameters[name] = parameter

    def __contains__(self, name: str) -> bool:
        """Check if parameter exists"""
        return name in self._parameters

    def keys(self):
        """Get all parameter names"""
        return self._parameters.keys()

    def values(self):
        """Get all parameters"""
        return self._parameters.values()

    def items(self):
        """Get all parameter name-value pairs"""
        return self._parameters.items()

    def validate_all(self) -> bool:
        """
        Validate all parameters.

        Returns:
            True if all parameters are valid

        Raises:
            ValueError: If any required parameter is not set
        """
        for param in self._parameters.values():
            param.validate()
        return True

    def lock_all(self):
        """Lock all parameters"""
        for param in self._parameters.values():
            param.lock()

    def unlock_all(self):
        """Unlock all parameters"""
        for param in self._parameters.values():
            param.unlock()

    def to_dict(self) -> dict:
        """Convert all parameters to dictionary"""
        return {name: param.to_dict() for name, param in self._parameters.items()}

    def __repr__(self) -> str:
        return f"ParameterSet({len(self._parameters)} parameters)"
