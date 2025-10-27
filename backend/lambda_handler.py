"""AWS Lambda handler for PyConDE contact form API."""

from main import app
from mangum import Mangum

# Create Lambda handler
# Mangum wraps the FastAPI ASGI app to work with AWS Lambda's event format
handler = Mangum(app, lifespan="off")
