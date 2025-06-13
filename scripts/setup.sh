#!/bin/bash
# Setup script for PS Ticket Process Bot development environment

set -e  # Exit on any error

echo "🚀 Setting up PS Ticket Process Bot development environment..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is required but not installed"
    exit 1
fi

echo "✅ pip3 found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install development requirements
echo "📦 Installing development requirements..."
pip install -r requirements-dev.txt

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x scripts/validate_jira_access.py
chmod +x scripts/setup_jira_webhooks.py

# Create .env file from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "✅ .env file created. Please edit it with your actual values."
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p data
mkdir -p tests

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your JIRA and API credentials"
echo "2. Run: source venv/bin/activate"
echo "3. Run: python scripts/validate_jira_access.py"
echo "4. Run: python scripts/setup_jira_webhooks.py"
echo ""
echo "For more information, see docs/jira-configuration.md"
