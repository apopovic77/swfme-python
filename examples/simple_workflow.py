"""
Simple Workflow Example for sWFME

This demonstrates the core features of sWFME:
- Atomic processes
- Orchestrated workflows
- Sequential/Parallel execution
- Parameter passing
- Event monitoring
- Metrics collection

Example Pipeline:
    LoadData → ProcessData → [ValidateResult, AnalyzeResult] → SaveResult
                  ↓                       ↓            ↓             ↓
              (Sequential)            (Parallel)             (Sequential)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from swfme.core.process import AtomarProcess, OrchestratedProcess, ProcessExecutionFlags
from swfme.core.parameters import InputParameter, OutputParameter
from swfme.monitoring.event_bus import event_bus
from swfme.monitoring.metrics import metrics_collector


# ═══════════════════════════════════════════════════════════════════════════
# ATOMIC PROCESSES
# ═══════════════════════════════════════════════════════════════════════════

class ProcessLoadData(AtomarProcess):
    """Load data from a source"""

    def define_parameters(self):
        self.input.add(InputParameter("filename", str, description="File to load"))
        self.output.add(OutputParameter("data", list, description="Loaded data"))
        self.output.add(OutputParameter("row_count", int, description="Number of rows"))

    async def execute_impl(self):
        filename = self.input["filename"].value

        # Simulate loading data
        print(f"📂 Loading data from: {filename}")
        await asyncio.sleep(1.2)  # Simulate I/O

        # Generate fake data
        data = [
            {"id": 1, "value": 100, "status": "active"},
            {"id": 2, "value": 200, "status": "active"},
            {"id": 3, "value": 150, "status": "inactive"},
            {"id": 4, "value": 300, "status": "active"},
        ]

        self.output["data"].value = data
        self.output["row_count"].value = len(data)

        print(f"   ✓ Loaded {len(data)} rows")


class ProcessTransformData(AtomarProcess):
    """Transform/clean data"""

    def define_parameters(self):
        self.input.add(InputParameter("data", list))
        self.output.add(OutputParameter("transformed_data", list))

    async def execute_impl(self):
        data = self.input["data"].value

        print(f"🔄 Transforming {len(data)} rows...")
        await asyncio.sleep(1.0)  # Simulate processing

        # Filter active items and double values
        transformed = [
            {**item, "value": item["value"] * 2}
            for item in data
            if item["status"] == "active"
        ]

        self.output["transformed_data"].value = transformed

        print(f"   ✓ Transformed to {len(transformed)} rows")


class ProcessValidateData(AtomarProcess):
    """Validate data quality"""

    def define_parameters(self):
        self.input.add(InputParameter("data", list))
        self.output.add(OutputParameter("is_valid", bool))
        self.output.add(OutputParameter("validation_errors", list))

    async def execute_impl(self):
        data = self.input["data"].value

        print(f"✅ Validating {len(data)} rows...")
        await asyncio.sleep(1.0)  # Simulate validation

        errors = []

        # Validation rules
        for item in data:
            if item["value"] <= 0:
                errors.append(f"Row {item['id']}: Value must be positive")

            if item["value"] > 1000:
                errors.append(f"Row {item['id']}: Value too large (>{1000})")

        is_valid = len(errors) == 0

        self.output["is_valid"].value = is_valid
        self.output["validation_errors"].value = errors

        if is_valid:
            print(f"   ✓ Validation passed")
        else:
            print(f"   ⚠️  Validation failed: {len(errors)} errors")


class ProcessAnalyzeData(AtomarProcess):
    """Analyze data and compute statistics"""

    def define_parameters(self):
        self.input.add(InputParameter("data", list))
        self.output.add(OutputParameter("stats", dict))

    async def execute_impl(self):
        data = self.input["data"].value

        print(f"📊 Analyzing {len(data)} rows...")
        await asyncio.sleep(1.4)  # Simulate analysis

        values = [item["value"] for item in data]

        stats = {
            "count": len(data),
            "sum": sum(values),
            "avg": sum(values) / len(values) if values else 0,
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
        }

        self.output["stats"].value = stats

        print(f"   ✓ Analysis complete: avg={stats['avg']:.1f}, sum={stats['sum']}")


class ProcessSaveResult(AtomarProcess):
    """Save processed data"""

    def define_parameters(self):
        self.input.add(InputParameter("data", list))
        self.input.add(InputParameter("stats", dict))
        self.input.add(InputParameter("is_valid", bool))
        self.output.add(OutputParameter("saved_path", str))
        self.output.add(OutputParameter("success", bool))

    async def execute_impl(self):
        data = self.input["data"].value
        stats = self.input["stats"].value
        is_valid = self.input["is_valid"].value

        if not is_valid:
            raise Exception("Cannot save: Data validation failed")

        print(f"💾 Saving {len(data)} rows with stats...")
        await asyncio.sleep(1.0)  # Simulate saving

        # Simulate file write
        path = "/tmp/result.json"

        self.output["saved_path"].value = path
        self.output["success"].value = True

        print(f"   ✓ Saved to: {path}")


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATED WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════

class DataProcessingPipeline(OrchestratedProcess):
    """
    Complete data processing pipeline.

    Flow:
        LoadData → TransformData → [ValidateData, AnalyzeData] → SaveResult
                      ↓                      ↓           ↓             ↓
                  Sequential              Parallel              Sequential
    """

    def define_parameters(self):
        # Input
        self.input.add(InputParameter("filename", str, description="Input file"))

        # Output
        self.output.add(OutputParameter("result_path", str, description="Output file"))
        self.output.add(OutputParameter("statistics", dict, description="Data statistics"))
        self.output.add(OutputParameter("row_count", int, description="Processed rows"))

    def orchestrate(self):
        """Define the workflow"""

        # STEP 1: Load Data (Sequential)
        load = ProcessLoadData(name="LoadData")
        # Connect input parameter
        self._connect_param(self.input["filename"], load.input["filename"])
        self.add_child(load, ProcessExecutionFlags.SEQUENTIAL)

        # STEP 2: Transform Data (Sequential)
        transform = ProcessTransformData(name="TransformData")
        # Connect to previous step's output (will be resolved at runtime)
        self._connect_param(load.output["data"], transform.input["data"])
        self.add_child(transform, ProcessExecutionFlags.SEQUENTIAL)

        # STEP 3: Validate & Analyze (Parallel)
        validate = ProcessValidateData(name="ValidateData")
        self._connect_param(transform.output["transformed_data"], validate.input["data"])
        self.add_child(validate, ProcessExecutionFlags.PARALLEL)

        analyze = ProcessAnalyzeData(name="AnalyzeData")
        self._connect_param(transform.output["transformed_data"], analyze.input["data"])
        self.add_child(analyze, ProcessExecutionFlags.PARALLEL)

        # STEP 4: Save Result (Sequential, waits for parallel to complete)
        save = ProcessSaveResult(name="SaveResult")
        self._connect_param(transform.output["transformed_data"], save.input["data"])
        self._connect_param(analyze.output["stats"], save.input["stats"])
        self._connect_param(validate.output["is_valid"], save.input["is_valid"])
        self.add_child(save, ProcessExecutionFlags.SEQUENTIAL)

        # Parameter Derivation: Map child outputs to workflow outputs
        # These will be resolved after execution
        self._connect_param(save.output["saved_path"], self.output["result_path"])
        self._connect_param(analyze.output["stats"], self.output["statistics"])
        self._connect_param(load.output["row_count"], self.output["row_count"])

    def _connect_param(self, source, target):
        """Helper to connect parameters (value will be copied at execution time)"""
        # Store connection for later resolution
        if not hasattr(self, '_param_connections'):
            self._param_connections = []
        self._param_connections.append((source, target))


# ═══════════════════════════════════════════════════════════════════════════
# DEMO RUNNER
# ═══════════════════════════════════════════════════════════════════════════

async def event_logger(event):
    """Simple event logger for demo"""
    event_type = event.get("type", "unknown")
    process_name = event.get("process_name", "Unknown")
    status = event.get("status", "")

    icons = {
        "process.started": "▶️",
        "process.completed": "✅",
        "process.failed": "❌",
        "process.group_started": "📦",
        "process.group_completed": "✔️"
    }

    icon = icons.get(event_type, "•")

    if event_type == "process.started":
        print(f"\n{icon} Started: {process_name}")
    elif event_type == "process.completed":
        exec_time = event.get("execution_time_ms", 0)
        print(f"{icon} Completed: {process_name} ({exec_time:.0f}ms)")
    elif event_type == "process.failed":
        error = event.get("error", "Unknown error")
        print(f"{icon} Failed: {process_name} - {error}")
    elif event_type == "process.group_started":
        mode = event.get("execution_mode", "unknown")
        size = event.get("group_size", 0)
        print(f"\n{icon} Execution Group ({mode}): {size} process(es)")
    elif event_type == "process.group_completed":
        print(f"{icon} Group Completed")


async def main():
    """Run the demo"""
    print("=" * 70)
    print("sWFME Demo: Data Processing Pipeline")
    print("=" * 70)

    # Subscribe to events
    event_bus.subscribe("*", event_logger)

    # Create and configure workflow
    pipeline = DataProcessingPipeline(name="DataPipeline")
    pipeline.input["filename"].value = "data.csv"

    print(f"\n📋 Workflow: {pipeline.name}")
    print(f"   Input: {pipeline.input['filename'].value}")

    # Execute
    print("\n" + "=" * 70)
    print("EXECUTION")
    print("=" * 70)

    success = await pipeline.execute()

    # Results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    if success:
        print(f"✅ Workflow completed successfully!")
        print(f"\nOutputs:")
        print(f"  • Result Path: {pipeline.output['result_path'].value}")
        print(f"  • Row Count: {pipeline.output['row_count'].value}")
        print(f"  • Statistics: {pipeline.output['statistics'].value}")
        print(f"\nExecution Time: {pipeline.execution_time_ms:.0f}ms")
    else:
        print(f"❌ Workflow failed!")
        print(f"   Error: {pipeline.error}")

    # Metrics
    print("\n" + "=" * 70)
    print("METRICS")
    print("=" * 70)

    # Per-execution metrics
    metrics = metrics_collector.get_metrics(pipeline.id)
    if metrics:
        print(f"\nWorkflow Metrics:")
        print(f"  • Process ID: {metrics.process_id[:16]}...")
        print(f"  • Status: {metrics.status}")
        print(f"  • Execution Time: {metrics.execution_time_ms:.0f}ms")

    # Aggregated metrics
    summary = metrics_collector.get_summary()
    print(f"\nOverall Summary:")
    print(f"  • Total Processes: {summary['total_processes']}")
    print(f"  • Completed: {summary['completed']}")
    print(f"  • Failed: {summary['failed']}")
    print(f"  • Success Rate: {summary['success_rate']:.1%}")
    print(f"  • Avg Execution Time: {summary['avg_execution_time_ms']:.0f}ms")

    # Per-class metrics
    print(f"\nPer-Process Metrics:")
    for agg in metrics_collector.get_all_aggregated():
        print(f"  • {agg.process_class}:")
        print(f"      - Executions: {agg.total_executions}")
        print(f"      - Success Rate: {agg.success_rate:.1%}")
        print(f"      - Avg Time: {agg.avg_execution_time_ms:.0f}ms")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
