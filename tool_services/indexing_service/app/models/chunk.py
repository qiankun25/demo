from sqlalchemy import Column, String, Integer, Text, ForeignKey
from app.database.session import Base

class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id = Column(String, primary_key=True, index=True)
    doc_id = Column(String, ForeignKey("docs.doc_id"), index=True)
    text = Column(Text, nullable=False)
    page = Column(Integer, nullable=True)
    paragraph = Column(Integer, nullable=True)
    section_path = Column(Text, nullable=True)

