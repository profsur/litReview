# database.py
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# --- CONNECTION STRING ---
# For local file-based testing (SQLite):
DATABASE_URL = "sqlite:///literature_repository.db"

# To switch to PostgreSQL later, simply swap the URL to:
# DATABASE_URL = "postgresql://username:password@localhost:5432/literature_db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- TABLE DEFINITION ---
class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    authors = Column(String)
    year = Column(Integer)
    domain = Column(String, index=True)
    
    # Methodology
    sample_size = Column(String)
    technique = Column(String)
    
    # Insights (Using Text for longer string storage)
    variables = Column(Text) 
    findings = Column(Text)
    limitations = Column(Text)
    file_reference = Column(String)

# Create the tables in the database
Base.metadata.create_all(bind=engine)