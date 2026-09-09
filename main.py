from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas, database
from preprocessor import TextPreprocessor
from importer import TextImporter
import json
import tempfile
import os
from fastapi import UploadFile, File
from analytics import get_agreement_report
from exporter import generate_full_corpus_export
from fastapi.responses import Response
from searcher import CorpusSearcher
from datetime import date
from auto_annotator import suggest_annotations, apply_suggestions_to_db
from models import Document, Annotation, ManipulationType
import schemas, database


# Создание таблиц в БД при первом запуске (если их нет)
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="ManipCorpus API",
    description="Система для создания и анализа размеченного корпуса манипулятивных текстов",
    version="1.0.0"
)

# --- ЭНДПОИНТЫ (Реализация функций ТЗ) ---

@app.post("/api/v1/annotations/", response_model=schemas.AnnotationResponse, tags=["Разметка"])
def create_annotation(annotation: schemas.AnnotationCreate, db: Session = Depends(database.get_db)):
    """
    Функция 2 ТЗ: Сохранение ручной или полуавтоматической разметки.
    """
    db_annotation = models.Annotation(**annotation.dict())
    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)
    return db_annotation

@app.get("/api/v1/documents/{doc_id}/annotations", response_model=List[schemas.AnnotationResponse], tags=["Аналитика"])
def get_document_annotations(doc_id: int, db: Session = Depends(database.get_db)):
    """
    Получение всех аннотаций для текста (нужно для расчета Каппы Коэна).
    """
    annotations = db.query(models.Annotation).filter(models.Annotation.doc_id == doc_id).all()
    if not annotations:
        raise HTTPException(status_code=404, detail="Annotations not found")
    return annotations

@app.get("/api/v1/taxonomy/", tags=["Справочники"])
def get_manipulation_types(db: Session = Depends(database.get_db)):
    """Получение таксономии манипуляций."""
    return db.query(models.ManipulationType).all()

# --- ЭНДПОИНТЫ ИМПОРТА (Реализация Функции 1 ТЗ) ---

