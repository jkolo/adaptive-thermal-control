#!/usr/bin/env bash
#
# Test runner script for Adaptive Thermal Control
#
# Usage:
#   ./run_tests.sh                    # Run all tests
#   ./run_tests.sh tests/test_mpc*    # Run specific test file(s)
#   ./run_tests.sh -v                 # Run with verbose output
#   ./run_tests.sh -k test_name       # Run tests matching pattern
#

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to project directory
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found at .venv/"
    echo "Please create it first with: python -m venv .venv"
    exit 1
fi

# Set PYTHONPATH to include project root
export PYTHONPATH="."

# Run pytest with all arguments passed through
pytest "$@"

# Capture exit code
EXIT_CODE=$?

# Deactivate virtual environment
deactivate

# Exit with pytest's exit code
exit $EXIT_CODE
