"""
Challenge 1: Health Checks
Comprehensive health checks for all dependencies
"""

from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging
import time
from lifecycle_manager import ManagedDependencies

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    healthy: bool
    message: str
    latency_ms: float
    timestamp: datetime


class HealthChecker:
    """
    Comprehensive health checker for all dependencies.

    Provides detailed status for monitoring and alerting.
    """

    def __init__(self, dependencies: ManagedDependencies):
        """
        Initialize health checker.

        Args:
            dependencies: Managed dependencies to check
        """
        self.dependencies = dependencies

    async def check_database(self) -> HealthCheckResult:
        """
        Check database health.

        Performs a simple query to verify connectivity.

        Returns:
            Health check result
        """
        start = time.time()

        try:
            await self.dependencies.database.query("SELECT 1")
            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                healthy=True,
                message="Database healthy",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Database health check failed: {e}")

            return HealthCheckResult(
                healthy=False,
                message=f"Database error: {str(e)[:100]}",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

    async def check_cache(self) -> HealthCheckResult:
        """
        Check cache health.

        Performs a ping-like operation (set/get).

        Returns:
            Health check result
        """
        start = time.time()
        sentinel_key = "_health_check_sentinel"
        sentinel_value = f"ok-{int(start * 1000)}"

        try:
            await self.dependencies.cache.set(sentinel_key, sentinel_value, ttl=5)
            round_trip = await self.dependencies.cache.get(sentinel_key)
            latency = (time.time() - start) * 1000

            if round_trip != sentinel_value:
                return HealthCheckResult(
                    healthy=False,
                    message=(
                        "Cache round-trip mismatch: "
                        f"expected={sentinel_value}, got={round_trip}"
                    )[:100],
                    latency_ms=round(latency, 2),
                    timestamp=datetime.now(),
                )

            return HealthCheckResult(
                healthy=True,
                message="Cache healthy",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"Cache health check failed: {e}")

            return HealthCheckResult(
                healthy=False,
                message=f"Cache error: {str(e)[:100]}",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

    async def check_http_client(self) -> HealthCheckResult:
        """
        Check HTTP client health.

        Verifies client is initialized and can make requests.

        Returns:
            Health check result
        """
        start = time.time()

        try:
            # Check client is initialized
            if not self.dependencies.http._initialized:
                raise RuntimeError("HTTP client not initialized")

            # Optionally test with actual request
            # response = await self.dependencies.http.get('https://httpbin.org/status/200')
            # if response.status_code != 200:
            #     raise ValueError(f"HTTP check failed: status {response.status_code}")

            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                healthy=True,
                message="HTTP client healthy",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"HTTP client health check failed: {e}")

            return HealthCheckResult(
                healthy=False,
                message=f"HTTP client error: {str(e)[:100]}",
                latency_ms=round(latency, 2),
                timestamp=datetime.now(),
            )

    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Perform all health checks.

        Returns:
            Dictionary mapping dependency name to health check result
        """
        database_result, cache_result, http_result = await asyncio.gather(
            self.check_database(),
            self.check_cache(),
            self.check_http_client(),
        )

        results = {
            "database": database_result,
            "cache": cache_result,
            "http": http_result,
        }

        for name, result in results.items():
            logger.info(
                "Health check %s: healthy=%s latency_ms=%.2f message=%s",
                name,
                result.healthy,
                result.latency_ms,
                result.message,
            )

        return results

    def get_overall_status(self, results: Dict[str, HealthCheckResult]) -> str:
        """
        Determine overall health status.

        Args:
            results: Health check results

        Returns:
            'healthy', 'degraded', or 'unhealthy'
        """
        healthy_count = sum(1 for r in results.values() if r.healthy)
        total_count = len(results)

        if healthy_count == total_count:
            return "healthy"
        elif healthy_count > 0:
            return "degraded"
        else:
            return "unhealthy"

    async def get_health_report(self) -> Dict[str, Any]:
        """
        Get comprehensive health report.

        Returns:
            Health report dictionary
        """
        results = await self.check_all()
        status = self.get_overall_status(results)

        checks = {
            name: {
                "healthy": result.healthy,
                "message": result.message,
                "latency_ms": result.latency_ms,
                "timestamp": result.timestamp.isoformat(),
            }
            for name, result in results.items()
        }

        total_checks = len(results)
        healthy_checks = sum(1 for result in results.values() if result.healthy)
        unhealthy_checks = total_checks - healthy_checks

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "checks": checks,
            "summary": {
                "total": total_checks,
                "healthy": healthy_checks,
                "unhealthy": unhealthy_checks,
            },
        }


# Example usage with FastAPI
async def health_endpoint_example():
    """Example FastAPI health endpoint."""
    from fastapi import FastAPI
    from lifecycle_manager import LifecycleManager

    app = FastAPI()
    manager = LifecycleManager()

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        if not manager.is_initialized():
            return {"status": "not_initialized", "healthy": False}

        checker = HealthChecker(manager.dependencies)
        report = await checker.get_health_report()

        # Return appropriate status code
        status_code = 200 if report["status"] == "healthy" else 503

        return report

    @app.get("/health/database")
    async def health_database():
        """Database-specific health check."""
        checker = HealthChecker(manager.dependencies)
        result = await checker.check_database()

        return {
            "healthy": result.healthy,
            "message": result.message,
            "latency_ms": result.latency_ms,
            "timestamp": result.timestamp.isoformat(),
        }


# Example usage
async def main():
    """Example health check usage."""
    from lifecycle_manager import LifecycleManager
    import json

    manager = LifecycleManager()

    async with manager.lifespan() as deps:
        checker = HealthChecker(deps)

        # Get full health report
        report = await checker.get_health_report()

        print("\n" + "=" * 60)
        print("HEALTH CHECK REPORT")
        print("=" * 60)
        print(json.dumps(report, indent=2))
        print("=" * 60)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
