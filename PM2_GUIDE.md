# PM2 Process Manager Guide for Chatbot API

Complete guide for running the chatbot API with PM2 process manager.

## What is PM2?

PM2 is a production-grade process manager that:
- Keeps your application running 24/7
- Automatically restarts on crashes
- Manages logs
- Provides monitoring
- Starts on system boot
- Zero-downtime reloads

## Quick Start

### Option 1: Using the start script (Easiest)

```bash
cd /home/ubuntu/pinecone_indexing
chmod +x start_api_pm2.sh
./start_api_pm2.sh
```

### Option 2: Using ecosystem file

```bash
cd /home/ubuntu/pinecone_indexing
pm2 start ecosystem.config.js
pm2 save
```

### Option 3: Direct command

```bash
cd /home/ubuntu/pinecone_indexing
pm2 start chatbot_api.py --name chatbot-api --interpreter venv/bin/python
pm2 save
```

## Installation

If PM2 is not installed:

```bash
# Install Node.js and npm first (if needed)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2 globally
sudo npm install -g pm2
```

## Essential PM2 Commands

### Start/Stop/Restart

```bash
# Start the API
pm2 start ecosystem.config.js

# Stop the API
pm2 stop chatbot-api

# Restart the API
pm2 restart chatbot-api

# Reload (zero-downtime restart)
pm2 reload chatbot-api

# Delete from PM2
pm2 delete chatbot-api
```

### Monitoring

```bash
# View status
pm2 status

# View real-time logs
pm2 logs chatbot-api

# View only errors
pm2 logs chatbot-api --err

# View last 200 lines
pm2 logs chatbot-api --lines 200

# Clear logs
pm2 flush

# Real-time monitoring dashboard
pm2 monit

# Get detailed info
pm2 describe chatbot-api
```

### Managing Multiple Instances

```bash
# List all processes
pm2 list

# Restart all processes
pm2 restart all

# Stop all processes
pm2 stop all

# Delete all processes
pm2 delete all
```

## Auto-Start on System Reboot

To make the API start automatically when the server reboots:

```bash
# Generate startup script
pm2 startup

# This will output a command like:
# sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u ubuntu --hp /home/ubuntu
# Copy and run that command

# Save current process list
pm2 save

# Test by rebooting
sudo reboot
```

After reboot, check with:
```bash
pm2 list
```

## Configuration File (ecosystem.config.js)

The ecosystem file is already created with these settings:

```javascript
{
  name: 'chatbot-api',                    // Process name
  script: 'venv/bin/python',              // Python interpreter
  args: 'chatbot_api.py',                 // Script to run
  instances: 1,                           // Number of instances
  autorestart: true,                      // Auto-restart on crash
  max_memory_restart: '1G',               // Restart if memory exceeds 1GB
  error_file: 'logs/error.log',           // Error log location
  out_file: 'logs/output.log',            // Output log location
}
```

## Viewing Logs

### Real-time logs

```bash
# All logs
pm2 logs chatbot-api

# Only errors
pm2 logs chatbot-api --err

# Only output
pm2 logs chatbot-api --out

# With timestamp
pm2 logs chatbot-api --timestamp

# Specific number of lines
pm2 logs chatbot-api --lines 100
```

### Log files location

```
/home/ubuntu/pinecone_indexing/logs/error.log   - Error logs
/home/ubuntu/pinecone_indexing/logs/output.log  - Output logs
```

View logs directly:
```bash
# Tail error log
tail -f /home/ubuntu/pinecone_indexing/logs/error.log

# Tail output log
tail -f /home/ubuntu/pinecone_indexing/logs/output.log
```

## Updating the Application

When you make changes to `chatbot_api.py`:

```bash
# Option 1: Restart
pm2 restart chatbot-api

# Option 2: Reload (zero-downtime)
pm2 reload chatbot-api

# Option 3: Stop, pull changes, start
pm2 stop chatbot-api
# ... make your changes ...
pm2 start chatbot-api
```

## Monitoring

### Basic monitoring

```bash
# Interactive monitoring
pm2 monit

# Status overview
pm2 status

# Detailed process info
pm2 describe chatbot-api
```

### Web monitoring (PM2 Plus)

For advanced monitoring:
```bash
pm2 register
# Follow the prompts to connect to PM2 Plus
```

## Troubleshooting

### API not starting

```bash
# Check status
pm2 status

# View error logs
pm2 logs chatbot-api --err --lines 50

# Check if port is in use
lsof -i :9001

# Try starting manually first
cd /home/ubuntu/pinecone_indexing
source venv/bin/activate
python chatbot_api.py
```

### High memory usage

```bash
# Check memory
pm2 list

# Set memory limit (restarts if exceeded)
pm2 restart chatbot-api --max-memory-restart 500M

# Or update ecosystem.config.js
```

### Process keeps restarting

```bash
# View error logs
pm2 logs chatbot-api --err

# Check restarts
pm2 describe chatbot-api | grep "restart"

# Common issues:
# - Port already in use
# - Missing dependencies
# - Invalid API keys
```

### Can't stop process

```bash
# Force stop
pm2 stop chatbot-api --force

# Or delete it
pm2 delete chatbot-api
```

## Best Practices

### 1. Use ecosystem file
Always use `ecosystem.config.js` for production - it's more reliable and easier to manage.

### 2. Save configuration
After starting, always run:
```bash
pm2 save
```

### 3. Monitor logs
Regularly check logs:
```bash
pm2 logs chatbot-api --lines 50
```

### 4. Set up log rotation
```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

### 5. Use health checks
Check API health regularly:
```bash
curl http://localhost:9001/health
```

## Complete Workflow Example

```bash
# 1. Navigate to project
cd /home/ubuntu/pinecone_indexing

# 2. Ensure virtual environment exists
ls venv/

# 3. Start with PM2
pm2 start ecosystem.config.js

# 4. Save configuration
pm2 save

# 5. Set up auto-start
pm2 startup
# Run the command it outputs

# 6. Check status
pm2 status

# 7. View logs
pm2 logs chatbot-api

# 8. Test the API
curl http://localhost:9001/health
```

## Useful PM2 Commands Cheatsheet

```bash
# Start
pm2 start ecosystem.config.js

# Stop
pm2 stop chatbot-api

# Restart
pm2 restart chatbot-api

# Reload (zero-downtime)
pm2 reload chatbot-api

# Delete
pm2 delete chatbot-api

# Status
pm2 status

# Logs
pm2 logs chatbot-api

# Monitor
pm2 monit

# Save list
pm2 save

# Startup script
pm2 startup

# Clear logs
pm2 flush

# Resurrect saved processes
pm2 resurrect
```

## Integration with Nginx

Your nginx is configured to proxy to port 9001, which is where the API runs. Once PM2 starts the API, nginx will automatically route traffic to it:

```
User Request → nginx (port 80/443) → PM2-managed API (port 9001)
```

Test the full stack:
```bash
# Test directly
curl http://localhost:9001/health

# Test through nginx
curl http://cencan.mininglifeserver.com/health
```

## Next Steps

1. ✅ Start API with PM2: `pm2 start ecosystem.config.js`
2. ✅ Save configuration: `pm2 save`
3. ✅ Enable auto-start: `pm2 startup` and run the generated command
4. ✅ Test the API: `curl http://localhost:9001/health`
5. ✅ Monitor: `pm2 monit` or `pm2 logs chatbot-api`

Your chatbot API is now running 24/7 with automatic restarts and log management! 🚀

