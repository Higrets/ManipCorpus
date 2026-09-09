"""
Модуль экспорта данных корпуса ManipCorpus.
Реализует выгрузку в форматы CoNLL-U (с BIO-разметкой) и JSONL.
"""
import json
from typing import List, Dict
from models import Document, Annotation, ManipulationType
from sqlalchemy.orm import Session
from preprocessor import TextPreprocessor

def get_bio_tags(text: str, annotations: List[Annotation], types_dict: Dict[int, str]) -> List[Dict]:
    """
    Преобразует аннотации со смещениями (offsets) в BIO-разметку на уровне токенов.
    Исправленная версия: корректно обрабатывает частичные перекрытия и гарантирует
    наличие B-тега в начале каждого спана.
    """
    tokens_data = TextPreprocessor.tokenize(text)
    
    # Сортируем аннотации по start_offset для предсказуемости
    sorted_annotations = sorted(annotations, key=lambda a: a.start_offset)
    
    result = []
    for token in tokens_data:
        t_start = token["start_char"]
        t_end = token["end_char"]
        token_text = token["text"]
        
        tag = "O"
        
        for ann in sorted_annotations:
            a_start = ann.start_offset
            a_end = ann.end_offset
            
            # Проверяем ЛЮБОЕ перекрытие между токеном и аннотацией
            # (а не строгое вхождение, как раньше)
            if t_start < a_end and t_end > a_start:
                type_code = types_dict.get(ann.type_id, "MANIP")
                
                # Определяем, является ли этот токен ПЕРВЫМ в спане
                # Токен — начало спана, если его начало <= начала аннотации
                # ИЛИ если предыдущий токен не перекрывался с этой аннотацией
                is_first_token = (t_start <= a_start)
                
                if not is_first_token and result:
                    # Проверяем, был ли предыдущий токен помечен B- или I- для этого же типа
                    prev_tag = result[-1]["bio_tag"]
                    is_first_token = prev_tag not in (f"B-{type_code}", f"I-{type_code}")
                
                if is_first_token:
                    tag = f"B-{type_code}"
                else:
                    tag = f"I-{type_code}"
                break  # Один токен — одна аннотация (приоритет у первой по позиции)
                
        result.append({
            "token": token_text,
            "lemma": token["lemma"],
            "bio_tag": tag
        })
        
    return result

def export_to_conllu(doc: Document, annotations: List[Annotation], types_dict: Dict[int, str]) -> str:
    """
    Формирует строку в формате, совместимом с CoNLL-U (упрощенный вариант для NLP).
    Формат: ID \t FORM \t LEMMA \t UPOS \t XPOS \t FEATS \t HEAD \t DEPREL \t DEPS \t MISC (BIO-тег)
    """
    tokens_bio = get_bio_tags(doc.normalized_text, annotations, types_dict)
    lines = [f"# text = {doc.normalized_text}"]
    
    for i, item in enumerate(tokens_bio, start=1):
        # Заполняем фиктивные значения для UPOS, HEAD и т.д., чтобы формат был валидным CoNLL-U
        # Реальный POS-тег можно взять из item, если доработать preprocessor
        line = f"{i}\t{item['token']}\t{item['lemma']}\t_\t_\t_\t_\t_\t_\t{item['bio_tag']}"
        lines.append(line)
        
    lines.append("") # Пустая строка между предложениями/документами
    return "\n".join(lines)

def export_to_jsonl(doc: Document, annotations: List[Annotation], types_dict: Dict[int, str]) -> Dict:
    """
    Формирует словарь для записи в JSONL (удобно для Hugging Face datasets).
    """
    tokens_bio = get_bio_tags(doc.normalized_text, annotations, types_dict)
    
    return {
        "id": doc.doc_id,
        "domain": doc.domain,
        "source_url": doc.source_url,
        "tokens": [item["token"] for item in tokens_bio],
        "ner_tags": [item["bio_tag"] for item in tokens_bio],
        "full_text": doc.normalized_text
    }

def generate_full_corpus_export(db: Session, format: str = "conllu") -> str:
    """
    Генерирует экспорт всего корпуса.
    """
    docs = db.query(Document).all()
    
    # Загружаем справочник типов манипуляций в память для быстрого доступа
    types = db.query(ManipulationType).all()
    types_dict = {t.type_id: t.code for t in types}
    
    if format == "conllu":
        output_parts = []
        for doc in docs:
            annotations = db.query(Annotation).filter(Annotation.doc_id == doc.doc_id).all()
            output_parts.append(export_to_conllu(doc, annotations, types_dict))
        return "\n".join(output_parts)
        
    elif format == "jsonl":
        output_parts = []
        for doc in docs:
            annotations = db.query(Annotation).filter(Annotation.doc_id == doc.doc_id).all()
            output_parts.append(json.dumps(export_to_jsonl(doc, annotations, types_dict), ensure_ascii=False))
        return "\n".join(output_parts)
        
    else:
        raise ValueError(f"Неподдерживаемый формат экспорта: {format}")