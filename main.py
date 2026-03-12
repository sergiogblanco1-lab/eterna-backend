from fastapi import FastAPI

app = FastAPI(title="ETERNA API")

@app.get("/")
def home():
return {"message": "ETERNA backend running"}
