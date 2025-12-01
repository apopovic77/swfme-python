"""
Simple math workflow to showcase data flow in the UI graph.

Pipeline: A + B -> Sum -> Average
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from swfme.core.process import AtomarProcess, OrchestratedProcess, ProcessExecutionFlags
from swfme.core.parameters import InputParameter, OutputParameter


class ProcessAdd(AtomarProcess):
    """Add two numbers"""

    def define_parameters(self):
        self.input.add(InputParameter("a", float))
        self.input.add(InputParameter("b", float))
        self.output.add(OutputParameter("sum", float))

    async def execute_impl(self):
        a = self.input["a"].value
        b = self.input["b"].value
        await asyncio.sleep(0.5)
        self.output["sum"].value = a + b


class ProcessAverage(AtomarProcess):
    """Average of sum and count"""

    def define_parameters(self):
        self.input.add(InputParameter("sum", float))
        self.input.add(InputParameter("count", int))
        self.output.add(OutputParameter("avg", float))

    async def execute_impl(self):
        total = self.input["sum"].value
        count = self.input["count"].value
        await asyncio.sleep(0.5)
        self.output["avg"].value = total / count if count else 0


class ProcessMultiply(AtomarProcess):
    """Multiply average by a factor"""

    def define_parameters(self):
        self.input.add(InputParameter("value", float))
        self.input.add(InputParameter("factor", float))
        self.output.add(OutputParameter("result", float))

    async def execute_impl(self):
        value = self.input["value"].value
        factor = self.input["factor"].value
        await asyncio.sleep(0.5)
        self.output["result"].value = value * factor


class MathPipeline(OrchestratedProcess):
    """Add two numbers, compute average, multiply by factor"""

    def define_parameters(self):
        self.input.add(InputParameter("a", float))
        self.input.add(InputParameter("b", float))
        self.input.add(InputParameter("factor", float))
        self.output.add(OutputParameter("result", float))

    def orchestrate(self):
        add = ProcessAdd(name="Add")
        self._connect_param(self.input["a"], add.input["a"])
        self._connect_param(self.input["b"], add.input["b"])
        self.add_child(add, ProcessExecutionFlags.SEQUENTIAL)

        avg = ProcessAverage(name="Average")
        self._connect_param(add.output["sum"], avg.input["sum"])
        # count is constant 2
        avg.input["count"].value = 2
        self.add_child(avg, ProcessExecutionFlags.SEQUENTIAL)

        mult = ProcessMultiply(name="Multiply")
        self._connect_param(avg.output["avg"], mult.input["value"])
        self._connect_param(self.input["factor"], mult.input["factor"])
        self.add_child(mult, ProcessExecutionFlags.SEQUENTIAL)

        self._connect_param(mult.output["result"], self.output["result"])


if __name__ == "__main__":
    import asyncio
    from swfme.monitoring.event_bus import event_bus

    async def logger(event):
        print(event)

    event_bus.subscribe("*", logger)

    pipeline = MathPipeline(name="MathPipeline")
    pipeline.input["a"].value = 4
    pipeline.input["b"].value = 6
    pipeline.input["factor"].value = 10

    asyncio.run(pipeline.execute())

