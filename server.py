#!/usr/bin/env python3
"""
sWFME Development Server

Launches the FastAPI server with demo workflows registered.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import app
from swfme.api.app import app

# Import and register demo workflows
from examples.simple_workflow import (
    DataProcessingPipeline,
    ProcessLoadData,
    ProcessTransformData,
    ProcessValidateData,
    ProcessAnalyzeData,
    ProcessSaveResult
)
from examples.math_workflow import MathPipeline
from swfme.registry.process_registry import process_registry


def register_demo_workflows():
    """Register demo workflows for testing"""
    print("📦 Registering demo workflows...")

    # Register orchestrated workflow
    process_registry.register(DataProcessingPipeline, "DataPipeline")

    # Register atomic processes
    process_registry.register(ProcessLoadData, "LoadData")
    process_registry.register(ProcessTransformData, "TransformData")
    process_registry.register(ProcessValidateData, "ValidateData")
    process_registry.register(ProcessAnalyzeData, "AnalyzeData")
    process_registry.register(ProcessSaveResult, "SaveResult")
    process_registry.register(MathPipeline, "MathPipeline")

    registered = process_registry.list_processes()
    print(f"   ✓ Registered {len(registered)} processes:")
    for p in registered:
        print(f"      - {p['name']} ({p['type']})")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))

    print("=" * 70)
    print("🚀 sWFME Development Server")
    print("=" * 70)

    # Register workflows
    register_demo_workflows()

    print("\n" + "=" * 70)
    print(f"🌐 Starting FastAPI server on port {port}...")
    print("=" * 70)
    print("\n📍 API Documentation:")
    print(f"   • Swagger UI:  http://localhost:{port}/docs")
    print(f"   • ReDoc:       http://localhost:{port}/redoc")
    print(f"   • Health:      http://localhost:{port}/api/health")
    print("\n📡 WebSocket:")
    print(f"   • Monitor All: ws://localhost:{port}/api/ws/monitor/all")
    print("\n" + "=" * 70)
    print()

    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
        # Note: reload=True requires import string format
        # Use: uvicorn server:app --reload for development
    )