@app.post("/api/v1/documents/import/text", tags=["Импорт"])
async def import_single_text(
    text: str,
    domain: str = Query(default="unknown", description="Домен: политика, сми, реклама"),
    source_url: str = Query(default=None),
    db: Session = Depends(database.get_db)
):
    """
    Импорт одного текста через строку.
    """
    processed = TextPreprocessor.full_pipeline(text)
    
    new_doc = models.Document(
        source_url=source_url,
        domain=domain,
        raw_text=processed["raw_text"],
        normalized_text=processed["normalized_text"],
        status="pending"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return {
        "doc_id": new_doc.doc_id,
        "status": "imported",
        "stats": {
            "char_count": processed["char_count"],
            "sentence_count": processed["sentence_count"],
            "token_count": processed["token_count"],
        }
    }


@app.post("/api/v1/documents/import/file", tags=["Импорт"])
async def import_from_file(
    file: UploadFile = File(...),
    domain: str = Query(default="unknown"),
    db: Session = Depends(database.get_db)
):
    """
    Пакетный импорт из файла (TXT, CSV, JSON).
    """
    # Сохраняем файл во временную папку
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Выбираем импортер по расширению
        if suffix == ".txt":
            docs_data = TextImporter.import_from_txt(tmp_path)
        elif suffix == ".csv":
            docs_data = TextImporter.import_from_csv(tmp_path)
        elif suffix == ".json":
            docs_data = TextImporter.import_from_json(tmp_path)
        else:
            raise ValueError(f"Неподдерживаемый формат: {suffix}")
        
        # Сохраняем в БД
        imported_ids = []
        for doc_data in docs_data:
            new_doc = models.Document(
                source_url=doc_data["source_url"],
                domain=doc_data["domain"] if doc_data["domain"] != "unknown" else domain,
                raw_text=doc_data["raw_text"],
                normalized_text=doc_data["normalized_text"],
                status="pending"
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            imported_ids.append(new_doc.doc_id)
        
        return {
            "status": "success",
            "imported_count": len(imported_ids),
            "doc_ids": imported_ids
        }
    finally:
        # Удаляем временный файл
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/api/v1/documents/import/url", tags=["Импорт"])
async def import_from_url(
    url: str = Query(...),
    domain: str = Query(default="web"),
    db: Session = Depends(database.get_db)
):
    """
    Импорт текста по URL.
    """
    doc_data = TextImporter.import_from_url(url, domain)
    
    new_doc = models.Document(
        source_url=doc_data["source_url"],
        domain=doc_data["domain"],
        raw_text=doc_data["raw_text"],
        normalized_text=doc_data["normalized_text"],
        status="pending"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return {
        "doc_id": new_doc.doc_id,
        "status": "imported",
        "stats": doc_data["metadata"]["stats"]
    }


@app.get("/api/v1/analytics/agreement/{doc_id}", tags=["Аналитика"])
def get_agreement(doc_id: int, db: Session = Depends(database.get_db)):
    """
    Функция 2 ТЗ: Расчет межаннотаторской согласованности (Каппа Коэна) для документа.
    """
    report = get_agreement_report(doc_id, db)
    return report


@app.get("/api/v1/export/conllu", tags=["Экспорт"])
def export_corpus_conllu(db: Session = Depends(database.get_db)):
    """
    Функция 6 ТЗ: Экспорт всего размеченного корпуса в формате CoNLL-U (с BIO-разметкой).
    """
    data = generate_full_corpus_export(db, format="conllu")
    return Response(
        content=data,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=manipcorpus_export.conllu"}
    )

@app.get("/api/v1/export/jsonl", tags=["Экспорт"])
def export_corpus_jsonl(db: Session = Depends(database.get_db)):
    """
    Функция 6 ТЗ: Экспорт корпуса в формате JSONL (для Hugging Face datasets).
    """
    data = generate_full_corpus_export(db, format="jsonl")
    return Response(
        content=data,
        media_type="application/x-jsonlines",
        headers={"Content-Disposition": "attachment; filename=manipcorpus_export.jsonl"}
    )


# --- ЭНДПОИНТЫ ПОИСКА (Реализация Функции 4 ТЗ) ---

@app.get("/api/v1/search/domain/{domain}", tags=["Поиск"])
def search_by_domain(domain: str, db: Session = Depends(database.get_db)):
    """Поиск документов по домену."""
    docs = CorpusSearcher.search_by_domain(db, domain)
    return {
        "count": len(docs),
        "documents": [
            {
                "doc_id": d.doc_id,
                "domain": d.domain,
                "status": d.status,
                "char_count": len(d.normalized_text)
            }
            for d in docs
        ]
    }

@app.get("/api/v1/search/type/{type_code}", tags=["Поиск"])
def search_by_manipulation_type(type_code: str, db: Session = Depends(database.get_db)):
    """Поиск документов, содержащих определенный тип манипуляции."""
    docs = CorpusSearcher.search_by_manipulation_type(db, type_code)
    return {
        "count": len(docs),
        "type_code": type_code,
        "documents": [
            {
                "doc_id": d.doc_id,
                "domain": d.domain,
                "status": d.status
            }
            for d in docs
        ]
    }

@app.get("/api/v1/search/text", tags=["Поиск"])
def search_by_text(text: str, db: Session = Depends(database.get_db)):
    """Полнотекстовый поиск по содержимому документов."""
    docs = CorpusSearcher.search_by_text(db, text)
    return {
        "count": len(docs),
        "query": text,
        "documents": [
            {
                "doc_id": d.doc_id,
                "domain": d.domain,
                "text_preview": d.normalized_text[:200] + "..." if len(d.normalized_text) > 200 else d.normalized_text
            }
            for d in docs
        ]
    }

@app.get("/api/v1/search/advanced", tags=["Поиск"])
def advanced_search(
    domain: Optional[str] = None,
    manipulation_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    text: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    """Комбинированный поиск по нескольким критериям."""
    docs = CorpusSearcher.advanced_search(
        db, domain, manipulation_type, start_date, end_date, text
    )
    return {
        "count": len(docs),
        "filters": {
            "domain": domain,
            "manipulation_type": manipulation_type,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "text": text
        },
        "documents": [
            {
                "doc_id": d.doc_id,
                "domain": d.domain,
                "status": d.status
            }
            for d in docs
        ]
    }

@app.get("/api/v1/statistics", tags=["Аналитика"])
def get_corpus_statistics(db: Session = Depends(database.get_db)):
    """Получение общей статистики по корпусу."""
    return CorpusSearcher.get_statistics(db)


@app.post("/api/v1/documents/{doc_id}/suggest", tags=["Полуавтоматическая разметка"])
def get_ai_suggestions(doc_id: int, db: Session = Depends(database.get_db)):
    """
    Функция 2 ТЗ: Получение предварительных гипотез (аннотаций) от AI-ассистента.
    Аннотатор может просмотреть их и принять/отклонить.
    """
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Получаем справочник типов для маппинга
    types = db.query(ManipulationType).all()
    types_dict = {t.type_id: t.code for t in types}
    
    suggestions = suggest_annotations(doc.normalized_text, types_dict)
    
    return {
        "doc_id": doc_id,
        "suggestions_count": len(suggestions),
        "suggestions": suggestions
    }

@app.post("/api/v1/documents/{doc_id}/apply-suggestions", tags=["Полуавтоматическая разметка"])
def apply_ai_suggestions(doc_id: int, ai_user_id: int = 4, db: Session = Depends(database.get_db)):
    """
    Функция 2 ТЗ: Массовое применение предложенных AI аннотаций к документу.
    По умолчанию использует user_id = 4 (ai_assistant_system).
    """
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    types = db.query(ManipulationType).all()
    types_dict = {t.type_id: t.code for t in types}
    
    suggestions = suggest_annotations(doc.normalized_text, types_dict)
    created_ids = apply_suggestions_to_db(db, doc_id, suggestions, ai_user_id)
    
    return {
        "status": "success",
        "doc_id": doc_id,
        "suggestions_generated": len(suggestions),
        "annotations_saved": len(created_ids),
        "saved_ids": created_ids
    }