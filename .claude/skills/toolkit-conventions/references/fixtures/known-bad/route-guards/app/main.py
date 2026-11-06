from fastapi import FastAPI

from .api import orders

app = FastAPI()
app.include_router(orders.router)


@app.get("/health")
def health():
    return {"ok": True}
