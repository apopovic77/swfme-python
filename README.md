# sWFME Python - Workflow Management Engine

**Process-Oriented Programming Framework for Python**

A modern Python implementation of the original sWFME (sense Workflow Management Engine) from 2010, bringing process-oriented programming paradigms to modern Python applications.

---

## 🎯 **What is sWFME?**

sWFME is a workflow orchestration framework that treats **processes as first-class citizens**. Instead of hiding business logic in methods and classes, sWFME makes workflows **explicit, visual, and monitorable**.

### **Core Philosophy:**

```python
# Traditional OOP (Hidden Logic)
result = pipeline.process(data)  # What happens inside? 🤷

# Process-Oriented (Explicit Workflow)
pipeline = DataPipeline()
pipeline.input["data"].value = data
await pipeline.execute()
result = pipeline.output["result"].value  # Clear I/O, visible flow! ✨
```

---

## 🚀 **Key Features**

✅ **Declarative Workflows** - Define workflows as composable processes
✅ **Type-Safe Parameters** - Input/Output parameters with runtime validation
✅ **Sequential & Parallel Execution** - Automatic execution order resolution
✅ **Real-Time Monitoring** - Event bus for process observability
✅ **Comprehensive Metrics** - Per-process and aggregated performance analytics
✅ **Context-Independent** - Same process code runs locally or distributed
✅ **Clean Architecture** - SOLID principles, Template Method pattern

---

## 📦 **Installation**

```bash
# Clone repository
git clone https://github.com/apopovic77/swfme-python.git
cd swfme-python

# Install dependencies
pip install -e .
```

---

## 🎨 **Quick Start**

### **1. Define Atomic Processes**

```python
from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter

class ProcessLoadData(AtomarProcess):
    """Load data from a file"""

    def define_parameters(self):
        self.input.add(InputParameter("filename", str))
        self.output.add(OutputParameter("data", list))

    async def execute_impl(self):
        filename = self.input["filename"].value
        # Load data logic
        data = load_from_file(filename)
        self.output["data"].value = data
```

### **2. Compose Orchestrated Workflows**

```python
from swfme.core.process import OrchestratedProcess, ProcessExecutionFlags

class DataPipeline(OrchestratedProcess):
    """Complete data processing pipeline"""

    def define_parameters(self):
        self.input.add(InputParameter("filename", str))
        self.output.add(OutputParameter("result", dict))

    def orchestrate(self):
        # Sequential: Load → Transform
        load = ProcessLoadData()
        self._connect_param(self.input["filename"], load.input["filename"])
        self.add_child(load, ProcessExecutionFlags.SEQUENTIAL)

        transform = ProcessTransformData()
        self._connect_param(load.output["data"], transform.input["data"])
        self.add_child(transform, ProcessExecutionFlags.SEQUENTIAL)

        # Parallel: Validate AND Analyze (concurrently!)
        validate = ProcessValidateData()
        self._connect_param(transform.output["data"], validate.input["data"])
        self.add_child(validate, ProcessExecutionFlags.PARALLEL)

        analyze = ProcessAnalyzeData()
        self._connect_param(transform.output["data"], analyze.input["data"])
        self.add_child(analyze, ProcessExecutionFlags.PARALLEL)

        # Sequential: Save (waits for parallel to complete)
        save = ProcessSaveResult()
        self._connect_param(analyze.output["stats"], save.input["stats"])
        self.add_child(save, ProcessExecutionFlags.SEQUENTIAL)

        # Output mapping
        self._connect_param(save.output["result"], self.output["result"])
```

### **3. Execute & Monitor**

```python
import asyncio
from swfme.monitoring.event_bus import event_bus

# Subscribe to events
async def monitor(event):
    print(f"{event['type']}: {event['process_name']}")

event_bus.subscribe("*", monitor)

# Execute workflow
pipeline = DataPipeline()
pipeline.input["filename"].value = "data.csv"

success = await pipeline.execute()

if success:
    print(f"Result: {pipeline.output['result'].value}")
    print(f"Execution time: {pipeline.execution_time_ms}ms")
```

---

## 📊 **Workflow Visualization**

```
DataPipeline
├── LoadData (Sequential)
│   └── Output: data
├── TransformData (Sequential)
│   └── Output: transformed_data
├── ┌─ ValidateData (Parallel) ─┐
│   │  └── Output: is_valid     │
│   └─ AnalyzeData (Parallel) ──┘
│      └── Output: stats
└── SaveResult (Sequential)
    └── Output: result
```

---

## 📈 **Metrics & Analytics**

sWFME automatically collects comprehensive metrics:

```python
from swfme.monitoring.metrics import metrics_collector

# Per-execution metrics
metrics = metrics_collector.get_metrics(pipeline.id)
print(f"Execution time: {metrics.execution_time_ms}ms")
print(f"Status: {metrics.status}")

# Aggregated metrics (per process class)
agg = metrics_collector.get_aggregated_metrics("DataPipeline")
print(f"Total executions: {agg.total_executions}")
print(f"Success rate: {agg.success_rate:.1%}")
print(f"Avg execution time: {agg.avg_execution_time_ms}ms")

# Overall summary
summary = metrics_collector.get_summary()
print(f"Total processes: {summary['total_processes']}")
print(f"Success rate: {summary['success_rate']:.1%}")
```

