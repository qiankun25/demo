from sqlalchemy import Column, String, Integer, Boolean, Text, BigInteger
from app.database.session import Base

class Doc(Base):
    __tablename__ = "docs"

    doc_id = Column(String, primary_key=True, index=True)
    canonical_id = Column(String, index=True, nullable=True)
    doc_type = Column(String, default="paper", index=True)
    title = Column(Text, nullable=True)
    authors_json = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    venue = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    license = Column(Text, nullable=True)
    open_access = Column(Integer, nullable=True)
    pdf_object_key = Column(Text, nullable=True)
    pdf_sha256 = Column(String, index=True, nullable=True)
    extra_json = Column(Text, nullable=True)
    created_at_unix = Column(BigInteger, nullable=True)

