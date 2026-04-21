#!/usr/bin/env python3
"""Compatibility entrypoint for the video publisher example."""

import asyncio

from video_publisher import main


if __name__ == "__main__":
    asyncio.run(main())
