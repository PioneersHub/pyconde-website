"""AWS Lambda handler for PyConDE contact form API."""

# CRITICAL: Add SAM dependencies directory to Python path BEFORE any imports
# This must be the very first code that executes
import sys
import os

# Check common SAM dependency locations
deps_paths = [
    '/var/task/.aws-sam/deps',  # Lambda runtime location (non-container builds)
    '/var/task/.aws-sam/cache',  # Lambda runtime location (container builds)
    '.aws-sam/deps',  # Local testing location (non-container)
    '.aws-sam/cache',  # Local testing location (container)
]

for deps_base in deps_paths:
    if os.path.exists(deps_base) and os.path.isdir(deps_base):
        # Add all subdirectories (SAM creates UUID-named subdirs)
        for item in os.listdir(deps_base):
            deps_dir = os.path.join(deps_base, item)
            if os.path.isdir(deps_dir) and deps_dir not in sys.path:
                sys.path.insert(0, deps_dir)
                break  # Only need one deps directory

# Now safe to import dependencies
from main import app
from mangum import Mangum

# Create Lambda handler
# Mangum wraps the FastAPI ASGI app to work with AWS Lambda's event format
handler = Mangum(app, lifespan="off")
