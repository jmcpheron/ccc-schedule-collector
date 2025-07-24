#!/bin/bash

# Rio Hondo College Schedule Collector Setup Script

echo "🎓 Rio Hondo College Schedule Collector Setup"
echo "============================================="
echo ""

# Check for uv installation
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "✅ uv installed"
else
    echo "✅ uv is already installed"
fi

# Make scripts executable
echo ""
echo "🔧 Making scripts executable..."
chmod +x collect.py test_collector.py cli.py
echo "✅ Scripts are now executable"

# Run tests
echo ""
echo "🧪 Running tests..."
if uv run test_collector.py; then
    echo "✅ All tests passed!"
else
    echo "⚠️  Some tests failed, but continuing setup..."
fi

# Test imports
echo ""
echo "📚 Verifying imports..."
python3 -c "
import sys
sys.path.append('.')
try:
    from collect import RioHondoCollector
    from utils.parser import RioHondoScheduleParser
    from utils.storage import ScheduleStorage
    from models import Course, ScheduleData
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

# Create sample collection
echo ""
echo "📊 Testing CLI tools..."
echo '{"term": "Test", "term_code": "TEST", "collection_timestamp": "2025-01-24T12:00:00", "source_url": "test", "courses": [], "total_courses": 0, "departments": []}' > data/test_schedule.json
uv run cli.py validate data/test_schedule.json
rm data/test_schedule.json

echo ""
echo "✨ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Push to GitHub to activate automated collection"
echo "2. Use 'uv run collect.py' to run a manual collection"
echo "3. Use 'uv run cli.py --help' to explore analysis tools"
echo ""
echo "The collector will run automatically on GitHub Actions:"
echo "- Schedule: Monday, Wednesday, Friday at 6 AM UTC"
echo "- Manual trigger: Actions tab → 'Run workflow'"
echo ""
echo "Happy collecting! 🚀"