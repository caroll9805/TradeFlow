# Import connectors so they self-register.
from app.services.market_data.connectors import file_import, http_json, supplier_submission  # noqa: F401
