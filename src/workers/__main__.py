"""Worker module entry point."""
import asyncio

from src.workers.runner import main

if __name__ == "__main__":
    asyncio.run(main())
