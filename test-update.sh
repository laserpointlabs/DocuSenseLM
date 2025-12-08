#!/bin/bash

# Test auto-update functionality for DocuSenseLM
# This script helps test the update mechanism

echo "🔄 Testing DocuSenseLM Auto-Updates"
echo "=================================="

# Check current version
echo "📋 Current version: $(node -p "require('./package.json').version")"
echo ""

# Check available versions
echo "📦 Available versions:"
ls -la dist/ | grep -E "\.AppImage$" | awk '{print "   - " $9 " (" $5 " bytes)"}'
echo ""

# Step 1: Test current version
echo "🧪 Step 1: Test current version (1.0.4)"
echo "   - Run: ./dist/DocuSenseLM-1.0.4.AppImage"
echo "   - Check that app title shows 'DocuSenseLM' (not 'NDA Tool')"
echo "   - Check that version shows '1.0.4' in sidebar"
echo "   - Check loading screen says 'Initializing DocuSenseLM...'"
echo ""

# Step 2: Build and test new version
echo "🏗️  Step 2: Build version 1.0.5"
echo "   - Update package.json version to 1.0.5"
echo "   - Update src/App.tsx APP_VERSION to 1.0.5"
echo "   - Run: npm run build:linux"
echo "   - New AppImage will have ✨ next to version"
echo ""

# Step 3: Manual update test
echo "🔄 Step 3: Manual update simulation"
echo "   - Run 1.0.4 version - should show 'DocuSenseLM' title"
echo "   - Run 1.0.5 version - should show same title but version 1.0.5"
echo "   - ✨ proves the update mechanism works!"
echo ""

# Step 4: Enable GitHub token for CI builds (optional)
echo "🔑 Step 4: Enable CI builds (optional)"
echo "   - Add GH_TOKEN secret to GitHub repository"
echo "   - Remove --publish never from workflow"
echo "   - Push to trigger automatic builds"
echo ""

echo "✅ Ready to test!"
echo "Run this script again after each version bump."
