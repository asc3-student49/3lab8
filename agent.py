"""
Agent with Managed Dependencies
Demonstrates agent using lifecycle-managed dependencies
"""

import os
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from lifecycle_manager import ManagedDependencies
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class OrderLookupResult(BaseModel):
    """Order lookup result."""

    order_id: str
    status: str
    total: float
    cached: bool


# Create agent with managed dependencies type
service_agent = Agent(
    os.getenv("AI_MODEL", "openai:gpt-5.4-mini"),
    deps_type=ManagedDependencies,
    system_prompt="""You are a customer service agent.
    
    Help customers with:
    - Order lookups
    - Status updates
    - General inquiries
    
    Use the available tools to access order data efficiently.""",
)


@service_agent.tool
async def lookup_order(
    ctx: RunContext[ManagedDependencies], order_id: str
) -> OrderLookupResult:
    """
    Lookup order by ID using cache and database.

    Implements cache-aside pattern for performance.
    """
    logger.info(f"Looking up order: {order_id}")

    # Try cache first
    cache_key = f"order:{order_id}"

    if ctx.deps.settings.enable_caching:
        cached = await ctx.deps.cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for order {order_id}")
            return OrderLookupResult(**cached, cached=True)

    # Cache miss - query database
    logger.info(f"Cache MISS for order {order_id}, querying database")
    result = await ctx.deps.database.query(
        "SELECT * FROM orders WHERE id = :id", {"id": order_id}
    )

    if not result:
        raise ValueError(f"Order {order_id} not found")

    # Build result
    order = OrderLookupResult(
        order_id=order_id, status="shipped", total=99.99, cached=False
    )

    # Cache result
    if ctx.deps.settings.enable_caching:
        await ctx.deps.cache.set(cache_key, order.model_dump(exclude={"cached"}))
        logger.info(f"Cached order {order_id}")

    return order


@service_agent.tool
async def get_external_data(ctx: RunContext[ManagedDependencies], url: str) -> dict:
    """
    Fetch data from external API using managed HTTP client.

    Uses connection pooling for efficiency.
    """
    logger.info(f"Fetching external data from {url}")

    try:
        response = await ctx.deps.http.get(url)
        return {
            "status": response.status_code,
            "data": response.text[:200],  # First 200 chars
        }
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return {"status": "error", "error": str(e)}


async def process_query(query: str, deps: ManagedDependencies) -> str:
    """
    Process customer query using managed dependencies.

    Args:
        query: Customer query
        deps: Managed dependencies container

    Returns:
        Agent response
    """
    logger.info(f"Processing query: {query}")

    result = await service_agent.run(query, deps=deps)

    logger.info("Query processed successfully")
    return result.output


# Example usage
async def main():
    """Example of using agent with lifecycle management."""
    from lifecycle_manager import LifecycleManager

    manager = LifecycleManager()

    async with manager.lifespan() as deps:
        logger.info("Agent service ready")

        # Process queries
        queries = [
            "What's the status of order ORD-12345?",
            "Look up order ORD-12345 again",  # Should hit cache
        ]

        for i, query in enumerate(queries, 1):
            print(f"\n{'=' * 60}")
            print(f"Query {i}: {query}")
            print("=" * 60)

            response = await process_query(query, deps)
            print(f"Response: {response}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
