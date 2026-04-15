import os
import sys

# Make the src/ package importable when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rss_generator.main import run  # noqa: E402

if __name__ == "__main__":
    run()
