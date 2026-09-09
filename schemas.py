from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AnnotationCreate(BaseModel):
    doc_id: int
    user_id: int
    type_id: int
    start_offset: int
    end_offset: int
    comment: Optional[str] = None
    is_ai_suggested: bool = False

class AnnotationResponse(AnnotationCreate):
    annotation_id: int
    class Config:
        from_attributes = True