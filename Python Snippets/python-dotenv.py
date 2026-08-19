#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Load .env from scene_generator directory when running locally
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed; use system/env vars (Ex: in container)

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)