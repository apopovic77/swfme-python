"""
FastAPI Application for sWFME

Main application setup with CORS, middleware, and route registration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from swfme.api.routes import router


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="sWFME API",
        description="Workflow Management Engine - Process-Oriented Programming Framework",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware (allow all origins for development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production: specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(router)

    # Root endpoint
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint with API information"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>sWFME API</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background: #f5f5f5;
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 { color: #2c3e50; margin-top: 0; }
                h2 { color: #34495e; margin-top: 30px; }
                a {
                    color: #3498db;
                    text-decoration: none;
                }
                a:hover { text-decoration: underline; }
                .endpoint {
                    background: #ecf0f1;
                    padding: 10px;
                    margin: 10px 0;
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                }
                .badge {
                    display: inline-block;
                    padding: 2px 8px;
                    background: #3498db;
                    color: white;
                    border-radius: 3px;
                    font-size: 12px;
                    margin-right: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 sWFME API</h1>
                <p><strong>Process-Oriented Programming Framework for Python</strong></p>
                <p>Version 0.1.0</p>

                <h2>📚 Documentation</h2>
                <ul>
                    <li><a href="/docs" target="_blank">OpenAPI Documentation (Swagger UI)</a></li>
                    <li><a href="/redoc" target="_blank">ReDoc Documentation</a></li>
                    <li><a href="https://github.com/apopovic77/swfme-python" target="_blank">GitHub Repository</a></li>
                </ul>

                <h2>🎯 Quick Start</h2>

                <h3>List Workflows</h3>
                <div class="endpoint">
                    <span class="badge">GET</span> /api/workflows
                </div>

                <h3>Execute Workflow</h3>
                <div class="endpoint">
                    <span class="badge">POST</span> /api/workflows/execute
                </div>

                <h3>Get Metrics</h3>
                <div class="endpoint">
                    <span class="badge">GET</span> /api/metrics/summary
                </div>

                <h3>Real-Time Monitoring (WebSocket)</h3>
                <div class="endpoint">
                    <span class="badge">WS</span> /api/ws/monitor/all
                </div>

                <h2>🔥 Example</h2>
                <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto;">
# Execute a workflow
curl -X POST http://localhost:8000/api/workflows/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "workflow_name": "DataPipeline",
    "parameters": {
      "filename": "data.csv"
    }
  }'
                </pre>

                <h2>📊 Health Check</h2>
                <p><a href="/api/health">Check API Health</a></p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #ecf0f1;">
                <p style="text-align: center; color: #95a5a6; font-size: 14px;">
                    Built with ❤️ by Alex Popovic (Arkturian) | 2025
                </p>
            </div>
        </body>
        </html>
        """

    return app


# Create app instance
app = create_app()
