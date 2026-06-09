import os
import sys
from rq import Connection, Worker

# Ensure the root directory is in the path so python can find the 'app' module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import logger
from app.config.redis_config import redis_client

def start_worker():
    if not redis_client:
        logger.critical("Cannot start Redis Queue worker. Redis service connection is offline.")
        sys.exit(1)
        
    logger.info("Initializing Redis Queue (RQ) background task worker listening on 'default' queue...")
    
    try:
        # Establish connection context and run the worker
        with Connection(redis_client):
            worker = Worker(['default'])
            # Start processing jobs (runs blocking loop)
            worker.work(logging_level='INFO')
    except Exception as e:
        logger.critical(f"Redis Queue worker encountered a fatal error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    start_worker()
