# Java Integration Test Environment
FROM eclipse-temurin:17-jdk

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    maven \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy business app
COPY examples/business_apps/java_multithread_job.java /workspace/

# Copy test files
COPY components/tests/integration/java/test_java_integration.sh /workspace/tests/
COPY components/tests/integration/java/pom.xml /workspace/

# Build Java application
RUN javac java_multithread_job.java

# Install JUnit for testing
RUN mvn dependency:resolve

# Make test script executable
RUN chmod +x /workspace/tests/test_java_integration.sh

# Run tests by default
CMD ["/workspace/tests/test_java_integration.sh"]

