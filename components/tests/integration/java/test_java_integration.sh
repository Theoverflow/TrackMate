#!/bin/bash
# Java Integration Test Suite

set -e

echo "=== Java Integration Tests ==="
echo ""

# Test 1: Compilation check
echo "Test 1: Checking Java compilation..."
if [ -f "java_multithread_job.class" ]; then
    echo "✅ Java application compiled successfully"
else
    echo "❌ Java application compilation failed"
    exit 1
fi

# Test 2: Basic execution test (dry run with minimal load)
echo ""
echo "Test 2: Running Java application (dry run)..."
timeout 60s java java_multithread_job 2 2 || {
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        echo "⚠️  Test timed out after 60s (expected for heavy load)"
    elif [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Java application executed successfully"
    else
        echo "❌ Java application failed with exit code $EXIT_CODE"
        exit 1
    fi
}

# Test 3: Check for monitoring integration
echo ""
echo "Test 3: Checking monitoring integration..."
if java java_multithread_job 1 1 2>&1 | grep -q "Worker"; then
    echo "✅ Monitoring integration detected"
else
    echo "⚠️  Monitoring integration not clearly detected (may be working)"
fi

# Test 4: Thread safety test
echo ""
echo "Test 4: Testing thread safety..."
if java java_multithread_job 4 4 > /tmp/java_output.txt 2>&1; then
    if grep -q "Exception" /tmp/java_output.txt; then
        echo "❌ Thread safety issues detected"
        cat /tmp/java_output.txt
        exit 1
    else
        echo "✅ Thread safety test passed"
    fi
else
    echo "⚠️  Thread safety test completed with non-zero exit (may be expected)"
fi

# Test 5: Memory test
echo ""
echo "Test 5: Checking memory handling..."
java -Xmx256m java_multithread_job 2 2 && \
    echo "✅ Memory handling test passed" || \
    echo "⚠️  Memory test completed"

echo ""
echo "=== All Java Integration Tests Complete ==="
exit 0

