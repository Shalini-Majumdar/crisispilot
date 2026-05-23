from fastapi import FastAPI

app = FastAPI(title="CrisisPilot")

@app.get("/api/health")
def health():
    return {
        "status": "healthy"
    }