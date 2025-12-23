#!/usr/bin/env bash
# Setup script for Mac development environment

set -e

cd "/Users/ankursharma/Documents/Dev Projects/tokymon"

echo "🔧 Setting up Tokymon development environment..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✓ Virtual environment already exists"
fi

# Activate venv
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Session Orchestrator:"
echo "  ./run_session_mac.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  export TOKY_ENV=dev"
echo "  python3 main_session.py"

