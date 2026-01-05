#!/bin/bash

# Add src directory to PYTHONPATH for proper package imports
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Start uvicorn with the application factory
exec uvicorn src.dbrx_api.main:create_app --host 0.0.0.0 --port 8000 --factory
