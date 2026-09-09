"""
Модуль импорта текстов в систему ManipCorpus.
Поддерживает: TXT, CSV, JSON, загрузку по URL.
"""
import csv
import json
import os
import requests
from typing import List, Dict
from preprocessor import TextPreprocessor


class TextImporter:
    """Класс для импорта текстов из различных источников."""
    
    @staticmethod
    def import_from_txt(file_path: str) -> List[Dict]:
        """Импорт из TXT-файла (один документ = один файл)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        
        processed = TextPreprocessor.full_pipeline(raw_text)
        return [{
            "raw_text": processed["raw_text"],
            "normalized_text": processed["normalized_text"],
            "source_url": None,
            "domain": "unknown",
            "metadata": {
                "source_file": os.path.basename(file_path),
                "stats": {
                    "char_count": processed["char_count"],
                    "sentence_count": processed["sentence_count"],
                    "token_count": processed["token_count"],
                }
            }
        }]
    
    @staticmethod
    def import_from_csv(file_path: str, text_column: str = "text", 
                        url_column: str = "url",
                        domain_column: str = "domain") -> List[Dict]:
        """
        Импорт из CSV-файла. 
        Ожидается колонка с текстом и опционально URL и домен.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        documents = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_text = row.get(text_column, "")
                if not raw_text.strip():
                    continue
                
                processed = TextPreprocessor.full_pipeline(raw_text)
                documents.append({
                    "raw_text": processed["raw_text"],
                    "normalized_text": processed["normalized_text"],
                    "source_url": row.get(url_column),
                    "domain": row.get(domain_column, "unknown"),
                    "metadata": {
                        "source_file": os.path.basename(file_path),
                        "stats": {
                            "char_count": processed["char_count"],
                            "sentence_count": processed["sentence_count"],
                            "token_count": processed["token_count"],
                        }
                    }
                })
        return documents
    
    @staticmethod
    def import_from_json(file_path: str) -> List[Dict]:
        """Импорт из JSON (ожидается список словарей с полем 'text')."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        documents = []
        for item in data:
            raw_text = item.get("text", "")
            if not raw_text.strip():
                continue
            
            processed = TextPreprocessor.full_pipeline(raw_text)
            documents.append({
                "raw_text": processed["raw_text"],
                "normalized_text": processed["normalized_text"],
                "source_url": item.get("url"),
                "domain": item.get("domain", "unknown"),
                "metadata": {
                    "source_file": os.path.basename(file_path),
                    "stats": {
                        "char_count": processed["char_count"],
                        "sentence_count": processed["sentence_count"],
                        "token_count": processed["token_count"],
                    }
                }
            })
        return documents
    
    @staticmethod
    def import_from_url(url: str, domain: str = "web") -> Dict:
        """Загрузка и обработка текста по URL."""
        try:
            response = requests.get(url, timeout=10, headers={
                "User-Agent": "ManipCorpus/1.0 (Academic Research)"
            })
            response.raise_for_status()
            
            # Пытаемся извлечь текст из HTML
            raw_text = response.text
            processed = TextPreprocessor.full_pipeline(raw_text)
            
            return {
                "raw_text": processed["raw_text"],
                "normalized_text": processed["normalized_text"],
                "source_url": url,
                "domain": domain,
                "metadata": {
                    "stats": {
                        "char_count": processed["char_count"],
                        "sentence_count": processed["sentence_count"],
                        "token_count": processed["token_count"],
                    }
                }
            }
        except requests.RequestException as e:
            raise RuntimeError(f"Ошибка загрузки URL {url}: {e}")