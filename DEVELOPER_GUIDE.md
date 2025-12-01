# sWFME Developer Guide

**Comprehensive guide to Process-Oriented Programming with sWFME**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Concepts](#core-concepts)
3. [Architecture](#architecture)
4. [Creating Processes](#creating-processes)
5. [Parameter System](#parameter-system)
6. [Orchestration](#orchestration)
7. [Event System](#event-system)
8. [Metrics & Monitoring](#metrics--monitoring)
9. [Testing](#testing)
10. [Advanced Patterns](#advanced-patterns)
11. [Best Practices](#best-practices)
12. [API Reference](#api-reference)

---

## Introduction

### What is Process-Oriented Programming?

**Process-Oriented Programming (POP)** treats workflows as first-class citizens, making business logic explicit and observable.

**Comparison:**

```python
# ========================================
# Traditional OOP (Hidden Logic)
# ========================================
class DataProcessor:
    def process(self, data):
        # What happens here? 🤷
        # How long does it take?
        # Can we run parts in parallel?
        # How do we monitor it?
        result = self._load(data)
        result = self._transform(result)
        result = self._validate(result)
        return result

processor = DataProcessor()
result = processor.process(data)  # Black box!


# ========================================
# Process-Oriented Programming (Explicit)
# ========================================
class DataPipeline(OrchestratedProcess):
    def define_orchestration(self):
        load = ProcessLoad()
        transform = ProcessTransform()
        validate = ProcessValidate()

        # Sequential flow - VISIBLE!
        self.add_child(load)
        self.add_child(transform)
        self.add_child(validate)

        # Parameter connections - TRACEABLE!
        self._connect_param(load.output["data"], transform.input["data"])
        self._connect_param(transform.output["data"], validate.input["data"])

pipeline = DataPipeline()
pipeline.input["data"].value = data
await pipeline.execute()  # ← Monitored, measured, visualized!
result = pipeline.output["result"].value
```

**POP Benefits:**
- 🎯 **Transparency**: See exactly what runs and when
- 📊 **Observability**: Real-time monitoring + metrics
- ⚡ **Performance**: Parallel execution where possible
- 🔧 **Maintainability**: Isolated, testable components
- 🔄 **Reusability**: Processes used across workflows

---

## Core Concepts

### 1. Processes

**Two types of processes:**

#### Atomic Process
A single, indivisible unit of work.

```python
class ProcessCalculateSum(AtomarProcess):
    """Calculate sum of numbers"""

    def __init__(self):
        super().__init__("CalculateSum")
        self.input.add(InputParameter("numbers", list, required=True))
        self.output.add(OutputParameter("sum", int))

    async def execute_impl(self):
        numbers = self.input["numbers"].value
        total = sum(numbers)
        self.output["sum"].value = total
```

**Characteristics:**
- Single responsibility
- Type-safe inputs/outputs
- Independently testable
- Reusable across workflows

#### Orchestrated Process
Combines multiple processes into a workflow.

```python
class MathPipeline(OrchestratedProcess):
    """Calculate sum and average"""

    def define_orchestration(self):
        calc_sum = ProcessCalculateSum()
        calc_avg = ProcessCalculateAverage()

        # Sequential execution
        self.add_child(calc_sum, ProcessExecutionFlags(parallel=False))
        self.add_child(calc_avg, ProcessExecutionFlags(parallel=False))

        # Data flow
        self._connect_param(calc_sum.output["sum"], calc_avg.input["sum"])
```

**Characteristics:**
- Composes atomic processes
- Defines execution order (sequential/parallel)
- Manages data flow between processes
- Can itself be used in other workflows (composability)

### 2. Parameters

**Type-safe input/output parameters:**

```python
# Input: Required parameter
self.input.add(InputParameter(
    name="filename",
    param_type=str,
    required=True,
    description="File to process"
))

# Input: Optional with default
self.input.add(InputParameter(
    name="timeout",
    param_type=int,
    required=False,
    default=30
))

# Output
self.output.add(OutputParameter(
    name="result",
    param_type=dict,
    description="Processing result"
))
```

**Runtime validation:**
```python
# Type checking at runtime
process.input["filename"].value = 123  # ❌ TypeError!
process.input["filename"].value = "test.txt"  # ✅ OK
```

### 3. Execution Modes

**Sequential:** Processes run one after another
```python
self.add_child(process1, ProcessExecutionFlags(parallel=False))
self.add_child(process2, ProcessExecutionFlags(parallel=False))
# Execution: process1 → process2
```

**Parallel:** Processes run simultaneously
```python
self.add_child(process3, ProcessExecutionFlags(parallel=True))
self.add_child(process4, ProcessExecutionFlags(parallel=True))
# Execution: process3 + process4 (at the same time)
```

**Mixed (Groups):**
```python
# Group 1 (Sequential)
self.add_child(processA, ProcessExecutionFlags(parallel=False))

# Group 2 (Parallel)
self.add_child(processB, ProcessExecutionFlags(parallel=True))
self.add_child(processC, ProcessExecutionFlags(parallel=True))

# Group 3 (Sequential)
self.add_child(processD, ProcessExecutionFlags(parallel=False))

# Execution:
# processA → [processB + processC] → processD
```

### 4. Event System

All process lifecycle events are published:

```python
# Events emitted automatically:
{
    "type": "process.started",
    "process_id": "uuid",
    "process_name": "LoadData",
    "process_class": "ProcessLoadData",
    "timestamp": "2025-11-28T18:00:00",
    "status": "running"
}

{
    "type": "process.completed",
    "process_id": "uuid",
    "execution_time_ms": 523.4,
    "status": "completed"
}
```

**Subscribe to events:**
```python
from swfme.monitoring.event_bus import event_bus

def on_process_completed(event):
    print(f"{event['process_name']} took {event['execution_time_ms']}ms")

event_bus.subscribe("process.completed", on_process_completed)
```

### 5. Metrics

Automatic metrics collection:

```python
from swfme.monitoring.metrics import metrics_collector

# Get aggregated metrics for a process class
metrics = metrics_collector.get_aggregated_metrics("ProcessLoadData")

print(f"Total executions: {metrics.total_executions}")
print(f"Success rate: {metrics.success_rate * 100}%")
print(f"Avg time: {metrics.avg_execution_time_ms}ms")
print(f"Min/Max: {metrics.min_execution_time_ms}/{metrics.max_execution_time_ms}ms")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Application                        │
│  - Dashboard (React + D3.js)                                │
│  - CLI Tools                                                │
│  - Custom Integrations                                      │
└─────────────────────────────────────────────────────────────┘
                            ↕ REST API + WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Layer                           │
│  /api/workflows          - List workflows                   │
│  /api/workflows/execute  - Execute workflow                 │
│  /api/metrics/*          - Metrics endpoints                │
│  /api/ws/monitor/*       - WebSocket monitoring             │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   Process Registry                           │
│  - Workflow Discovery                                       │
│  - Dynamic Instantiation                                    │
│  - Metadata Extraction                                      │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                  Orchestration Engine                        │
│  - Execution Scheduling (Sequential/Parallel)               │
│  - Parameter Resolution                                     │
│  - Lifecycle Management                                     │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   Monitoring System                          │
│  Event Bus (Pub/Sub)  ←→  Metrics Collector                │
│  - process.started         - Execution times                │
│  - process.completed       - Success rates                  │
│  - process.failed          - Aggregations                   │
│  - group.started/completed                                  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                      Core Framework                          │
│  Process (Abstract Base)                                    │
│  ├── AtomarProcess                                          │
│  └── OrchestratedProcess                                    │
│                                                             │
│  Parameter System                                           │
│  ├── InputParameter                                         │
│  ├── OutputParameter                                        │
│  └── ParameterSet                                           │
└─────────────────────────────────────────────────────────────┘
```

**Data Flow:**

```
User Request
    ↓
Registry.create("WorkflowName")
    ↓
Workflow Instance
    ↓
Set Input Parameters
    ↓
Execute()
    ↓
Orchestration Engine
    ↓
[Event: process.started]
    ↓
Execute Child Processes (Sequential/Parallel Groups)
    ↓
Resolve Parameter Connections
    ↓
[Event: process.completed]
    ↓
Collect Metrics
    ↓
Return Output Parameters
```

---

## Creating Processes

### Atomic Process Template

```python
from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter

class ProcessMyTask(AtomarProcess):
    """
    Brief description of what this process does.

    Inputs:
        input1 (type): Description
        input2 (type): Description

    Outputs:
        output1 (type): Description
    """

    def __init__(self, name: str = "MyTask"):
        super().__init__(name)

        # Define inputs
        self.input.add(InputParameter(
            name="input1",
            param_type=str,
            required=True,
            description="First input"
        ))
        self.input.add(InputParameter(
            name="input2",
            param_type=int,
            required=False,
            default=10,
            description="Second input with default"
        ))

        # Define outputs
        self.output.add(OutputParameter(
            name="output1",
            param_type=dict,
            description="Result"
        ))

    async def execute_impl(self):
        """
        Main execution logic.

        Access inputs via: self.input["name"].value
        Set outputs via: self.output["name"].value = result
        """
        input1 = self.input["input1"].value
        input2 = self.input["input2"].value

        # Your logic here
        result = {"input1": input1, "count": input2}

        # Set output
        self.output["output1"].value = result

    async def on_before_execute(self):
        """
        Hook: Called before execute_impl()
        Use for validation, setup, etc.
        """
        # Optional validation
        if len(self.input["input1"].value) == 0:
            raise ValueError("input1 cannot be empty")

    async def on_after_execute(self):
        """
        Hook: Called after execute_impl()
        Use for cleanup, logging, etc.
        """
        # Optional cleanup
        print(f"Process {self.name} completed successfully")
```

### Orchestrated Process Template

```python
from swfme.core.process import OrchestratedProcess, ProcessExecutionFlags
from swfme.core.parameters import InputParameter, OutputParameter

class MyWorkflow(OrchestratedProcess):
    """
    Brief description of the workflow.

    Flow:
        ProcessA → ProcessB → [ProcessC, ProcessD] → ProcessE
               Sequential      Parallel          Sequential

    Inputs:
        workflow_input (type): Description

    Outputs:
        workflow_output (type): Description
    """

    def __init__(self, name: str = "MyWorkflow"):
        super().__init__(name)

        # Workflow-level inputs (from external caller)
        self.input.add(InputParameter(
            name="workflow_input",
            param_type=str,
            required=True,
            description="Input to the workflow"
        ))

        # Workflow-level outputs (to external caller)
        self.output.add(OutputParameter(
            name="workflow_output",
            param_type=dict,
            description="Final result"
        ))

    def define_orchestration(self):
        """
        Define the workflow structure.

        Called automatically before execution.
        Create process instances and define their connections.
        """
        # Create process instances
        process_a = ProcessA()
        process_b = ProcessB()
        process_c = ProcessC()
        process_d = ProcessD()
        process_e = ProcessE()

        # =====================================
        # Group 1: ProcessA (Sequential)
        # =====================================
        self.add_child(process_a, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))

        # Connect workflow input to ProcessA
        self._connect_param(
            self.input["workflow_input"],
            process_a.input["some_input"]
        )

        # =====================================
        # Group 2: ProcessB (Sequential)
        # =====================================
        self.add_child(process_b, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))

        # Connect ProcessA output to ProcessB input
        self._connect_param(
            process_a.output["result"],
            process_b.input["data"]
        )

        # =====================================
        # Group 3: ProcessC + ProcessD (PARALLEL)
        # =====================================
        self.add_child(process_c, ProcessExecutionFlags(
            parallel=True,  # ← Runs in parallel!
            wait_for_completion=True
        ))
        self.add_child(process_d, ProcessExecutionFlags(
            parallel=True,  # ← Runs in parallel!
            wait_for_completion=True
        ))

        # Both processes get input from ProcessB
        self._connect_param(
            process_b.output["transformed_data"],
            process_c.input["data"]
        )
        self._connect_param(
            process_b.output["transformed_data"],
            process_d.input["data"]
        )

        # =====================================
        # Group 4: ProcessE (Sequential)
        # =====================================
        self.add_child(process_e, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))

        # ProcessE gets inputs from both parallel processes
        self._connect_param(
            process_c.output["result_c"],
            process_e.input["input_c"]
        )
        self._connect_param(
            process_d.output["result_d"],
            process_e.input["input_d"]
        )

        # =====================================
        # Workflow Output
        # =====================================
        self._connect_param(
            process_e.output["final_result"],
            self.output["workflow_output"]
        )
```

---

## Parameter System

### Parameter Types

```python
# Supported Python types
InputParameter("text", str)
InputParameter("count", int)
InputParameter("ratio", float)
InputParameter("enabled", bool)
InputParameter("items", list)
InputParameter("config", dict)

# Custom types (must be serializable)
from dataclasses import dataclass

@dataclass
class CustomData:
    name: str
    value: int

InputParameter("custom", CustomData)
```

### Parameter Validation

```python
class ProcessWithValidation(AtomarProcess):
    def __init__(self):
        super().__init__("Validation")
        self.input.add(InputParameter(
            name="age",
            param_type=int,
            required=True
        ))

    async def on_before_execute(self):
        """Custom validation"""
        age = self.input["age"].value
        if age < 0 or age > 150:
            raise ValueError(f"Invalid age: {age}")
```

### Required vs Optional

```python
# Required parameter - must be set before execution
self.input.add(InputParameter(
    name="required_param",
    param_type=str,
    required=True  # ← Must be set!
))

# Optional parameter with default
self.input.add(InputParameter(
    name="optional_param",
    param_type=int,
    required=False,
    default=42  # ← Used if not set
))
```

### Parameter Connections

**IMPORTANT:** Parameter connections are resolved at **runtime**, not at orchestration definition time!

```python
# ✅ CORRECT: Store connection, resolved during execution
self._connect_param(
    source.output["data"],
    target.input["data"]
)

# ❌ WRONG: Direct access during orchestration
target.input["data"].value = source.output["data"].value
# This fails because source hasn't executed yet!
```

**How it works:**

```python
def define_orchestration(self):
    load = ProcessLoad()
    transform = ProcessTransform()

    # 1. Define connection (stored, not executed)
    self._connect_param(load.output["data"], transform.input["data"])

    # 2. Add to workflow
    self.add_child(load)
    self.add_child(transform)

# During execution:
# 1. ProcessLoad executes
# 2. ProcessLoad.output["data"].value = [1,2,3]
# 3. Connection resolved: ProcessTransform.input["data"].value = [1,2,3]
# 4. ProcessTransform executes with the data
```

### Parameter Locking

Parameters are locked after process execution to prevent modification:

```python
process = ProcessLoad()
await process.execute()

# After execution, parameters are locked
process.output["data"].value = [4,5,6]  # ❌ RuntimeError: Parameter locked!
```

---

## Orchestration

### Execution Groups

Processes are organized into **execution groups** based on `parallel` flag:

```python
def define_orchestration(self):
    # Group 1 (Sequential)
    self.add_child(p1, ProcessExecutionFlags(parallel=False))
    self.add_child(p2, ProcessExecutionFlags(parallel=False))

    # Group 2 (Parallel)
    self.add_child(p3, ProcessExecutionFlags(parallel=True))
    self.add_child(p4, ProcessExecutionFlags(parallel=True))
    self.add_child(p5, ProcessExecutionFlags(parallel=True))

    # Group 3 (Sequential)
    self.add_child(p6, ProcessExecutionFlags(parallel=False))

# Execution order:
# [p1] → [p2] → [p3 + p4 + p5] → [p6]
#  G1     G1         G2           G3
```

### ProcessExecutionFlags

```python
class ProcessExecutionFlags:
    parallel: bool = False              # Run in parallel with other processes in group
    wait_for_completion: bool = True    # Wait for process to complete before continuing

# Common patterns:

# Sequential, wait for completion
ProcessExecutionFlags(parallel=False, wait_for_completion=True)

# Parallel, wait for completion
ProcessExecutionFlags(parallel=True, wait_for_completion=True)

# Fire-and-forget (rarely used)
ProcessExecutionFlags(parallel=True, wait_for_completion=False)
```

### Data Flow Patterns

#### 1. Linear Flow (Sequential)

```python
# A → B → C
self.add_child(a)
self.add_child(b)
self.add_child(c)

self._connect_param(a.output["data"], b.input["data"])
self._connect_param(b.output["data"], c.input["data"])
```

#### 2. Fan-Out (One-to-Many)

```python
# A → [B, C, D]
self.add_child(a, ProcessExecutionFlags(parallel=False))

self.add_child(b, ProcessExecutionFlags(parallel=True))
self.add_child(c, ProcessExecutionFlags(parallel=True))
self.add_child(d, ProcessExecutionFlags(parallel=True))

# All get same data from A
self._connect_param(a.output["data"], b.input["data"])
self._connect_param(a.output["data"], c.input["data"])
self._connect_param(a.output["data"], d.input["data"])
```

#### 3. Fan-In (Many-to-One)

```python
# [A, B, C] → D
self.add_child(a, ProcessExecutionFlags(parallel=True))
self.add_child(b, ProcessExecutionFlags(parallel=True))
self.add_child(c, ProcessExecutionFlags(parallel=True))

self.add_child(d, ProcessExecutionFlags(parallel=False))

# D receives from all
self._connect_param(a.output["result"], d.input["input_a"])
self._connect_param(b.output["result"], d.input["input_b"])
self._connect_param(c.output["result"], d.input["input_c"])
```

#### 4. Diamond Pattern

```python
#      A
#     / \
#    B   C
#     \ /
#      D

self.add_child(a, ProcessExecutionFlags(parallel=False))

self.add_child(b, ProcessExecutionFlags(parallel=True))
self.add_child(c, ProcessExecutionFlags(parallel=True))

self.add_child(d, ProcessExecutionFlags(parallel=False))

self._connect_param(a.output["data"], b.input["data"])
self._connect_param(a.output["data"], c.input["data"])
self._connect_param(b.output["result"], d.input["result_b"])
self._connect_param(c.output["result"], d.input["result_c"])
```

### Nested Orchestration

Orchestrated processes can contain other orchestrated processes:

```python
class SubWorkflow(OrchestratedProcess):
    def define_orchestration(self):
        self.add_child(ProcessA())
        self.add_child(ProcessB())

class MainWorkflow(OrchestratedProcess):
    def define_orchestration(self):
        sub1 = SubWorkflow()  # ← Orchestrated process as child!
        sub2 = SubWorkflow()
        final = ProcessFinal()

        self.add_child(sub1)
        self.add_child(sub2, ProcessExecutionFlags(parallel=True))
        self.add_child(final)
```

---

## Event System

### Event Types

```python
# Process lifecycle events
"process.started"           # Process begins execution
"process.completed"         # Process completed successfully
"process.failed"            # Process failed with error

# Group events (for orchestrated processes)
"process.group_started"     # Execution group started
"process.group_completed"   # Execution group completed
```

### Event Structure

```python
{
    "type": "process.started",
    "process_id": "uuid-string",
    "process_name": "LoadData",
    "process_class": "ProcessLoadData",
    "timestamp": "2025-11-28T18:00:00.123456",
    "status": "running"
}

{
    "type": "process.completed",
    "process_id": "uuid-string",
    "process_name": "LoadData",
    "process_class": "ProcessLoadData",
    "timestamp": "2025-11-28T18:00:02.456789",
    "status": "completed",
    "execution_time_ms": 2333.333  # Optional
}

{
    "type": "process.failed",
    "process_id": "uuid-string",
    "process_name": "LoadData",
    "process_class": "ProcessLoadData",
    "timestamp": "2025-11-28T18:00:02.456789",
    "status": "failed",
    "error": "Connection timeout"
}

{
    "type": "process.group_started",
    "process_id": "uuid-of-parent",
    "process_name": "DataPipeline",
    "process_class": "DataProcessingPipeline",
    "timestamp": "2025-11-28T18:00:00",
    "status": "running",
    "group_index": 2,
    "group_size": 3,
    "execution_mode": "parallel"
}
```

### Subscribe to Events

```python
from swfme.monitoring.event_bus import event_bus

# Subscribe to specific event type
def on_started(event):
    print(f"Process {event['process_name']} started")

event_bus.subscribe("process.started", on_started)

# Subscribe to all events
def on_any_event(event):
    print(f"Event: {event['type']}")

event_bus.subscribe("*", on_any_event)

# Unsubscribe
event_bus.unsubscribe("process.started", on_started)
```

### Custom Event Handlers

```python
from swfme.monitoring.event_bus import event_bus

class ProcessLogger:
    def __init__(self):
        event_bus.subscribe("process.completed", self.log_completion)

    def log_completion(self, event):
        print(f"[LOG] {event['process_name']} completed in {event.get('execution_time_ms', 0)}ms")

logger = ProcessLogger()
```

---

## Metrics & Monitoring

### ProcessMetrics

Individual process execution metrics:

```python
from swfme.monitoring.metrics import metrics_collector

# Get metrics for specific process execution
metrics = metrics_collector.get_metrics("process-uuid")

print(f"Process: {metrics.process_name}")
print(f"Status: {metrics.status}")
print(f"Started: {metrics.started_at}")
print(f"Completed: {metrics.completed_at}")
print(f"Duration: {metrics.execution_time_ms}ms")
print(f"Failed: {metrics.is_failed}")
```

### AggregatedMetrics

Aggregated metrics across all executions of a process class:

```python
from swfme.monitoring.metrics import metrics_collector

# Get aggregated metrics for a process class
agg = metrics_collector.get_aggregated_metrics("ProcessLoadData")

print(f"Total executions: {agg.total_executions}")
print(f"Successful: {agg.successful_executions}")
print(f"Failed: {agg.failed_executions}")
print(f"Success rate: {agg.success_rate * 100}%")
print(f"Avg time: {agg.avg_execution_time_ms}ms")
print(f"Min time: {agg.min_execution_time_ms}ms")
print(f"Max time: {agg.max_execution_time_ms}ms")
print(f"Last execution: {agg.last_execution_at}")
```

### Custom Metrics Collection

```python
from swfme.monitoring.event_bus import event_bus
from swfme.monitoring.metrics import metrics_collector

class CustomMetricsCollector:
    def __init__(self):
        self.slow_processes = []
        event_bus.subscribe("process.completed", self.check_performance)

    def check_performance(self, event):
        if event.get('execution_time_ms', 0) > 5000:
            self.slow_processes.append({
                'name': event['process_name'],
                'time': event['execution_time_ms'],
                'timestamp': event['timestamp']
            })
            print(f"⚠️ Slow process detected: {event['process_name']} took {event['execution_time_ms']}ms")

collector = CustomMetricsCollector()
```

---

## Testing

### Unit Testing Atomic Processes

```python
import pytest
from your_module import ProcessCalculateSum

@pytest.mark.asyncio
async def test_calculate_sum():
    # Arrange
    process = ProcessCalculateSum()
    process.input["numbers"].value = [1, 2, 3, 4, 5]

    # Act
    await process.execute()

    # Assert
    assert process.output["sum"].value == 15
    assert process.status == "completed"

@pytest.mark.asyncio
async def test_calculate_sum_empty_list():
    process = ProcessCalculateSum()
    process.input["numbers"].value = []

    await process.execute()

    assert process.output["sum"].value == 0

@pytest.mark.asyncio
async def test_calculate_sum_validation():
    process = ProcessCalculateSum()

    # Missing required parameter
    with pytest.raises(ValueError):
        await process.execute()
```

### Testing Orchestrated Processes

```python
import pytest
from your_module import DataPipeline

@pytest.mark.asyncio
async def test_data_pipeline():
    # Arrange
    pipeline = DataPipeline()
    pipeline.input["filename"].value = "test_data.csv"

    # Act
    await pipeline.execute()

    # Assert
    assert pipeline.status == "completed"
    assert pipeline.output["result_path"].value is not None
    assert pipeline.output["row_count"].value > 0

@pytest.mark.asyncio
async def test_data_pipeline_with_mocked_processes(monkeypatch):
    """Test workflow with mocked child processes"""

    # Mock ProcessLoadData
    async def mock_execute(self):
        self.output["data"].value = [{"id": 1}]
        self.output["row_count"].value = 1

    monkeypatch.setattr("your_module.ProcessLoadData.execute_impl", mock_execute)

    pipeline = DataPipeline()
    pipeline.input["filename"].value = "test.csv"

    await pipeline.execute()

    assert pipeline.status == "completed"
```

### Testing with Events

```python
import pytest
from swfme.monitoring.event_bus import event_bus

@pytest.mark.asyncio
async def test_process_emits_events():
    events = []

    def capture_event(event):
        events.append(event)

    event_bus.subscribe("*", capture_event)

    process = ProcessCalculateSum()
    process.input["numbers"].value = [1, 2, 3]

    await process.execute()

    # Check events were emitted
    assert len(events) >= 2  # At least started + completed
    assert events[0]["type"] == "process.started"
    assert events[-1]["type"] == "process.completed"

    event_bus.unsubscribe("*", capture_event)
```

### Integration Testing

```python
import pytest
from swfme.registry.process_registry import process_registry

@pytest.mark.asyncio
async def test_full_workflow_integration():
    """Test complete workflow end-to-end"""

    # Create workflow from registry
    workflow = process_registry.create("DataPipeline")

    # Set inputs
    workflow.input["filename"].value = "integration_test.csv"

    # Execute
    await workflow.execute()

    # Verify outputs
    assert workflow.status == "completed"
    assert workflow.output["result_path"].value.endswith(".json")
    assert workflow.output["statistics"].value["count"] > 0
```

---

## Advanced Patterns

### 1. Conditional Execution

```python
class ConditionalWorkflow(OrchestratedProcess):
    def define_orchestration(self):
        check = ProcessCheck()
        process_a = ProcessA()
        process_b = ProcessB()

        self.add_child(check)
        self.add_child(process_a)  # Always added
        self.add_child(process_b)  # Always added

        # Use parameter to control which runs
        self._connect_param(check.output["should_run_a"], process_a.input["enabled"])
        self._connect_param(check.output["should_run_b"], process_b.input["enabled"])

class ProcessA(AtomarProcess):
    async def execute_impl(self):
        if not self.input["enabled"].value:
            return  # Skip execution

        # Normal logic...
```

### 2. Dynamic Process Creation

```python
class DynamicWorkflow(OrchestratedProcess):
    def define_orchestration(self):
        # Create processes based on input
        num_workers = self.input["worker_count"].value

        for i in range(num_workers):
            worker = ProcessWorker(name=f"Worker{i}")
            self.add_child(worker, ProcessExecutionFlags(parallel=True))
```

### 3. Error Handling & Retry

```python
class ProcessWithRetry(AtomarProcess):
    def __init__(self):
        super().__init__()
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    async def execute_impl(self):
        for attempt in range(self.max_retries):
            try:
                result = await self.do_work()
                self.output["result"].value = result
                return  # Success!
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    raise  # Final attempt failed

    async def do_work(self):
        # Actual work that might fail
        pass
```

### 4. Process Pooling

```python
class ProcessPool:
    def __init__(self, process_class, size=5):
        self.process_class = process_class
        self.pool = [process_class() for _ in range(size)]
        self.available = asyncio.Queue()
        for p in self.pool:
            self.available.put_nowait(p)

    async def execute(self, **inputs):
        process = await self.available.get()
        try:
            for key, value in inputs.items():
                process.input[key].value = value
            await process.execute()
            return process.output
        finally:
            self.available.put_nowait(process)

# Usage
pool = ProcessPool(ProcessHeavyTask, size=10)
results = await asyncio.gather(*[
    pool.execute(data=item) for item in large_dataset
])
```

### 5. Pipeline Checkpointing

```python
class CheckpointedWorkflow(OrchestratedProcess):
    async def on_after_execute(self):
        """Save workflow state after execution"""
        checkpoint = {
            'workflow_id': self.id,
            'inputs': self.input.to_dict(),
            'outputs': self.output.to_dict(),
            'timestamp': datetime.now().isoformat()
        }
        await self.save_checkpoint(checkpoint)

    async def save_checkpoint(self, data):
        # Save to database, file, etc.
        pass

    async def restore_from_checkpoint(self, checkpoint_id):
        # Load checkpoint and restore state
        pass
```

---

## Best Practices

### 1. Process Design

**✅ DO:**
- Single Responsibility: One process = one task
- Clear naming: `ProcessLoadData`, not `ProcessDoStuff`
- Type-safe parameters with descriptions
- Idempotent operations where possible
- Proper error handling

**❌ DON'T:**
- Multiple responsibilities in one process
- Hidden side effects
- Direct database/file access without abstraction
- Tight coupling between processes

### 2. Parameter Naming

```python
# ✅ GOOD: Clear, descriptive names
self.input.add(InputParameter("source_file_path", str))
self.output.add(OutputParameter("validated_records", list))

# ❌ BAD: Vague names
self.input.add(InputParameter("data", object))  # What kind of data?
self.output.add(OutputParameter("result", object))  # What result?
```

### 3. Orchestration

```python
# ✅ GOOD: Clear structure, comments for groups
def define_orchestration(self):
    # Step 1: Load data
    load = ProcessLoad()
    self.add_child(load)

    # Step 2: Parallel processing
    validate = ProcessValidate()
    enrich = ProcessEnrich()
    self.add_child(validate, ProcessExecutionFlags(parallel=True))
    self.add_child(enrich, ProcessExecutionFlags(parallel=True))

    # Step 3: Combine results
    combine = ProcessCombine()
    self.add_child(combine)

    # Parameter connections
    self._connect_param(load.output["data"], validate.input["data"])
    self._connect_param(load.output["data"], enrich.input["data"])

# ❌ BAD: No structure, unclear flow
def define_orchestration(self):
    p1 = ProcessA()
    p2 = ProcessB()
    p3 = ProcessC()
    self.add_child(p1)
    self.add_child(p2)
    self.add_child(p3)
    # Where are the connections?
```

### 4. Error Handling

```python
# ✅ GOOD: Explicit error handling
class ProcessLoadFile(AtomarProcess):
    async def execute_impl(self):
        filepath = self.input["filepath"].value

        try:
            with open(filepath, 'r') as f:
                data = f.read()
            self.output["data"].value = data
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")
        except PermissionError:
            raise PermissionError(f"No permission to read: {filepath}")

# ❌ BAD: Silent failures
class ProcessLoadFile(AtomarProcess):
    async def execute_impl(self):
        try:
            data = open(self.input["filepath"].value).read()
            self.output["data"].value = data
        except:
            self.output["data"].value = None  # Hides the error!
```

### 5. Documentation

```python
# ✅ GOOD: Complete documentation
class ProcessTransformData(AtomarProcess):
    """
    Transform raw data to normalized format.

    This process converts input data from various formats
    (JSON, CSV, XML) to a standardized internal format.

    Inputs:
        raw_data (str): Raw data string
        format (str): Input format ('json', 'csv', 'xml')

    Outputs:
        normalized_data (dict): Normalized data structure
        record_count (int): Number of records processed

    Raises:
        ValueError: If format is not supported
        ParseError: If data cannot be parsed

    Example:
        >>> process = ProcessTransformData()
        >>> process.input["raw_data"].value = '{"key": "value"}'
        >>> process.input["format"].value = "json"
        >>> await process.execute()
        >>> print(process.output["normalized_data"].value)
    """
    pass

# ❌ BAD: No documentation
class ProcessTransformData(AtomarProcess):
    pass  # What does this do?
```

---

## API Reference

### Process Base Classes

#### Process (Abstract)

```python
class Process(ABC):
    """Abstract base class for all processes"""

    # Properties
    id: UUID                    # Unique process instance ID
    name: str                   # Process name
    status: str                 # Current status
    input: ParameterSet         # Input parameters
    output: ParameterSet        # Output parameters

    # Methods
    async def execute() -> None
    async def on_before_execute() -> None
    async def on_after_execute() -> None

    @abstractmethod
    async def execute_impl() -> None
```

#### AtomarProcess

```python
class AtomarProcess(Process):
    """Atomic process - single unit of work"""

    async def execute_impl() -> None:
        """Implement your process logic here"""
        pass
```

#### OrchestratedProcess

```python
class OrchestratedProcess(Process):
    """Orchestrated process - combines multiple processes"""

    children: List[Tuple[Process, ProcessExecutionFlags]]

    def define_orchestration() -> None:
        """Define workflow structure"""
        pass

    def add_child(process: Process, flags: ProcessExecutionFlags) -> None:
        """Add child process"""
        pass

    def _connect_param(source: Parameter, target: Parameter) -> None:
        """Connect parameters"""
        pass
```

### Parameters

```python
class InputParameter:
    def __init__(
        self,
        name: str,
        param_type: Type,
        required: bool = True,
        default: Any = None,
        description: str = ""
    ):
        pass

class OutputParameter:
    def __init__(
        self,
        name: str,
        param_type: Type,
        description: str = ""
    ):
        pass

class ParameterSet:
    def add(param: Parameter) -> None
    def __getitem__(name: str) -> Parameter
    def to_dict() -> Dict[str, Any]
```

### Process Registry

```python
class ProcessRegistry:
    def register(
        self,
        process_class: Type[Process],
        name: Optional[str] = None
    ) -> None:
        """Register a process class"""
        pass

    def create(
        self,
        name: str,
        instance_name: Optional[str] = None
    ) -> Process:
        """Create process instance"""
        pass

    def list_processes() -> List[Dict[str, Any]]:
        """List all registered processes"""
        pass

# Global registry instance
process_registry = ProcessRegistry()
```

### Event Bus

```python
class EventBus:
    async def emit(event: Dict[str, Any]) -> None:
        """Emit an event"""
        pass

    def subscribe(
        self,
        event_type: str,
        callback: Callable
    ) -> None:
        """Subscribe to events ('*' for all)"""
        pass

    def unsubscribe(
        self,
        event_type: str,
        callback: Callable
    ) -> None:
        """Unsubscribe from events"""
        pass

# Global event bus instance
event_bus = EventBus()
```

### Metrics Collector

```python
class MetricsCollector:
    def get_metrics(process_id: str) -> Optional[ProcessMetrics]:
        """Get metrics for specific process execution"""
        pass

    def get_aggregated_metrics(
        process_class: str
    ) -> AggregatedMetrics:
        """Get aggregated metrics for process class"""
        pass

    def get_all_metrics() -> Dict[str, ProcessMetrics]:
        """Get all process metrics"""
        pass

# Global metrics collector instance
metrics_collector = MetricsCollector()
```

---

## Next Steps

1. **Read Examples**: Check `examples/simple_workflow.py` for complete working example
2. **Run Tests**: `pytest tests/ -v` to see test patterns
3. **Try Dashboard**: Start server and explore visual orchestration
4. **Build Your First Process**: Start with a simple atomic process
5. **Create Workflow**: Combine processes into orchestrated workflow

---

**Happy Process-Oriented Programming! 🚀**

For specific integration guides:
- **Storage API Integration**: See `STORAGE_API_GUIDE.md`
- **General README**: See `README.md`
- **Examples**: See `examples/`
