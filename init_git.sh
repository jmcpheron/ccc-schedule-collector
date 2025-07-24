#!/bin/bash

# Initialize git repository for Rio Hondo Schedule Collector

echo "🚀 Initializing Git repository..."

# Initialize git if not already initialized
if [ ! -d ".git" ]; then
    git init
    echo "✅ Git repository initialized"
else
    echo "ℹ️  Git repository already exists"
fi

# Add all files
echo ""
echo "📁 Adding files to git..."
git add .

# Show status
echo ""
echo "📊 Current status:"
git status --short

# Create initial commit
echo ""
read -p "Create initial commit? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "Initial commit: Rio Hondo Schedule Collector

- BeautifulSoup-based HTML parser
- Pydantic data models
- UV package management
- CLI analysis tools
- GitHub Actions workflows
- Local testing utilities"
    
    echo "✅ Initial commit created"
fi

echo ""
echo "🔧 Recommended next steps:"
echo "1. Test with local HTML: ./test_local.py"
echo "2. Test web collection: ./test_collection.py --test-connection"
echo "3. Create GitHub repository and add remote:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/ccc-schedule-collector.git"
echo "4. Push to GitHub: git push -u origin main"