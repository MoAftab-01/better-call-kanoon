from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def welcome() -> dict[str, str]:
    return {"message": "Welcome to Better Call Kanoon"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "better-call-kanoon"}
