#!/bin/bash

# Run all unittests
for d in ./components/*/ ; do
    echo "Running tests in $d"
    python3 -m unittest discover -s $d -p "test_*.py" 
done
