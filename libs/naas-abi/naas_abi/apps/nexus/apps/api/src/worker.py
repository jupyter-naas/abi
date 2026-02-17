"""
NEXUS API - Cloudflare Workers Entry Point

This module adapts the FastAPI application to run on Cloudflare Workers
using their Python runtime and ASGI support.
"""

import asgi
from workers import WorkerEntrypoint

# Import the FastAPI app
from app.main import app


class Default(WorkerEntrypoint):
    """
    Cloudflare Worker entry point for the NEXUS API.

    This class handles incoming requests and routes them through
    the FastAPI application using the ASGI protocol.
    """

    async def fetch(self, request):
        """
        Handle incoming HTTP requests.

        Args:
            request: The incoming Cloudflare request object

        Returns:
            Response object to send back to the client
        """
        # Pass environment bindings to the app
        # These can be accessed via request.state in FastAPI
        return await asgi.fetch(app, request, self.env)


# For local development with wrangler dev
def on_fetch(request, env, ctx):
    """Alternative entry point for wrangler dev."""
    import asyncio

    async def run():
        worker = Default()
        worker.env = env
        worker.ctx = ctx
        return await worker.fetch(request)

    return asyncio.get_event_loop().run_until_complete(run())
