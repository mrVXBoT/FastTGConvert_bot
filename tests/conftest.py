import os

# Ensure PROXY_ENCRYPTION_KEY is populated during unit testing
os.environ["PROXY_ENCRYPTION_KEY"] = "TEST_SUITE_PROXY_ENCRYPTION_KEY_2026"
