from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .logger import logger
from .settings import settings

class PostgresConfig:
    def __init__(self):
        self.host = settings.POSTGRES_HOST
        self.port = settings.POSTGRES_PORT
        self.dbname = settings.POSTGRES_DB
        self.user = settings.POSTGRES_USER
        self.password = settings.POSTGRES_PASSWORD
        self.url = settings.POSTGRES_URL
        
        self.engine = None
        self.SessionLocal = None

    def connect(self):
        """Attempts to open a connection and configure SQLAlchemy engine/sessionmaker."""
        try:
            if not self.engine:
                db_url = self.url
                if not db_url:
                    db_url = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"
                
                logger.info("Initializing SQLAlchemy database engine...")
                self.engine = create_engine(
                    db_url,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 5}
                )
                self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
                
                # Run automatic table creation
                try:
                    from app.db.models import Base
                    Base.metadata.create_all(bind=self.engine)
                    logger.info("Database tables verified/created successfully via SQLAlchemy.")
                except Exception as me:
                    logger.error(f"SQLAlchemy table initialization failure: {str(me)}")
                    
            return self.engine
        except Exception as e:
            logger.error(f"Failed to connect and initialize SQLAlchemy: {str(e)}")
            self.engine = None
            self.SessionLocal = None
            return None

    @contextmanager
    def get_session(self):
        """Context manager to yield a transactional SQLAlchemy session."""
        self.connect()
        if not self.SessionLocal:
            logger.error("SQLAlchemy SessionLocal is not initialized. Database is offline.")
            yield None
            return
            
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            try:
                session.rollback()
            except Exception:
                pass
            logger.error(f"SQLAlchemy transaction failed: {str(e)}")
            raise e
        finally:
            session.close()

    def close(self):
        """Disposes the active SQLAlchemy engine."""
        if self.engine:
            try:
                self.engine.dispose()
                logger.info("SQLAlchemy engine disposed")
            except Exception as e:
                logger.error(f"Error disposing SQLAlchemy engine: {str(e)}")
            finally:
                self.engine = None
                self.SessionLocal = None

postgres_manager = PostgresConfig()


