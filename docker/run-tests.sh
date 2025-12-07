#!/bin/bash
# Run MCP Server tests in Docker
# Usage: ./run-tests.sh [pytest-args]
# Examples:
#   ./run-tests.sh                    # Run all tests
#   ./run-tests.sh -m unit            # Run unit tests only
#   ./run-tests.sh -m integration     # Run integration tests only
#   ./run-tests.sh -k "test_crypto"   # Run tests matching pattern
#   ./run-tests.sh --lf               # Run last failed tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create reports directory
mkdir -p reports reports/tmp

# Build image
docker-compose -f docker-compose.test.yml build

# Start Redis and HTTP server containers
docker-compose -f docker-compose.test.yml up -d redis-test mcp-test

echo "Waiting for MCP HTTP server to become healthy..."
set +e
READY=0
for i in {1..30}; do
    docker-compose -f docker-compose.test.yml exec -T mcp-test curl -sf http://localhost:8000/health >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        READY=1
        break
    fi
    sleep 2
done
set -e

if [ $READY -ne 1 ]; then
    echo "MCP HTTP server failed to become healthy within timeout."
    docker-compose -f docker-compose.test.yml logs mcp-test
    docker-compose -f docker-compose.test.yml down
    exit 1
fi

# Run pytest in dedicated runner container (talks to live HTTP server)
set +e
docker-compose -f docker-compose.test.yml run --rm mcp-test-runner "$@"
EXIT_CODE=$?
set -e

# Cleanup services
docker-compose -f docker-compose.test.yml down

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "Tests passed! Coverage report available at: reports/index.html"
else
    echo "Tests failed with exit code: $EXIT_CODE"
fi

exit $EXIT_CODE
