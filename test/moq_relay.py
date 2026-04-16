#!/usr/bin/env python3
"""
MOQ Relay Server for Testing
Standalone relay using webui's moq implementation
"""

import asyncio
import sys
import os
from pathlib import Path

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.relay.relay import MOQRelay


async def main():
    """Start MOQ Relay Server"""
    print("=" * 70)
    print("MOQ Relay Server (Test)")
    print("=" * 70)

    relay = MOQRelay("localhost", 9004)  # Use port 9004 for testing

    print("\n[1] Starting relay on localhost:9004...")
    await relay.start()
    print("[✓] Relay started")

    print("\n[2] Waiting for connections...")
    print("    Press Ctrl+C to stop\n")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass

    print("\n[3] Stopping relay...")
    await relay.stop()
    print("[✓] Relay stopped")


if __name__ == "__main__":
    asyncio.run(main())
