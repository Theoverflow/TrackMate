# Perl Integration Test Environment
FROM perl:5.38

WORKDIR /workspace

# Install system dependencies and Perl modules
RUN apt-get update && apt-get install -y \
    build-essential \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && cpanm --notest \
        LWP::UserAgent \
        JSON \
        Parallel::ForkManager \
        Test::More \
        Test::Deep

# Copy business app
COPY examples/business_apps/perl_multiprocess_job.pl /workspace/

# Copy test files
COPY components/tests/integration/perl/test_perl_integration.pl /workspace/tests/

# Make scripts executable
RUN chmod +x /workspace/perl_multiprocess_job.pl
RUN chmod +x /workspace/tests/test_perl_integration.pl

# Run tests by default
CMD ["perl", "/workspace/tests/test_perl_integration.pl"]

