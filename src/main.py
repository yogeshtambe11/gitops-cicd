from datetime import datetime, timezone
from fastapi import FastAPI

app = FastAPI(
    title="DevSecOps Sample Service",
    description="Python microservice for OpenShift Tekton CI/CD and Argo CD GitOps",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "Hello from OpenShift GitOps & Tekton CI/CD!",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/healthz")
def health_check():
    return {"status": "UP"}
