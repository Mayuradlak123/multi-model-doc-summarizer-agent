import os
import chromadb
from .logger import logger
from .settings import settings

def get_chroma_client():
    try:
        # Connect to Chroma Cloud
        api_key = settings.CHROMA_API_KEY
        tenant = settings.CHROMA_TENANT
        database = settings.CHROMA_DATABASE
        
        if not api_key:
            logger.warning("CHROMA_API_KEY not found in environment settings. Falling back to local/remote client.")
            # Fallback to local/remote if cloud key is missing
            return chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT
            )

        client = chromadb.CloudClient(
            api_key=api_key,
            tenant=tenant,
            database=database
        )
        
        # Test connection
        client.heartbeat()
        logger.info(f"Successfully connected to Chroma Cloud (Tenant: {tenant}, DB: {database})")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Chroma Server: {str(e)}")
        logger.warning("Falling back to Chroma EphemeralClient (In-Memory) for local development.")
        try:
            return chromadb.EphemeralClient()
        except Exception as inner_e:
            logger.critical(f"Failed to initialize Ephemeral Chroma Client: {str(inner_e)}")
            return None

chroma_client = get_chroma_client()