---

## 🏗️ **Architecture**

### **Core Components:**

```
swfme/
├── core/
│   ├── process.py        # Process base classes (Template Method pattern)
│   ├── parameters.py     # Type-safe parameter system
│   └── executor.py       # Execution engine (coming soon)
├── monitoring/
│   ├── event_bus.py      # Pub/Sub event system
│   └── metrics.py        # Metrics collection & aggregation
├── api/
│   └── routes.py         # FastAPI endpoints (coming soon)
└── registry/
    └── process_registry.py  # Process discovery (coming soon)
```

### **Design Patterns:**

- **Template Method** - `Process.execute()` defines workflow, subclasses implement `execute_impl()`
- **Composite** - `OrchestratedProcess` composes child processes
- **Observer** - Event bus for monitoring
- **Singleton** - Global event bus & metrics collector

---

## 🔥 **Why Process-Oriented Programming?**

### **Problems with Traditional OOP:**

```python
# Traditional: Hidden complexity
async def process_upload(file):
    # What happens here?
    # - File storage?
    # - AI analysis?
    # - Transcoding?
    # - Knowledge graph?
    # No visibility, hard to debug, impossible to monitor
    result = await upload_pipeline.process(file)
    return result
```

### **Solution: Explicit Process Flow:**

```python
# sWFME: Transparent, monitorable
class UploadPipeline(OrchestratedProcess):
    def orchestrate(self):
        self.add_child(ProcessSaveFile(), SEQUENTIAL)
        self.add_child(ProcessAIAnalysis(), PARALLEL)
        self.add_child(ProcessTranscoding(), PARALLEL)
        self.add_child(ProcessBuildKnowledgeGraph(), SEQUENTIAL)
```

**Benefits:**
✅ **Visibility** - See exactly what happens
✅ **Debugging** - Clear error location, input/output inspection
✅ **Monitoring** - Real-time metrics per process
✅ **Testing** - Test individual processes in isolation
✅ **Reusability** - Compose workflows from existing processes

---

## 📚 **Examples**

### **Run the Demo:**

```bash
python examples/simple_workflow.py
```

Output:
```
======================================================================
sWFME Demo: Data Processing Pipeline
======================================================================

▶️ Started: DataPipeline
📦 Execution Group (sequential): 1 process(es)
📂 Loading data from: data.csv
   ✓ Loaded 4 rows
✅ Completed: LoadData (501ms)

📦 Execution Group (parallel): 2 process(es)
✅ Validating 3 rows...
📊 Analyzing 3 rows...
   ✓ Validation passed
   ✓ Analysis complete: avg=400.0, sum=1200
✅ Completed: ValidateData (402ms)
✅ Completed: AnalyzeData (501ms)

✅ Workflow completed successfully!
Execution Time: 1608ms
Success Rate: 100.0%
```

---

## 🚧 **Roadmap**

### **Phase 1: Core Framework** ✅ (DONE!)
- [x] Process base classes
- [x] Parameter system
- [x] Sequential/Parallel execution
- [x] Event bus
- [x] Metrics collector

### **Phase 2: API & Integration** (In Progress)
- [ ] FastAPI REST endpoints
- [ ] WebSocket real-time monitoring
- [ ] Process registry
- [ ] Unit tests

### **Phase 3: Visualization** (Planned)
- [ ] React dashboard
- [ ] D3.js flow diagram
- [ ] Real-time execution tracking
- [ ] Historical analytics

### **Phase 4: Advanced Features** (Future)
- [ ] Distributed execution (PEE/PCE)
- [ ] Workflow designer (Drag & Drop)
- [ ] Debug mode (step-through)
- [ ] Persistent workflow storage

---

## 🎓 **History & Inspiration**

sWFME Python is a modernized version of the original **sWFME** (sense Workflow Management Engine) developed in C# in 2010 as a student project by Alex Popovic.

### **Original Innovation (2010):**
- Process-oriented programming paradigm
- Distributed execution with load balancing
- Type-safe parameter passing
- Context-independent process design

### **Modern Evolution (2025):**
- Python async/await
- Modern web technologies (FastAPI, React)
- Cloud-native architecture
- Real-time observability

**The core ideas from 2010 are still relevant today!** The industry has built similar tools (Kubernetes, Temporal, Airflow), but sWFME offers a unique Python-native, lightweight alternative.

---

## 👨‍💻 **Author**

**Alex Popovic (Arkturian)**
- 10+ years experience in Clean Architecture & OOP
- Specialization: 3D Engine Development, Field-Aware Systems, FastAPI
- Philosophy: "Geile Ideen, geile Sachen bauen" 🚀

---

## 📄 **License**

MIT License - See LICENSE file for details

---

## 🤝 **Contributing**

Contributions welcome! Please open an issue or PR.

---

**🌟 If you find this useful, give it a star!**

---

## 📖 **Documentation**

Full documentation coming soon. For now, check:
- `examples/simple_workflow.py` - Complete working example
- Source code docstrings - Comprehensive inline documentation
- `swfme/core/process.py` - Architecture overview

---

**Built with ❤️ in 2025, inspired by innovation from 2010**
