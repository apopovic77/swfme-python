"""
Process Logging Configuration for sWFME

Provides configurable logging levels for process execution:
- QUIET: No process logging
- NORMAL: Start/complete messages
- VERBOSE: Full input/output parameter details
- DEBUG: Everything including internal state

Author: Alex Popovic (Arkturian)
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional


class ProcessLogLevel(Enum):
    """Logging verbosity levels for process execution."""
    QUIET = 0      # No process-specific logging
    NORMAL = 1     # Process start/complete with name
    VERBOSE = 2    # Include input/output parameter summaries
    DEBUG = 3      # Full details including values


class ProcessLogConfig:
    """
    Global configuration for process logging.

    Usage:
        from swfme.core.logging import process_log_config, ProcessLogLevel

        # Set globally
        process_log_config.level = ProcessLogLevel.VERBOSE

        # Or via string
        process_log_config.set_level("verbose")
    """

    def __init__(self):
        self._level = ProcessLogLevel.NORMAL
        self._indent_char = "  "
        self._max_value_length = 100
        self._show_timestamps = False

    @property
    def level(self) -> ProcessLogLevel:
        return self._level

    @level.setter
    def level(self, value: ProcessLogLevel):
        self._level = value

    def set_level(self, level: str) -> None:
        """Set log level from string (quiet, normal, verbose, debug)."""
        level_map = {
            "quiet": ProcessLogLevel.QUIET,
            "normal": ProcessLogLevel.NORMAL,
            "verbose": ProcessLogLevel.VERBOSE,
            "debug": ProcessLogLevel.DEBUG,
        }
        if level.lower() not in level_map:
            raise ValueError(f"Invalid log level: {level}. Use: {list(level_map.keys())}")
        self._level = level_map[level.lower()]

    @property
    def indent_char(self) -> str:
        return self._indent_char

    @indent_char.setter
    def indent_char(self, value: str):
        self._indent_char = value

    @property
    def max_value_length(self) -> int:
        return self._max_value_length

    @max_value_length.setter
    def max_value_length(self, value: int):
        self._max_value_length = value

    @property
    def show_timestamps(self) -> bool:
        return self._show_timestamps

    @show_timestamps.setter
    def show_timestamps(self, value: bool):
        self._show_timestamps = value


# Global config instance
process_log_config = ProcessLogConfig()


class ProcessLogger:
    """
    Logger mixin for Process classes.

    Provides structured logging methods that respect the global log level.
    """

    def __init__(self, process_name: str, process_class: str, depth: int = 0):
        self._process_name = process_name
        self._process_class = process_class
        self._depth = depth
        self._logger = logging.getLogger(f"swfme.process.{process_class}")

    @property
    def _indent(self) -> str:
        return process_log_config.indent_char * self._depth

    def _should_log(self, min_level: ProcessLogLevel) -> bool:
        return process_log_config.level.value >= min_level.value

    def _format_value(self, value: Any) -> str:
        """Format a value for logging, truncating if needed."""
        max_len = process_log_config.max_value_length

        if value is None:
            return "None"

        if isinstance(value, str):
            if len(value) > max_len:
                return f'"{value[:max_len]}..."'
            return f'"{value}"'

        if isinstance(value, (int, float, bool)):
            return str(value)

        if isinstance(value, list):
            return f"[list: {len(value)} items]"

        if isinstance(value, dict):
            return f"{{dict: {len(value)} keys}}"

        # For objects, show class name
        type_name = type(value).__name__
        str_repr = str(value)
        if len(str_repr) > max_len:
            return f"<{type_name}: {str_repr[:max_len]}...>"
        return f"<{type_name}: {str_repr}>"

    def _format_params(self, params: Dict[str, Any], param_type: str) -> list[str]:
        """Format parameters for logging."""
        lines = []
        for name, param in params.items():
            value_str = self._format_value(param.value)
            type_str = param.param_type.__name__ if isinstance(param.param_type, type) else str(param.param_type)
            lines.append(f"{self._indent}    {param_type}.{name}: {type_str} = {value_str}")
        return lines

    # === Public Logging Methods ===

    def log_start(self, input_params: Optional[Dict] = None) -> None:
        """Log process start."""
        if not self._should_log(ProcessLogLevel.NORMAL):
            return

        self._logger.info(f"{self._indent}▶ {self._process_name} starting...")

        if self._should_log(ProcessLogLevel.VERBOSE) and input_params:
            for line in self._format_params(input_params, "input"):
                self._logger.info(line)

    def log_complete(self, output_params: Optional[Dict] = None, execution_time_ms: Optional[float] = None) -> None:
        """Log process completion."""
        if not self._should_log(ProcessLogLevel.NORMAL):
            return

        time_str = f" ({execution_time_ms:.0f}ms)" if execution_time_ms else ""
        self._logger.info(f"{self._indent}✓ {self._process_name} completed{time_str}")

        if self._should_log(ProcessLogLevel.VERBOSE) and output_params:
            for line in self._format_params(output_params, "output"):
                self._logger.info(line)

    def log_failed(self, error: str, execution_time_ms: Optional[float] = None) -> None:
        """Log process failure."""
        if not self._should_log(ProcessLogLevel.NORMAL):
            return

        time_str = f" ({execution_time_ms:.0f}ms)" if execution_time_ms else ""
        self._logger.error(f"{self._indent}✗ {self._process_name} failed{time_str}: {error}")

    def log_child_start(self, child_name: str, execution_mode: str) -> None:
        """Log child process start (for orchestrated processes)."""
        if not self._should_log(ProcessLogLevel.VERBOSE):
            return

        mode_icon = "∥" if execution_mode == "parallel" else "→"
        self._logger.info(f"{self._indent}  {mode_icon} {child_name}")

    def log_group_start(self, group_index: int, group_size: int, execution_mode: str) -> None:
        """Log execution group start."""
        if not self._should_log(ProcessLogLevel.DEBUG):
            return

        self._logger.debug(f"{self._indent}  [Group {group_index + 1}: {group_size} process(es), {execution_mode}]")

    def log_debug(self, message: str) -> None:
        """Log debug message."""
        if not self._should_log(ProcessLogLevel.DEBUG):
            return

        self._logger.debug(f"{self._indent}  {message}")

    def log_info(self, message: str) -> None:
        """Log info message (always shown unless QUIET)."""
        if not self._should_log(ProcessLogLevel.NORMAL):
            return

        self._logger.info(f"{self._indent}  {message}")
