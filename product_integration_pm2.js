module.exports = {
  apps: [{
    name: 'product-integration',
    script: '/home/ubuntu/pinecone_indexing/venv/bin/python',
    args: '/home/ubuntu/pinecone_indexing/product_integration.py',
    cwd: '/home/ubuntu/pinecone_indexing',
    interpreter: 'none',
    instances: 1,
    autorestart: false,
    watch: false,
    max_memory_restart: '1G',
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: '/home/ubuntu/pinecone_indexing'
    },
    error_file: '/home/ubuntu/pinecone_indexing/logs/product-integration-error.log',
    out_file: '/home/ubuntu/pinecone_indexing/logs/product-integration-output.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    time: true
  }]
};
