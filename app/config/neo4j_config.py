from neo4j import GraphDatabase
from .logger import logger
from .settings import settings

class Neo4jConfig:
    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.username = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.driver = None

    def connect(self):
        try:
            if not self.driver and self.password:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
                # Verify connectivity
                self.driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j")
            elif not self.password:
                logger.warning("NEO4J_PASSWORD not set. Skipping Neo4j driver initiation.")
            return self.driver
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            return None

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

neo4j_manager = Neo4jConfig()
# Try connecting (disabled for now)
# neo4j_manager.connect()
