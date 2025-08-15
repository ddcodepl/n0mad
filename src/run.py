#!/usr/bin/env python
"""Entry point for running the Nomad application."""

import os
import sys

# Add project root to Python path to enable imports
sys.path.insert(0, os.path.dirname(__file__))

from entry.main import main

if __name__ == "__main__":
    main()
