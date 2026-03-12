services:
  - type: web
    name: eterna-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    plan: free
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: eterna-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: eterna-redis
          property: connectionString

databases:
  - name: eterna-db
    plan: free

  - name: eterna-redis
    ipAllowList: []
