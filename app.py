"""FastAPI application wired to LifecycleManager-managed dependencies."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from lifecycle_manager import LifecycleManager, ManagedDependencies


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize managed dependencies at startup and cleanly shut down on exit."""
    manager = LifecycleManager()

    # Drive startup/shutdown through LifecycleManager's async context manager.
    async with manager.lifespan() as deps:
        app.state.manager = manager
        app.state.deps = deps
        yield


def get_manager(request: Request) -> LifecycleManager:
    """Retrieve the lifecycle manager from application state."""
    manager = getattr(request.app.state, "manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return manager


def get_deps(request: Request) -> ManagedDependencies:
    """Retrieve managed dependencies from application state."""
    deps = getattr(request.app.state, "deps", None)
    if deps is None:
        raise HTTPException(status_code=503, detail="Dependencies not initialized")
    return deps


app = FastAPI(title="Dependency Lifecycle API", lifespan=lifespan)


@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request) -> dict[str, Any]:
    """Fetch order details, checking cache before returning a database-backed result."""
    deps = get_deps(request)

    cache_key = f"order:{order_id}"
    cached = await deps.cache.get(cache_key)
    if cached:
        return {"order_id": order_id, "data": cached, "cached": True}

    rows = await deps.database.query(
        "SELECT * FROM orders WHERE id = :id", {"id": order_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Order not found")

    order = rows[0]
    await deps.cache.set(cache_key, order, ttl=60)

    return {"order_id": order_id, "data": order, "cached": False}


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Return aggregated health status from LifecycleManager."""
    manager = get_manager(request)
    return await manager.health_check()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000)
