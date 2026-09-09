"""
Модуль аналитики для системы ManipCorpus.
Реализует расчет межаннотаторской согласованности (Cohen's Kappa).
"""
import math
from sklearn.metrics import cohen_kappa_score
from typing import List, Dict
from models import Annotation

def calculate_cohens_kappa(
    annotations_user1: List[Annotation], 
    annotations_user2: List[Annotation],
    tolerance: int = 5
) -> float:
    """
    Расчет коэффициента Каппа Коэна для двух аннотаторов на одном документе.
    """
    all_types = set(a.type_id for a in annotations_user1) | set(a.type_id for a in annotations_user2)
    
    y_true = []
    y_pred = []
    
    for m_type in all_types:
        found_u1 = any(a.type_id == m_type for a in annotations_user1)
        found_u2 = any(a.type_id == m_type for a in annotations_user2)
        
        y_true.append(1 if found_u1 else 0)
        y_pred.append(1 if found_u2 else 0)
        
    if not y_true or (sum(y_true) == 0 and sum(y_pred) == 0):
        return 1.0
        
    kappa = cohen_kappa_score(y_true, y_pred)
    
    # === КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ===
    # Если scikit-learn вернул NaN (из-за отсутствия вариативности в классах),
    # проверяем, совпадают ли массивы полностью. Если да, это идеальное согласие (1.0).
    if math.isnan(kappa):
        kappa = 1.0 if y_true == y_pred else 0.0
        
    return round(float(kappa), 4)


def get_agreement_report(doc_id: int, db_session) -> Dict:
    """
    Формирует отчет о согласованности для конкретного документа.
    """
    annotations = db_session.query(Annotation).filter(Annotation.doc_id == doc_id).all()
    
    if not annotations:
        return {"status": "no_data", "message": "Аннотации для данного документа отсутствуют"}
        
    user_ids = list(set(a.user_id for a in annotations))
    
    if len(user_ids) < 2:
        return {
            "status": "insufficient_annotators", 
            "message": "Для расчета Каппы Коэна требуется разметка минимум от 2 аннотаторов",
            "annotators_count": len(user_ids)
        }
        
    u1_annotations = [a for a in annotations if a.user_id == user_ids[0]]
    u2_annotations = [a for a in annotations if a.user_id == user_ids[1]]
    
    kappa = calculate_cohens_kappa(u1_annotations, u2_annotations)
    
    if kappa < 0:
        interpretation = "Отсутствие согласия"
    elif 0.0 <= kappa < 0.20:
        interpretation = "Незначительное согласие"
    elif 0.21 <= kappa < 0.40:
        interpretation = "Умеренное согласие"
    elif 0.41 <= kappa < 0.60:
        interpretation = "Среднее согласие"
    elif 0.61 <= kappa < 0.80:
        interpretation = "Существенное согласие"
    else:
        interpretation = "Почти полное согласие"
        
    return {
        "status": "success",
        "doc_id": doc_id,
        "annotator_1": user_ids[0],
        "annotator_2": user_ids[1],
        "cohens_kappa": kappa,
        "interpretation": interpretation,
        "total_annotations": len(annotations)
    }