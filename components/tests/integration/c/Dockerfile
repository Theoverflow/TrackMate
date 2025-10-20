# C Integration Test Environment
FROM gcc:13

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    libcurl4-openssl-dev \
    libjson-c-dev \
    valgrind \
    gdb \
    && rm -rf /var/lib/apt/lists/*

# Copy business app
COPY examples/business_apps/c_multiprocess_job.c /workspace/

# Copy test files
COPY components/tests/integration/c/test_c_integration.sh /workspace/tests/
COPY components/tests/integration/c/CMakeLists.txt /workspace/

# Build C application
RUN gcc -o c_multiprocess_job c_multiprocess_job.c -lcurl -pthread

# Make test script executable
RUN chmod +x /workspace/tests/test_c_integration.sh

# Run tests by default
CMD ["/workspace/tests/test_c_integration.sh"]

