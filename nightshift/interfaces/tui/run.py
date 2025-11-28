"""
TUI Entry Point
Async runner for the TUI application
"""
import asyncio
from .app import create_app


def run():
    """Run the TUI application"""
    app = create_app()
    asyncio.run(app.run_async())


if __name__ == "__main__":
    run()
