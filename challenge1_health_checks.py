"""
Challenge 1: Health Checks
Comprehensive health checks for all dependencies
"""

from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
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
        # YOUR CODE HERE

    async def check_cache(self) -> HealthCheckResult:
        """
        Check cache health.

        Performs a ping-like operation (set/get).

        Returns:
            Health check result
        """
        # YOUR CODE HERE

    async def check_http_client(self) -> HealthCheckResult:
        """
        Check HTTP client health.

        Verifies client is initialized and can make requests.

        Returns:
            Health check result
        """
        import time

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
        # YOUR CODE HERE

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
        # YOUR CODE HERE


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
