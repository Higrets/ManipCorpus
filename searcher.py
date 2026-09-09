"""
Модуль поиска и фильтрации для системы ManipCorpus.
Реализует функцию 4 ТЗ: гибкий поиск по типу манипуляции, домену, дате, тексту.
"""
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models import Document, Annotation, ManipulationType


class CorpusSearcher:
    """Класс для поиска и фильтрации документов корпуса."""
    
    @staticmethod
    def search_by_domain(db: Session, domain: str) -> List[Document]:
        """Поиск документов по домену (политика, СМИ, реклама и т.д.)."""
        return db.query(Document).filter(Document.domain == domain).all()
    
    @staticmethod
    def search_by_date_range(
        db: Session, 
        start_date: Optional[date] = None, 
        end_date: Optional[date] = None
    ) -> List[Document]:
        """Поиск документов по диапазону дат публикации."""
        query = db.query(Document)
        
        if start_date:
            query = query.filter(Document.publish_date >= start_date)
        if end_date:
            query = query.filter(Document.publish_date <= end_date)
            
        return query.all()
    
    @staticmethod
    def search_by_manipulation_type(db: Session, type_code: str) -> List[Document]:
        """
        Поиск документов, содержащих аннотации определенного типа манипуляции.
        """
        # Находим type_id по коду
        m_type = db.query(ManipulationType).filter(
            ManipulationType.code == type_code
        ).first()
        
        if not m_type:
            return []
        
        # Находим все документы, у которых есть аннотации этого типа
        doc_ids = db.query(Annotation.doc_id).filter(
            Annotation.type_id == m_type.type_id
        ).distinct().all()
        
        doc_ids = [d[0] for d in doc_ids]
        
        if not doc_ids:
            return []
        
        return db.query(Document).filter(Document.doc_id.in_(doc_ids)).all()
    
    @staticmethod
    def search_by_text(db: Session, text_query: str) -> List[Document]:
        """Полнотекстовый поиск по содержимому документов."""
        # Простой поиск по подстроке (для прототипа)
        # В продакшене можно использовать PostgreSQL Full Text Search
        pattern = f"%{text_query}%"
        return db.query(Document).filter(
            or_(
                Document.raw_text.ilike(pattern),
                Document.normalized_text.ilike(pattern)
            )
        ).all()
    
    @staticmethod
    def advanced_search(
        db: Session,
        domain: Optional[str] = None,
        manipulation_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        text_query: Optional[str] = None
    ) -> List[Document]:
        """
        Комбинированный поиск по нескольким критериям одновременно.
        """
        query = db.query(Document)
        
        # Фильтр по домену
        if domain:
            query = query.filter(Document.domain == domain)
        
        # Фильтр по датам
        if start_date:
            query = query.filter(Document.publish_date >= start_date)
        if end_date:
            query = query.filter(Document.publish_date <= end_date)
        
        # Фильтр по тексту
        if text_query:
            pattern = f"%{text_query}%"
            query = query.filter(
                or_(
                    Document.raw_text.ilike(pattern),
                    Document.normalized_text.ilike(pattern)
                )
            )
        
        # Фильтр по типу манипуляции (самый сложный - требует JOIN)
        if manipulation_type:
            m_type = db.query(ManipulationType).filter(
                ManipulationType.code == manipulation_type
            ).first()
            
            if m_type:
                doc_ids_with_type = db.query(Annotation.doc_id).filter(
                    Annotation.type_id == m_type.type_id
                ).distinct().all()
                doc_ids = [d[0] for d in doc_ids_with_type]
                
                if doc_ids:
                    query = query.filter(Document.doc_id.in_(doc_ids))
                else:
                    return []  # Нет документов с таким типом
        
        return query.all()
    
    @staticmethod
    def get_statistics(db: Session) -> Dict:
        """
        Получение общей статистики по корпусу (для аналитической панели).
        """
        total_docs = db.query(Document).count()
        total_annotations = db.query(Annotation).count()
        
        # Статистика по доменам
        domain_stats = {}
        domains = db.query(Document.domain).distinct().all()
        for (domain,) in domains:
            count = db.query(Document).filter(Document.domain == domain).count()
            domain_stats[domain] = count
        
        # Статистика по типам манипуляций
        type_stats = {}
        types = db.query(ManipulationType).all()
        for m_type in types:
            count = db.query(Annotation).filter(
                Annotation.type_id == m_type.type_id
            ).count()
            type_stats[m_type.code] = count
        
        return {
            "total_documents": total_docs,
            "total_annotations": total_annotations,
            "documents_by_domain": domain_stats,
            "annotations_by_type": type_stats
        }