from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

@app.get("/")
def home():
return {"status": "ETERNA backend alive"}

if __name__ == "__main__":
port = int(os.environ.get("PORT", 10000))
uvicorn.run(app, host="0.0.0.0", port=port)
