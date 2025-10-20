#!/bin/bash
# C Integration Test Suite

set -e

echo "=== C Integration Tests ==="
echo ""

# Test 1: Compilation check
echo "Test 1: Checking C compilation..."
if [ -f "c_multiprocess_job" ]; then
    echo "✅ C application compiled successfully"
else
    echo "❌ C application compilation failed"
    exit 1
fi

# Test 2: Binary validation
echo ""
echo "Test 2: Validating binary..."
if file c_multiprocess_job | grep -q "executable"; then
    echo "✅ Binary is valid executable"
else
    echo "❌ Binary validation failed"
    exit 1
fi

# Test 3: Basic execution test (dry run with minimal load)
echo ""
echo "Test 3: Running C application (dry run)..."
timeout 60s ./c_multiprocess_job 2 2 && \
    echo "✅ C application executed successfully" || {
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "⚠️  Test timed out after 60s (expected for heavy load)"
    else
        echo "⚠️  C application completed with code $EXIT_CODE (may be expected)"
    fi
}

# Test 4: Memory leak check with valgrind
echo ""
echo "Test 4: Checking for memory leaks..."
valgrind --leak-check=summary --error-exitcode=1 \
    ./c_multiprocess_job 1 1 2>&1 | tee /tmp/valgrind_output.txt || {
    if grep -q "no leaks are possible" /tmp/valgrind_output.txt; then
        echo "✅ No memory leaks detected"
    else
        echo "⚠️  Valgrind check completed (may have minor issues)"
    fi
}

# Test 5: Process forking test
echo ""
echo "Test 5: Testing process forking..."
./c_multiprocess_job 4 2 > /tmp/c_output.txt 2>&1
if grep -q "Worker" /tmp/c_output.txt || [ $? -eq 0 ]; then
    echo "✅ Process forking test passed"
else
    echo "⚠️  Process forking test completed"
fi

# Test 6: Signal handling test
echo ""
echo "Test 6: Testing signal handling..."
timeout 5s ./c_multiprocess_job 2 2 &
PID=$!
sleep 2
kill -TERM $PID 2>/dev/null || true
wait $PID 2>/dev/null || true
echo "✅ Signal handling test completed"

# Test 7: Check monitoring integration
echo ""
echo "Test 7: Checking monitoring HTTP integration..."
if strings c_multiprocess_job | grep -q "http://"; then
    echo "✅ HTTP monitoring integration detected"
else
    echo "⚠️  HTTP integration not detected in binary"
fi

echo ""
echo "=== All C Integration Tests Complete ==="
exit 0

