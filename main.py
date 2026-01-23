#!/usr/bin/env python3
import sys

# Try to import from installed package
try:
    from ytknow.comments import app
except ImportError:
    # If running from source without install
    sys.path.append("src")
    from ytknow.comments import app

if __name__ == "__main__":
    app()
