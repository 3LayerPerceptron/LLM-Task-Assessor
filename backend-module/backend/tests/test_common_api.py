from backend.src.config import settings

from httpx import AsyncClient


async def test_healthy(api: AsyncClient) -> None:
    response = await api.get("/healthy")
    assert response.status_code == 200
    assert response.json() == True


async def test_cors_headers(api: AsyncClient) -> None:
    response = await api.options("/health", headers={
        "Origin": settings.CORS_ORIGINS[0],
        "Access-Control-Request-Method": "GET"
    })
    assert response.status_code == 200
    assert response.headers.get(
        "access-control-allow-origin") == settings.CORS_ORIGINS[0]
    assert response.headers.get(
        "access-control-allow-methods") == "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
    assert response.headers.get("access-control-allow-credentials") == "true"
