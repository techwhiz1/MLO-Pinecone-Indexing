module.exports = {
  apps: [{
    name: 'chatbot-api',
    script: '/home/ubuntu/pinecone_indexing/venv/bin/python',
    args: '/home/ubuntu/pinecone_indexing/chatbot_api.py',
    cwd: '/home/ubuntu/pinecone_indexing',
    interpreter: 'none',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: '/home/ubuntu/pinecone_indexing'
    },
    error_file: '/home/ubuntu/pinecone_indexing/logs/error.log',
    out_file: '/home/ubuntu/pinecone_indexing/logs/output.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    time: true
  }, {
    name: 'product-trigger',
    script: '/home/ubuntu/pinecone_indexing/venv/bin/python',
    args: '/home/ubuntu/pinecone_indexing/product_trigger.py',
    cwd: '/home/ubuntu/pinecone_indexing',
    interpreter: 'none',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: '/home/ubuntu/pinecone_indexing'
    },
    error_file: '/home/ubuntu/pinecone_indexing/logs/product-trigger-error.log',
    out_file: '/home/ubuntu/pinecone_indexing/logs/product-trigger-output.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    merge_logs: true,
    time: true
  }, {
    name: 'product-integration',
    script: '/home/ubuntu/pinecone_indexing/venv/bin/python',
    args: '/home/ubuntu/pinecone_indexing/product_integration.py',
    cwd: '/home/ubuntu/pinecone_indexing',
    interpreter: 'none',
    instances: 1,
    // This is a finite batch job. Do not restart it after a normal completion
    // or a failed row, because that could repeatedly re-run the workbook.
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
