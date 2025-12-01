"""
sWFME Core Module

Core process classes and utilities.
"""

from swfme.core.process import (
    Process,
    AtomarProcess,
    OrchestratedProcess,
    ProcessStatus,
    ProcessExecutionFlags,
    ProcessExecutionContext,
    SEQUENTIAL,
    PARALLEL,
)

from swfme.core.parameters import (
    Parameter,
    InputParameter,
    OutputParameter,
    ParameterSet,
)

from swfme.core.logging import (
    ProcessLogLevel,
    ProcessLogConfig,
    ProcessLogger,
    process_log_config,
)

__all__ = [
    # Process classes
    "Process",
    "AtomarProcess",
    "OrchestratedProcess",
    "ProcessStatus",
    "ProcessExecutionFlags",
    "ProcessExecutionContext",
    "SEQUENTIAL",
    "PARALLEL",
    # Parameters
    "Parameter",
    "InputParameter",
    "OutputParameter",
    "ParameterSet",
    # Logging
    "ProcessLogLevel",
    "ProcessLogConfig",
    "ProcessLogger",
    "process_log_config",
]
