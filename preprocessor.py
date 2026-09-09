"""
Модуль предобработки текстов для системы ManipCorpus.
Реализует: очистку HTML, нормализацию, токенизацию, сегментацию.
"""
import re
import spacy
from bs4 import BeautifulSoup
from typing import List, Dict

# Загрузка русской модели spaCy (один раз при старте)
try:
    nlp = spacy.load("ru_core_news_sm")
except OSError:
    raise RuntimeError(
        "Модель ru_core_news_sm не найдена. "
        "Выполните: python -m spacy download ru_core_news_sm"
    )


class TextPreprocessor:
    """Класс для предобработки текстов перед загрузкой в корпус."""
    
    @staticmethod
    def clean_html(text: str) -> str:
        """Удаление HTML-разметки."""
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ")
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Нормализация: удаление лишних пробелов, спецсимволов, приведение к единому формату."""
        # Удаление множественных пробелов
        text = re.sub(r"\s+", " ", text)
        # Удаление управляющих символов
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Удаление URL (сохраняем отдельно как метаданные при необходимости)
        text = re.sub(r"http\S+|www\.\S+", "", text)
        return text.strip()
    
    @staticmethod
    def segment_sentences(text: str) -> List[str]:
        """Сегментация текста на предложения с помощью spaCy."""
        doc = nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    
    @staticmethod
    def tokenize(text: str) -> List[Dict]:
        """Токенизация с лингвистическими атрибутами (лемма, POS-тег)."""
        doc = nlp(text)
        return [
            {
                "text": token.text,
                "lemma": token.lemma_,
                "pos": token.pos_,
                "start_char": token.idx,
                "end_char": token.idx + len(token.text),
            }
            for token in doc
            if not token.is_space
        ]
    
    @classmethod
    def full_pipeline(cls, raw_text: str) -> Dict:
        """
        Полный пайплайн предобработки.
        Возвращает словарь с нормализованным текстом, предложениями и токенами.
        """
        # 1. Очистка HTML
        text_no_html = cls.clean_html(raw_text)
        # 2. Нормализация
        normalized = cls.normalize_text(text_no_html)
        # 3. Сегментация
        sentences = cls.segment_sentences(normalized)
        # 4. Токенизация (только для нормализованного текста)
        tokens = cls.tokenize(normalized)
        
        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "sentences": sentences,
            "tokens": tokens,
            "char_count": len(normalized),
            "sentence_count": len(sentences),
            "token_count": len(tokens),
        }