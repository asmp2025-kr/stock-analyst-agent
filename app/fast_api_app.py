# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
from collections.abc import AsyncIterator

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.reasoning_engine_adapter import (
    attach_reasoning_engine_routes,
)
from app.app_utils.telemetry import (
    setup_agent_engine_telemetry,
    setup_telemetry,
)
from app.app_utils.typing import Feedback
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import logging
# Configure standard python logging
logging.basicConfig(level=logging.INFO)

load_dotenv()
setup_telemetry()
# Must run before get_fast_api_app to set the tracer provider resource.
setup_agent_engine_telemetry()

class LocalLoggerWrapper:
    def log_struct(self, data: dict, severity: str = "INFO"):
        import json
        level = getattr(logging, severity.upper(), logging.INFO)
        logging.log(level, f"Feedback structure: {json.dumps(data)}")
    def info(self, msg, *args, **kwargs):
        logging.info(msg, *args, **kwargs)
    def error(self, msg, *args, **kwargs):
        logging.error(msg, *args, **kwargs)

try:
    _, project_id = google.auth.default()
    logging_client = google_cloud_logging.Client()
    cloud_logger = logging_client.logger(__name__)
    class CloudLoggerWrapper:
        def __init__(self, cl):
            self.cl = cl
        def log_struct(self, data: dict, severity: str = "INFO"):
            self.cl.log_struct(data, severity=severity)
        def info(self, msg, *args, **kwargs):
            self.cl.log_text(msg, severity="INFO")
        def error(self, msg, *args, **kwargs):
            self.cl.log_text(msg, severity="ERROR")
    logger = CloudLoggerWrapper(cloud_logger)
except Exception as e:
    logger = LocalLoggerWrapper()
    logging.warning(
        f"Google Cloud credentials not found or error initializing Cloud Logging ({e}). "
        "Falling back to local logging."
    )
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runner for the A2A path, sharing the same session/artifact services as the
    # adk_api and reasoning_engine paths (see services.py). Imported here so the
    # agent is built after env/telemetry setup.
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    # Shared by the A2A path and the reasoning_engine adapter routes.
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "stock-analyst-agent"
app.description = "API for interacting with the Agent stock-analyst-agent"


# Proxy routes so the Vertex AI Console Playground (reasoning_engine SDK) can
# talk to this agent alongside the native adk_api routes.
attach_reasoning_engine_routes(app)


# Serve custom frontend dashboard at /dashboard
@app.get("/dashboard", response_class=HTMLResponse)
def read_dashboard():
    return FileResponse(os.path.join(AGENT_DIR, "frontend", "index.html"))


# Mount frontend directory for static assets
app.mount(
    "/frontend",
    StaticFiles(directory=os.path.join(AGENT_DIR, "frontend")),
    name="frontend",
)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
