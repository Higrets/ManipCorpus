"""
Модуль полуавтоматической разметки (AI-ассистент) для системы ManipCorpus.
Реализует функцию 2 ТЗ: предложение предварительных гипотез на основе лингвистических маркеров.
"""
import spacy
from spacy.matcher import Matcher
from typing import List, Dict
from models import ManipulationType
from sqlalchemy.orm import Session

# Загрузка русской модели spaCy
nlp = spacy.load("ru_core_news_sm")

# Словарь лингвистических маркеров для прототипа (в реальной системе загружается из БД или конфига)
LINGUISTIC_MARKERS = {
    "FALSE_DILEMMA": [
        [{"LOWER": "либо"}, {"IS_PUNCT": True, "OP": "*"}, {"LOWER": "либо"}],
        [{"LOWER": "третьего"}, {"LOWER": "не"}, {"LOWER": "дано"}],
        [{"LOWER": "или"}, {"IS_PUNCT": True, "OP": "*"}, {"LOWER": "или"}]
    ],
    "APPEAL_EMOTION": [
        [{"LOWER": "не"}, {"LOWER": "любят"}],
        [{"LOWER": "враги"}, {"OP": "*"}],
        [{"LOWER": "предатели"}]
    ],
    "LABELING": [
        [{"LOWER": "враг"}, {"OP": "*"}],
        [{"LOWER": "агент"}, {"OP": "*"}]
    ]
}

def suggest_annotations(text: str, types_dict: Dict[int, str]) -> List[Dict]:
    """
    Анализирует текст и возвращает список предполагаемых аннотаций.
    """
    doc = nlp(text)
    matcher = Matcher(nlp.vocab)
    
    # Добавляем паттерны в matcher
    for type_code, patterns in LINGUISTIC_MARKERS.items():
        matcher.add(type_code, patterns)
    
    # Находим совпадения
    matches = matcher(doc)
    suggestions = []
    
    for match_id, start, end in matches:
        span = doc[start:end]
        type_code = nlp.vocab.strings[match_id]
        
        # Находим type_id по коду
        type_id = None
        for t_id, t_code in types_dict.items():
            if t_code == type_code:
                type_id = t_id
                break
                
        if type_id:
            suggestions.append({
                "start_offset": span.start_char,
                "end_offset": span.end_char,
                "type_code": type_code,
                "type_id": type_id,
                "matched_text": span.text,
                "is_ai_suggested": True,
                "confidence": 0.85  # Имитация уверенности модели для будущего ML-апгрейда
            })
            
    # Сортируем предложения по позиции в тексте
    suggestions.sort(key=lambda x: x["start_offset"])
    return suggestions

def apply_suggestions_to_db(db: Session, doc_id: int, suggestions: List[Dict], ai_user_id: int) -> List[int]:
    """
    Сохраняет предложенные аннотации в базу данных с флагом is_ai_suggested=True.
    Возвращает список созданных ID аннотаций.
    """
    from models import Annotation
    
    created_ids = []
    for sugg in suggestions:
        # Проверяем, нет ли уже такой аннотации (защита от дубликатов)
        existing = db.query(Annotation).filter(
            Annotation.doc_id == doc_id,
            Annotation.start_offset == sugg["start_offset"],
            Annotation.end_offset == sugg["end_offset"],
            Annotation.type_id == sugg["type_id"]
        ).first()
        
        if not existing:
            new_ann = Annotation(
                doc_id=doc_id,
                user_id=ai_user_id,
                type_id=sugg["type_id"],
                start_offset=sugg["start_offset"],
                end_offset=sugg["end_offset"],
                comment=f"AI suggestion: matched '{sugg['matched_text']}'",
                is_ai_suggested=True
            )
            db.add(new_ann)
            db.commit()
            db.refresh(new_ann)
            created_ids.append(new_ann.annotation_id)
            
    return created_ids