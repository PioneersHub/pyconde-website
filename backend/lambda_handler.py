"""AWS Lambda handler for PyConDE contact form API."""

import sys
import os
import glob

# Add SAM dependencies directory to Python path if it exists
deps_dirs = glob.glob('/var/task/.aws-sam/deps/*/') + glob.glob('.aws-sam/deps/*/')
for deps_dir in deps_dirs:
    if os.path.isdir(deps_dir) and deps_dir not in sys.path:
        sys.path.insert(0, deps_dir)

from main import app
from mangum import Mangum

# Create Lambda handler
# Mangum wraps the FastAPI ASGI app to work with AWS Lambda's event format
handler = Mangum(app, lifespan="off")
