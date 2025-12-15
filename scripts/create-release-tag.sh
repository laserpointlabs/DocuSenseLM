#!/bin/bash
# Script to create a release tag and ensure build artifacts are generated
# Usage: ./scripts/create-release-tag.sh <version> <message>
# Example: ./scripts/create-release-tag.sh 1.0.15 "Add new feature"

set -e

VERSION=$1
MESSAGE=$2

if [ -z "$VERSION" ] || [ -z "$MESSAGE" ]; then
    echo "Usage: $0 <version> <message>"
    echo "Example: $0 1.0.15 'Add new feature'"
    exit 1
fi

# Validate version format (vX.Y.Z)
if [[ ! $VERSION =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 1.0.15)"
    exit 1
fi

# Ensure version starts with 'v'
if [[ ! $VERSION =~ ^v ]]; then
    VERSION="v$VERSION"
fi

echo "Creating release tag: $VERSION"
echo "Message: $MESSAGE"
echo ""

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "Warning: Not on main branch (currently on $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Warning: You have uncommitted changes"
    git status --short
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update version in package.json
VERSION_NUM=$(echo $VERSION | sed 's/^v//')
if [ -f "package.json" ]; then
    echo "Updating version in package.json to $VERSION_NUM..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION_NUM\"/" package.json
    else
        # Linux
        sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION_NUM\"/" package.json
    fi
    
    # Update version in App.tsx if it exists
    if [ -f "src/App.tsx" ]; then
        echo "Updating version in src/App.tsx to $VERSION_NUM..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/const APP_VERSION = \"[^\"]*\"/const APP_VERSION = \"$VERSION_NUM\"/" src/App.tsx
        else
            sed -i "s/const APP_VERSION = \"[^\"]*\"/const APP_VERSION = \"$VERSION_NUM\"/" src/App.tsx
        fi
    fi
    
    git add package.json src/App.tsx
    git commit -m "chore: Bump version to $VERSION_NUM"
fi

# Build web assets
echo ""
echo "Building web assets..."
npm run build:web

# Create annotated tag
echo ""
echo "Creating tag $VERSION..."
git tag -a "$VERSION" -m "$VERSION: $MESSAGE"

echo ""
echo "✅ Release tag $VERSION created successfully!"
echo ""
echo "Next steps:"
echo "  1. Review the tag: git show $VERSION"
echo "  2. Push the tag: git push origin $VERSION"
echo "  3. Push commits: git push origin main"
echo ""
echo "The build workflow will automatically create artifacts for this tag."

