"""AWS Lambda handler for PyConDE contact form API.

Dependencies sit at the package root because `sam deploy` ships the
`sam build` output (see samconfig.toml), so no sys.path setup is needed.
"""

from main import app
from mangum import Mangum

# Create Lambda handler
# Mangum wraps the FastAPI ASGI app to work with AWS Lambda's event format
handler = Mangum(app, lifespan="off")
