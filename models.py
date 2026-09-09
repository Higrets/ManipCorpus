from sqlalchemy import Column, Integer, String, Text, Boolean, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from database import Base

class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(Integer, primary_key=True, index=True)
    source_url = Column(Text)
    domain = Column(String(100))
    raw_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    status = Column(String(50), default='pending')
    
    annotations = relationship("Annotation", back_populates="document")

class ManipulationType(Base):
    __tablename__ = "manipulation_types"
    type_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name_ru = Column(String(255), nullable=False)
    definition = Column(Text)

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    role = Column(String(50), nullable=False)

class Annotation(Base):
    __tablename__ = "annotations"
    annotation_id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer, ForeignKey("documents.doc_id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.user_id"))
    type_id = Column(Integer, ForeignKey("manipulation_types.type_id"))
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    comment = Column(Text)
    is_ai_suggested = Column(Boolean, default=False)

    document = relationship("Document", back_populates="annotations")
    
    __table_args__ = (
        CheckConstraint('start_offset < end_offset', name='valid_offsets'),
    )