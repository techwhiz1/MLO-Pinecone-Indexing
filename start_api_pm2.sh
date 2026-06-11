#!/bin/bash

# Start Chatbot API with PM2
# Usage: ./start_api_pm2.sh

cd /home/ubuntu/pinecone_indexing

echo "Starting Chatbot API with PM2..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 is not installed. Installing..."
    sudo npm install -g pm2
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Stop existing instance if running
pm2 stop chatbot-api 2>/dev/null || true

# Start with ecosystem file
if [ -f "ecosystem.config.js" ]; then
    pm2 start ecosystem.config.js
else
    # Fallback to direct start
    pm2 start chatbot_api.py \
        --name chatbot-api \
        --interpreter venv/bin/python \
        --log logs/combined.log \
        --error logs/error.log \
        --out logs/output.log
fi

# Save PM2 process list
pm2 save

echo ""
echo "✅ Chatbot API started!"
echo ""
echo "Useful commands:"
echo "  pm2 status           - View status"
echo "  pm2 logs chatbot-api - View logs"
echo "  pm2 restart chatbot-api - Restart"
echo "  pm2 stop chatbot-api - Stop"
echo "  pm2 monit            - Monitor"
echo ""
echo "API is running on http://localhost:9001"

