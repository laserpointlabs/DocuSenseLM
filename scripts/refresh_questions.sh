#!/bin/bash
# Script to clean existing questions and generate fresh document-specific questions

echo "================================================================================"
echo "Refresh Competency Questions"
echo "================================================================================"
echo ""
echo "This will:"
echo "  1. Delete all existing competency questions and test data"
echo "  2. Generate fresh document-specific questions from loaded documents"
echo ""

read -p "Continue? (yes/no): " response
if [ "$response" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Step 1: Cleaning existing questions..."
python3 scripts/clean_questions.py <<< "yes"

echo ""
echo "Step 2: Generating document-specific questions..."
python3 scripts/generate_document_questions.py --create --no-llm

echo ""
echo "================================================================================"
echo "Done! Questions have been refreshed."
echo "================================================================================"

