# sWFME für storage-api - Entwickler-Guide

**Vollständige Anleitung zur Integration von sWFME in die storage-api Pipeline**

---

## 📋 Inhaltsverzeichnis

1. [Was ist sWFME?](#was-ist-swfme)
2. [Warum sWFME für storage-api?](#warum-swfme)
3. [Quick Start](#quick-start)
4. [Storage-API Pipeline mit sWFME](#storage-api-pipeline)
5. [Prozesse Schritt-für-Schritt](#prozesse-erstellen)
6. [Dashboard & Monitoring](#dashboard--monitoring)
7. [API Integration](#api-integration)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Was ist sWFME?

sWFME = **sense Workflow Management Engine**

Ein Framework für **Process-Oriented Programming (POP)** - eine Alternative zu versteckter Business-Logic in OOP.

### Problem mit storage-api aktuell:

```python
# async_pipeline.py
async def async_pipeline(storage_object_id: int, tenant_id: str):
    # Was passiert hier genau?
    # Welcher Schritt läuft gerade?
    # Wie lange dauert jeder Schritt?
    # Kann man Schritte parallel laufen lassen?
    # 🤷 Alles unklar!

    await save_to_database(...)
    metadata = await extract_metadata(...)
    await ai_safety_check(...)  # Wie lange dauert das?
    await video_transcode(...)   # Läuft parallel?
    await update_knowledge_graph(...)
```

### Lösung mit sWFME:

```python
# Jeder Schritt ist ein eigener Process
class ProcessSaveToDatabase(AtomarProcess):
    """Save storage object to database"""
    # Klare Inputs/Outputs
    # Wiederverwendbar
    # Messbar

class StorageUploadPipeline(OrchestratedProcess):
    """Complete storage upload workflow"""

    def define_orchestration(self):
        # VISUELL im Dashboard sichtbar!
        # Welche Schritte? ✅
        # Sequential oder Parallel? ✅
        # Execution Times? ✅
        # Fehler? ✅
```

**Vorteile:**
- 🎯 **Transparenz**: Sehe genau was läuft, in welcher Reihenfolge
- 📊 **Monitoring**: Echtzeit-Visualisierung im Dashboard
- ⚡ **Performance**: Parallele Ausführung wo sinnvoll
- 🔧 **Wartbarkeit**: Jeder Prozess ist isoliert und testbar
- 📈 **Metrics**: Automatische Erfassung von Zeiten, Success Rates

---

## Warum sWFME?

### Dein aktueller storage-api Upload Flow:

```
File Upload
    ↓
async_pipeline() ← Black Box!
    ↓
Done (maybe?)
```

### Mit sWFME:

```
File Upload
    ↓
┌─────────────────────────────────────────┐
│     StorageUploadPipeline               │
│                                         │
│  SaveToDatabase                         │
│       ↓                                 │
│  ExtractMetadata                        │
│       ↓                                 │
│  ╔═══════════════╗                      │
│  ║ PARALLEL      ║                      │
│  ╠═══════════════╣                      │
│  ║ AISafetyCheck ║ ← 2.5s              │
│  ║ TranscodeVideo║ ← 15.3s             │
│  ║ UpdateKG      ║ ← 1.2s              │
│  ╚═══════════════╝                      │
│       ↓                                 │
│  UpdateStatus                           │
└─────────────────────────────────────────┘
    ↓
Done ✓
```

**Du siehst:**
- Welcher Schritt läuft gerade
- Wie lange jeder Schritt dauert
- Was parallel läuft (AI + Transcode + KG gleichzeitig!)
- Wo Fehler auftreten

---

## Quick Start

### 1. Installation

```bash
cd /Volumes/DatenAP/Code/swfme-python

# Dependencies installieren
pip install -r requirements.txt

# Dashboard dependencies
cd dashboard
npm install
cd ..
```

### 2. Server starten

**Terminal 1 - Backend:**
```bash
python server.py
# → http://localhost:8000
```

**Terminal 2 - Dashboard:**
```bash
cd dashboard
npm run dev
# → http://localhost:5177
```

### 3. Dashboard öffnen

Browser: `http://localhost:5177`

Tabs:
- **🔀 Orchestration Graph** - Zeigt Workflow-Struktur
- **📊 Live Execution** - Echtzeit-Ausführung
- **🔧 Workflows** - Liste & Execute
- **📈 Metrics** - Statistiken

### 4. Demo ausführen

1. Gehe zu "🔧 Workflows"
2. Finde "DataPipeline"
3. Klicke "Execute"
4. Wechsle zu "📊 Live Execution" → Siehst Prozesse in Echtzeit!
5. Wechsle zu "🔀 Orchestration Graph" → Siehst die Struktur!

---

## Storage-API Pipeline

### Aktueller storage-api Code

```python
# storage-api/app/services/async_pipeline.py
async def async_pipeline(storage_object_id: int, tenant_id: str):
    """Background processing for uploaded files"""

    # 1. Save to database
    storage_obj = await save_initial_record(storage_object_id)

    # 2. Extract metadata
    metadata = await extract_file_metadata(storage_obj)

    # 3. AI safety check (Gemini Vision)
    safety_result = await ai_vision_check(storage_obj)

    # 4. Video transcoding (if video)
    if is_video(storage_obj):
        hls_url = await transcode_to_hls(storage_obj)

    # 5. Update knowledge graph
    await update_knowledge_graph_embeddings(storage_obj)

    # 6. Update status
    await update_status(storage_object_id, "completed")
```

### Mit sWFME

#### Schritt 1: Atomic Processes erstellen

Erstelle: `storage-api/app/workflows/storage_processes.py`

```python
from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter
from app.services.storage_service import StorageService
from app.services.ai_service import AIService
from app.services.video_service import VideoService
from app.services.kg_service import KnowledgeGraphService

class ProcessSaveToDatabase(AtomarProcess):
    """Save uploaded file to database"""

    def __init__(self, name: str = "SaveToDatabase"):
        super().__init__(name)

        # Inputs
        self.input.add(InputParameter(
            name="file_path",
            param_type=str,
            required=True,
            description="Path to uploaded file"
        ))
        self.input.add(InputParameter(
            name="tenant_id",
            param_type=str,
            required=True
        ))

        # Outputs
        self.output.add(OutputParameter(
            name="storage_id",
            param_type=int,
            description="Database ID of storage object"
        ))
        self.output.add(OutputParameter(
            name="storage_object",
            param_type=dict,
            description="Complete storage object data"
        ))

    async def execute_impl(self):
        """Save to database"""
        file_path = self.input["file_path"].value
        tenant_id = self.input["tenant_id"].value

        # Deine existing logic
        storage_service = StorageService()
        storage_obj = await storage_service.create_from_file(
            file_path=file_path,
            tenant_id=tenant_id
        )

        # Set outputs
        self.output["storage_id"].value = storage_obj.id
        self.output["storage_object"].value = storage_obj.to_dict()


class ProcessExtractMetadata(AtomarProcess):
    """Extract file metadata (dimensions, mime type, etc.)"""

    def __init__(self, name: str = "ExtractMetadata"):
        super().__init__(name)

        self.input.add(InputParameter("storage_id", int, required=True))
        self.output.add(OutputParameter("metadata", dict))

    async def execute_impl(self):
        storage_id = self.input["storage_id"].value

        # Deine existing logic
        storage_service = StorageService()
        metadata = await storage_service.extract_metadata(storage_id)

        self.output["metadata"].value = metadata


class ProcessAISafetyCheck(AtomarProcess):
    """AI safety check using Gemini Vision API"""

    def __init__(self, name: str = "AISafetyCheck"):
        super().__init__(name)

        self.input.add(InputParameter("storage_id", int, required=True))
        self.output.add(OutputParameter("is_safe", bool))
        self.output.add(OutputParameter("safety_rating", str))
        self.output.add(OutputParameter("ai_title", str))
        self.output.add(OutputParameter("ai_tags", list))

    async def execute_impl(self):
        storage_id = self.input["storage_id"].value

        # Deine existing AI service logic
        ai_service = AIService()
        result = await ai_service.analyze_image(storage_id)

        self.output["is_safe"].value = result.is_safe
        self.output["safety_rating"].value = result.safety_rating
        self.output["ai_title"].value = result.title
        self.output["ai_tags"].value = result.tags


class ProcessTranscodeVideo(AtomarProcess):
    """Transcode video to HLS format"""

    def __init__(self, name: str = "TranscodeVideo"):
        super().__init__(name)

        self.input.add(InputParameter("storage_id", int, required=True))
        self.input.add(InputParameter("is_video", bool, required=True))
        self.output.add(OutputParameter("hls_url", str))

    async def execute_impl(self):
        storage_id = self.input["storage_id"].value
        is_video = self.input["is_video"].value

        if not is_video:
            self.output["hls_url"].value = None
            return

        # Deine existing video transcode logic
        video_service = VideoService()
        hls_url = await video_service.transcode_to_hls(storage_id)

        self.output["hls_url"].value = hls_url


class ProcessUpdateKnowledgeGraph(AtomarProcess):
    """Update knowledge graph embeddings (Chroma DB)"""

    def __init__(self, name: str = "UpdateKnowledgeGraph"):
        super().__init__(name)

        self.input.add(InputParameter("storage_id", int, required=True))
        self.input.add(InputParameter("ai_title", str))
        self.input.add(InputParameter("ai_tags", list))
        self.output.add(OutputParameter("embedding_id", str))

    async def execute_impl(self):
        storage_id = self.input["storage_id"].value
        ai_title = self.input["ai_title"].value
        ai_tags = self.input["ai_tags"].value

        # Deine existing KG logic
        kg_service = KnowledgeGraphService()
        embedding_id = await kg_service.create_embedding(
            storage_id=storage_id,
            title=ai_title,
            tags=ai_tags
        )

        self.output["embedding_id"].value = embedding_id


class ProcessUpdateStatus(AtomarProcess):
    """Update storage object status to completed"""

    def __init__(self, name: str = "UpdateStatus"):
        super().__init__(name)

        self.input.add(InputParameter("storage_id", int, required=True))
        self.input.add(InputParameter("status", str, default="completed"))

    async def execute_impl(self):
        storage_id = self.input["storage_id"].value
        status = self.input["status"].value

        storage_service = StorageService()
        await storage_service.update_status(storage_id, status)
```

#### Schritt 2: Orchestrated Workflow erstellen

```python
from swfme.core.process import OrchestratedProcess, ProcessExecutionFlags

class StorageUploadPipeline(OrchestratedProcess):
    """
    Complete storage upload and processing pipeline

    Flow:
        SaveToDatabase → ExtractMetadata →
        [AISafetyCheck, TranscodeVideo, UpdateKG] (PARALLEL) →
        UpdateStatus
    """

    def __init__(self, name: str = "StorageUpload"):
        super().__init__(name)

        # Pipeline Inputs
        self.input.add(InputParameter("file_path", str, required=True))
        self.input.add(InputParameter("tenant_id", str, required=True))

        # Pipeline Outputs
        self.output.add(OutputParameter("storage_id", int))
        self.output.add(OutputParameter("is_safe", bool))
        self.output.add(OutputParameter("hls_url", str))
        self.output.add(OutputParameter("embedding_id", str))

    def define_orchestration(self):
        """Define workflow structure"""

        # Erstelle Prozess-Instanzen
        save_db = ProcessSaveToDatabase()
        extract_meta = ProcessExtractMetadata()
        ai_check = ProcessAISafetyCheck()
        transcode = ProcessTranscodeVideo()
        update_kg = ProcessUpdateKnowledgeGraph()
        update_status = ProcessUpdateStatus()

        # ========================================
        # Gruppe 1: Save to Database (Sequential)
        # ========================================
        self.add_child(save_db, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))

        # Connect Pipeline Input → SaveToDatabase
        self._connect_param(self.input["file_path"], save_db.input["file_path"])
        self._connect_param(self.input["tenant_id"], save_db.input["tenant_id"])

        # ========================================
        # Gruppe 2: Extract Metadata (Sequential)
        # ========================================
        self.add_child(extract_meta, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))

        # Connect SaveToDatabase → ExtractMetadata
        self._connect_param(save_db.output["storage_id"], extract_meta.input["storage_id"])

        # ========================================
        # Gruppe 3: PARALLEL Processing
        # AI Check + Video Transcode + KG Update
        # ========================================

        # AI Safety Check
        self.add_child(ai_check, ProcessExecutionFlags(
            parallel=True,  # ← Läuft PARALLEL!
            wait_for_completion=True
        ))
        self._connect_param(save_db.output["storage_id"], ai_check.input["storage_id"])

        # Video Transcoding
        self.add_child(transcode, ProcessExecutionFlags(
            parallel=True,  # ← Läuft PARALLEL!
            wait_for_completion=True
        ))
        self._connect_param(save_db.output["storage_id"], transcode.input["storage_id"])
        # TODO: Add is_video detection logic

        # Knowledge Graph Update
        self.add_child(update_kg, ProcessExecutionFlags(
            parallel=True,  # ← Läuft PARALLEL!
            wait_for_completion=True
        ))
        self._connect_param(save_db.output["storage_id"], update_kg.input["storage_id"])
        self._connect_param(ai_check.output["ai_title"], update_kg.input["ai_title"])
        self._connect_param(ai_check.output["ai_tags"], update_kg.input["ai_tags"])

        # ========================================
        # Gruppe 4: Update Status (Sequential)
        # ========================================
        self.add_child(update_status, ProcessExecutionFlags(
            parallel=False,
            wait_for_completion=True
        ))
        self._connect_param(save_db.output["storage_id"], update_status.input["storage_id"])

        # ========================================
        # Pipeline Outputs
        # ========================================
        self._connect_param(save_db.output["storage_id"], self.output["storage_id"])
        self._connect_param(ai_check.output["is_safe"], self.output["is_safe"])
        self._connect_param(transcode.output["hls_url"], self.output["hls_url"])
        self._connect_param(update_kg.output["embedding_id"], self.output["embedding_id"])
```

#### Schritt 3: Prozesse registrieren

Erstelle: `storage-api/app/workflows/registry.py`

```python
from swfme.registry.process_registry import process_registry
from .storage_processes import (
    ProcessSaveToDatabase,
    ProcessExtractMetadata,
    ProcessAISafetyCheck,
    ProcessTranscodeVideo,
    ProcessUpdateKnowledgeGraph,
    ProcessUpdateStatus,
    StorageUploadPipeline,
)

def register_storage_workflows():
    """Register all storage-api workflows"""

    # Atomic Processes
    process_registry.register(ProcessSaveToDatabase, "SaveToDatabase")
    process_registry.register(ProcessExtractMetadata, "ExtractMetadata")
    process_registry.register(ProcessAISafetyCheck, "AISafetyCheck")
    process_registry.register(ProcessTranscodeVideo, "TranscodeVideo")
    process_registry.register(ProcessUpdateKnowledgeGraph, "UpdateKG")
    process_registry.register(ProcessUpdateStatus, "UpdateStatus")

    # Orchestrated Workflow
    process_registry.register(StorageUploadPipeline, "StorageUpload")

    print("✅ Storage workflows registered!")
```

#### Schritt 4: In FastAPI integrieren

Update: `storage-api/app/main.py`

```python
from fastapi import FastAPI
from app.workflows.registry import register_storage_workflows
from swfme.api.routes import router as swfme_router

app = FastAPI(title="Storage API")

# Register sWFME workflows
register_storage_workflows()

# Add sWFME API endpoints
app.include_router(swfme_router, prefix="/swfme/api")

# Deine existing routes...
```

#### Schritt 5: Upload Endpoint anpassen

```python
from swfme.registry.process_registry import process_registry

@app.post("/upload")
async def upload_file(file: UploadFile, tenant_id: str):
    """Upload file and trigger processing pipeline"""

    # 1. Save file temporarily
    temp_path = await save_temp_file(file)

    # 2. Start sWFME workflow (async/background)
    pipeline = process_registry.create("StorageUpload")
    pipeline.input["file_path"].value = temp_path
    pipeline.input["tenant_id"].value = tenant_id

    # Execute in background
    asyncio.create_task(pipeline.execute())

    # 3. Return process ID for tracking
    return {
        "process_id": pipeline.id,
        "status": "processing",
        "monitor_url": f"/swfme/api/ws/monitor/{pipeline.id}"
    }
```

---

## Dashboard & Monitoring

### Orchestration Graph

Zeigt die **statische Struktur** deiner Pipeline:

```
START
  ↓
SaveToDatabase (500ms)
  ↓
ExtractMetadata (200ms)
  ↓
╔═══════════════════════════╗
║    PARALLEL GROUP         ║
╠═══════════════════════════╣
║  AISafetyCheck   (2500ms) ║
║  TranscodeVideo (15300ms) ║
║  UpdateKG        (1200ms) ║
╚═══════════════════════════╝
  ↓
UpdateStatus (100ms)
  ↓
END

Total: ~15.9s (statt 19.6s sequential!)
```

### Live Execution

Zeigt Prozesse **während der Ausführung**:

- Grau = Pending
- Blau = Running
- Grün = Completed
- Rot = Failed

Mit Execution Times in Echtzeit!

### Metrics

```
Total Executions: 156
Success Rate: 98.7%
Average Time: 16.2s

Per Process:
  SaveToDatabase:   500ms avg
  ExtractMetadata:  200ms avg
  AISafetyCheck:   2500ms avg ← Bottleneck!
  TranscodeVideo: 15300ms avg ← Läuft parallel, OK
  UpdateKG:        1200ms avg
```

---

## API Integration

### Workflow ausführen

```python
# Python Client
from swfme.registry.process_registry import process_registry

pipeline = process_registry.create("StorageUpload")
pipeline.input["file_path"].value = "/tmp/upload.jpg"
pipeline.input["tenant_id"].value = "tenant_oneal"

await pipeline.execute()

storage_id = pipeline.output["storage_id"].value
is_safe = pipeline.output["is_safe"].value
```

### REST API

```bash
curl -X POST http://localhost:8000/swfme/api/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "StorageUpload",
    "parameters": {
      "file_path": "/tmp/upload.jpg",
      "tenant_id": "tenant_oneal"
    }
  }'
```

Response:
```json
{
  "success": true,
  "process_id": "uuid-here",
  "status": "completed",
  "execution_time_ms": 15900,
  "output": {
    "storage_id": 1234,
    "is_safe": true,
    "hls_url": "https://cdn.../video.m3u8",
    "embedding_id": "emb_xxx"
  }
}
```

### WebSocket Monitoring

```javascript
const ws = new WebSocket('ws://localhost:8000/swfme/api/ws/monitor/all');

ws.onmessage = (event) => {
  const evt = JSON.parse(event.data);

  if (evt.type === 'process.started') {
    console.log(`${evt.process_name} started`);
  }

  if (evt.type === 'process.completed') {
    console.log(`${evt.process_name} completed in ${evt.execution_time}ms`);
  }
};
```

---

## Best Practices

### 1. Ein Prozess = Eine Verantwortung

```python
# ✅ GOOD: Fokussiert
class ProcessAISafetyCheck(AtomarProcess):
    """Only does AI safety check"""
    pass

# ❌ BAD: Macht zu viel
class ProcessAIStuff(AtomarProcess):
    """AI check + metadata + KG update"""  # Zu viel!
    pass
```

### 2. Parameter Connections zur Laufzeit

```python
# ✅ GOOD
def define_orchestration(self):
    self._connect_param(src.output["data"], target.input["data"])

# ❌ BAD
def define_orchestration(self):
    target.input["data"].value = src.output["data"].value  # Fehler!
```

### 3. Error Handling in Prozessen

```python
class ProcessAISafetyCheck(AtomarProcess):
    async def execute_impl(self):
        try:
            result = await ai_service.check(...)
            self.output["is_safe"].value = result.is_safe
        except AIServiceError as e:
            # Log error
            logger.error(f"AI check failed: {e}")
            # Set safe default
            self.output["is_safe"].value = False
            # Optional: Re-raise für Workflow abort
            raise
```

### 4. Wiederverwendbare Prozesse

```python
# Prozess ist generisch, wiederverwendbar
class ProcessExtractMetadata(AtomarProcess):
    """Extract metadata from ANY storage object"""
    pass

# Kann in verschiedenen Workflows verwendet werden
class StorageUploadPipeline(OrchestratedProcess):
    def define_orchestration(self):
        self.add_child(ProcessExtractMetadata())

class StorageReprocessPipeline(OrchestratedProcess):
    def define_orchestration(self):
        self.add_child(ProcessExtractMetadata())  # Gleicher Prozess!
```

### 5. Testbarkeit

```python
# Prozesse sind leicht zu testen
import pytest

@pytest.mark.asyncio
async def test_ai_safety_check():
    process = ProcessAISafetyCheck()
    process.input["storage_id"].value = 123

    await process.execute()

    assert process.output["is_safe"].value is True
    assert process.output["safety_rating"].value == "SAFE"
```

---

## Troubleshooting

### Problem: "Parameter value is None"

**Ursache:** Parameter-Connection nicht korrekt definiert.

**Lösung:**
```python
# Prüfe ob _connect_param verwendet wird
self._connect_param(source.output["data"], target.input["data"])

# NICHT direkter Zugriff
target.input["data"].value = source.output["data"].value
```

### Problem: "Parallel processes not running in parallel"

**Ursache:** Alle als `parallel=False` definiert.

**Lösung:**
```python
# Parallele Prozesse MÜSSEN parallel=True haben
self.add_child(process1, ProcessExecutionFlags(parallel=True))
self.add_child(process2, ProcessExecutionFlags(parallel=True))
```

### Problem: "WebSocket disconnects"

**Ursache:** CORS oder Netzwerk-Issue.

**Lösung:**
```python
# FastAPI CORS Config
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5177"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Problem: "Dashboard zeigt keine Workflows"

**Ursache:** Workflows nicht registriert oder Backend nicht erreichbar.

**Lösung:**
```python
# 1. Check Backend
curl http://localhost:8000/swfme/api/health

# 2. Check Workflows
curl http://localhost:8000/swfme/api/workflows

# 3. Re-register workflows
from app.workflows.registry import register_storage_workflows
register_storage_workflows()
```

---

## Zusammenfassung

### Was du bekommst:

✅ **Transparenz** - Sehe genau was in deiner Pipeline läuft
✅ **Performance** - Parallele Ausführung (AI + Transcode + KG gleichzeitig)
✅ **Monitoring** - Echtzeit-Visualisierung + Metrics
✅ **Wartbarkeit** - Jeder Schritt ist isoliert und testbar
✅ **Wiederverwendbarkeit** - Prozesse können in mehreren Workflows verwendet werden

### Nächste Schritte:

1. Demo ausführen (`python server.py` + Dashboard öffnen)
2. DataPipeline im Dashboard anschauen
3. Storage-API Prozesse erstellen (siehe oben)
4. In deine FastAPI integrieren
5. Dashboard anpassen für deine Workflows

### Support:

- **README.md** - Allgemeine Doku
- **examples/simple_workflow.py** - Vollständiges Beispiel
- **tests/** - Unit Tests als Referenz

---

**Viel Erfolg! 🚀**

Bei Fragen: Alex Popovic (@apopovic77)
