#!/bin/bash
#
# Build script for all business applications
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "Building Business Applications"
echo "======================================================================"
echo ""

# Python - no build needed
echo "[1/4] Python: No compilation needed ✓"
chmod +x python_multiprocess_job.py
echo ""

# Java - compile if Java is available
echo "[2/4] Java: Compiling..."
if command -v javac &> /dev/null; then
    # Check for gson
    if [ ! -f "gson-2.8.9.jar" ]; then
        echo "  Downloading gson..."
        curl -s -L -o gson-2.8.9.jar \
            https://repo1.maven.org/maven2/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar
    fi
    
    javac -cp gson-2.8.9.jar java_multithread_job.java
    echo "  ✓ Java compiled successfully"
else
    echo "  ⚠ Java not found, skipping"
fi
echo ""

# C - compile if gcc is available
echo "[3/4] C: Compiling..."
if command -v gcc &> /dev/null; then
    gcc -o c_multiprocess_job c_multiprocess_job.c \
        -lcurl -lssl -lcrypto -lpthread 2>&1
    
    if [ $? -eq 0 ]; then
        echo "  ✓ C compiled successfully"
    else
        echo "  ⚠ C compilation failed (missing libraries?)"
        echo "    Install: sudo apt-get install libcurl4-openssl-dev libssl-dev"
        echo "    or macOS: brew install curl openssl"
    fi
else
    echo "  ⚠ GCC not found, skipping"
fi
echo ""

# Perl - check dependencies
echo "[4/4] Perl: Checking dependencies..."
chmod +x perl_multiprocess_job.pl

if command -v perl &> /dev/null; then
    # Check required modules
    perl -e 'use Parallel::ForkManager' 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "  ✓ Perl dependencies OK"
    else
        echo "  ⚠ Missing Perl modules"
        echo "    Install: cpanm Parallel::ForkManager LWP::UserAgent JSON"
    fi
else
    echo "  ⚠ Perl not found, skipping"
fi
echo ""

echo "======================================================================"
echo "Build Complete!"
echo "======================================================================"
echo ""
echo "Run applications:"
echo "  Python: python python_multiprocess_job.py --num-subjobs 20"
echo "  Java:   java -cp .:gson-2.8.9.jar JavaMultithreadJob --num-subjobs 20"
echo "  C:      ./c_multiprocess_job --num-subjobs 20"
echo "  Perl:   ./perl_multiprocess_job.pl --num-subjobs 20"
echo ""

