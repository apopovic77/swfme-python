"""
Process Registry for sWFME

Manages registration and discovery of available process types.
Allows dynamic workflow creation from class names.
"""

from typing import Dict, Type, List, Optional, Any
from swfme.core.process import Process, AtomarProcess, OrchestratedProcess


class ProcessRegistry:
    """
    Registry for process types.

    Allows registration and discovery of process classes,
    enabling dynamic workflow creation.

    Example:
        >>> registry = ProcessRegistry()
        >>> registry.register(MyProcess)
        >>> process = registry.create("MyProcess")
    """

    def __init__(self):
        self._processes: Dict[str, Type[Process]] = {}

    def register(self, process_class: Type[Process], name: Optional[str] = None):
        """
        Register a process class.

        Args:
            process_class: Process class to register
            name: Optional custom name (defaults to class name)

        Example:
            >>> registry.register(DataPipeline)
            >>> registry.register(DataPipeline, "custom-pipeline")
        """
        reg_name = name or process_class.__name__
        self._processes[reg_name] = process_class

    def unregister(self, name: str):
        """Unregister a process class"""
        if name in self._processes:
            del self._processes[name]

    def get(self, name: str) -> Optional[Type[Process]]:
        """Get process class by name"""
        return self._processes.get(name)

    def create(self, name: str, instance_name: Optional[str] = None) -> Optional[Process]:
        """
        Create process instance by name.

        Args:
            name: Registered process name
            instance_name: Optional instance name

        Returns:
            Process instance or None if not found

        Example:
            >>> process = registry.create("DataPipeline", instance_name="MyPipeline")
        """
        process_class = self.get(name)
        if process_class:
            return process_class(name=instance_name)
        return None

    def list_processes(self) -> List[Dict[str, Any]]:
        """
        List all registered processes with metadata.

        Returns:
            List of process info dicts

        Example:
            >>> processes = registry.list_processes()
            >>> print(processes)
            [
                {
                    "name": "DataPipeline",
                    "class": "DataPipeline",
                    "type": "orchestrated",
                    "module": "examples.simple_workflow"
                }
            ]
        """
        result = []

        for name, process_class in self._processes.items():
            # Determine process type
            if issubclass(process_class, OrchestratedProcess):
                process_type = "orchestrated"
            elif issubclass(process_class, AtomarProcess):
                process_type = "atomic"
            else:
                process_type = "base"

            # Create instance to get parameter info
            try:
                instance = process_class()
                input_params = {
                    k: {
                        "type": p.param_type.__name__ if hasattr(p.param_type, '__name__') else str(p.param_type),
                        "required": p.required,
                        "description": p.description
                    }
                    for k, p in instance.input.items()
                }
                output_params = {
                    k: {
                        "type": p.param_type.__name__ if hasattr(p.param_type, '__name__') else str(p.param_type),
                        "description": p.description
                    }
                    for k, p in instance.output.items()
                }
            except Exception:
                input_params = {}
                output_params = {}

            result.append({
                "name": name,
                "class": process_class.__name__,
                "type": process_type,
                "module": process_class.__module__,
                "doc": process_class.__doc__,
                "input_parameters": input_params,
                "output_parameters": output_params
            })

        return result

    def get_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a process"""
        processes = self.list_processes()
        for p in processes:
            if p["name"] == name:
                return p
        return None

    def clear(self):
        """Clear all registered processes"""
        self._processes.clear()

    def __contains__(self, name: str) -> bool:
        """Check if process is registered"""
        return name in self._processes

    def __len__(self) -> int:
        """Get number of registered processes"""
        return len(self._processes)

    def __repr__(self) -> str:
        return f"<ProcessRegistry processes={len(self._processes)}>"


# Global singleton instance
process_registry = ProcessRegistry()
