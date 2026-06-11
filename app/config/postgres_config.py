import psycopg2
from .logger import logger
from .settings import settings

class PostgresConfig:
    def __init__(self):
        self.host = settings.POSTGRES_HOST
        self.port = settings.POSTGRES_PORT
        self.dbname = settings.POSTGRES_DB
        self.user = settings.POSTGRES_USER
        self.password = settings.POSTGRES_PASSWORD
        self.conn = None

    def connect(self):
        """Attempts to open a connection to the PostgreSQL database."""
        try:
            if not self.conn:
                if settings.POSTGRES_URL:
                    logger.info("Connecting to PostgreSQL database using POSTGRES_URL...")
                    self.conn = psycopg2.connect(
                        settings.POSTGRES_URL,
                        connect_timeout=5
                    )
                else:
                    logger.info(f"Connecting to PostgreSQL database at {self.host}:{self.port}/{self.dbname}...")
                    self.conn = psycopg2.connect(
                        host=self.host,
                        port=self.port,
                        dbname=self.dbname,
                        user=self.user,
                        password=self.password,
                        connect_timeout=5  # Quick timeout to prevent startup hangs if DB is offline
                    )
                logger.info("Successfully connected to PostgreSQL")
            return self.conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
            self.conn = None
            return None

    def close(self):
        """Closes the active connection if it exists."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("PostgreSQL connection closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL connection: {str(e)}")
            finally:
                self.conn = None

postgres_manager = PostgresConfig()
