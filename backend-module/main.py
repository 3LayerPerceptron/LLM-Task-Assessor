from backend.src import app, settings

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.UVICORN_PORT,
        reload=settings.UVICORN_RELOAD
    )
