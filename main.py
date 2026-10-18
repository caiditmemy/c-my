from fastapi import FastAPI
from routers import auth, api

app = FastAPI(
    title="Guild RESTful API - Bài Thực Hành Số 2",
    description="Hệ thống xác thực danh tính với Router, Dependency Middleware và JWT"
)

# Gắn các tuyến đường Router
app.include_router(auth.router)
app.include_router(api.router)

if __name__ == "__main__":
    import uvicorn
    # Kích hoạt máy chủ Uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)