
import os
import json
import logging
import pickle
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from skills_extractor import SkillsExtractor

def setup_logging(name: str = "ai_hr_saas") -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers: return logger
    fh = logging.FileHandler(f"logs/{name}_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    import sys
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

logger = setup_logging()

def ensure_directory(directory: str) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path

def save_pickle(data: Any, filepath: str) -> bool:
    try:
        ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'wb') as f: pickle.dump(data, f)
        return True
    except Exception: return False

def load_pickle(filepath: str) -> Optional[Any]:
    try:
        if not os.path.exists(filepath): return None
        with open(filepath, 'rb') as f: return pickle.load(f)
    except Exception: return None

def extract_skills_from_text(text: str) -> List[str]:
    return SkillsExtractor().extract(text)

def extract_experience_years(text: str) -> Optional[float]:
    if not text: return None
    text_lower = text.lower()

    patterns = [
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?(?:work\s+)?experience',
        r'(\d+)\s*\+?\s*yrs?\s+(?:of\s+)?(?:professional\s+)?experience',
        r'total\s+(?:work\s+)?experience\s*:?\s*(\d+)\s*\+?\s*years?',
        r'experience\s*:?\s*(\d+)\s*\+?\s*years?',
        r'(\d+)\s*\+?\s*years?\s+(?:in\s+)?(?:software|development|engineering|it|programming)',
        r'over\s+(\d+)\s+years?', r'more\s+than\s+(\d+)\s+years?'
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                years = float(match.group(1))
                if 0 < years <= 50: return years
            except: continue

    date_range_pattern = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*(\d{4})\s*[-–—to]+\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*(\d{4})|present|current|now|ongoing)'
    ranges = re.findall(date_range_pattern, text_lower)
    
    if ranges:
        years_set = set()
        current_year = datetime.now().year
        for start_str, end_str in ranges:
            try:
                start_year = int(start_str)
                end_year = int(end_str) if end_str else current_year
                if end_year > current_year: end_year = current_year
                if 1970 <= start_year <= current_year and start_year <= end_year:
                    for y in range(start_year, end_year + 1): years_set.add(y)
            except: continue
        if len(years_set) > 0: return float(len(years_set))

    word_numbers = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
    for word, num in word_numbers.items():
        if re.search(rf'{word}\s+years?\s+(?:of\s+)?experience', text_lower): return float(num)
    return None

def extract_education(text: str) -> List[Dict]:
    if not text: return []
    education = []
    text_lower = text.lower()
    degree_patterns = [
        (r'\b(?:ph\.?d|doctorate)\b', "PhD"), (r'\b(?:m\.?b\.?a)\b', "MBA"),
        (r'\b(?:m\.?s\.?|master(?:\'?s)?)\b', "Master's"), (r'\b(?:m\.?tech)\b', "M.Tech"),
        (r'\b(?:b\.?tech)\b', "B.Tech"), (r'\b(?:b\.?e\.?|bachelor(?:\'?s)?)\b', "Bachelor's"),
        (r'\b(?:b\.?c\.?a)\b', "BCA"), (r'\b(?:b\.?b\.?a)\b', "BBA"),
        (r'\b(?:b\.?com)\b', "B.Com"), (r'\b(?:associate(?:\'?s)?)\b', "Associate's"),
        (r'\b(?:diploma)\b', "Diploma"), (r'\b(?:high\s+school|12th)\b', "High School")
    ]
    for pattern, degree_name in degree_patterns:
        if re.search(pattern, text_lower): education.append({"degree": degree_name})
    return education

def clean_text(text: str) -> str:
    text = ' '.join(text.split())
    text = re.sub(r'[^\w\s\-.,@+()/:;]', '', text)
    return text.strip()

def validate_email(email: str) -> bool:
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

def safe_json_loads(json_str: str, default=None) -> Any:
    try: return json.loads(json_str) if json_str else default
    except: return default

def safe_json_dumps(obj: Any, default=None) -> str:
    try: return json.dumps(obj, default=str)
    except: return default or "[]"

def error_response(code: int, message: str, details: Optional[str] = None) -> Dict:
    return {"error": True, "code": code, "message": message, "details": details, "timestamp": datetime.utcnow().isoformat()}

def success_response(data: Any = None, message: str = "Success") -> Dict:
    return {"error": False, "message": message, "data": data, "timestamp": datetime.utcnow().isoformat()}


class SimpleCache:
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def set(self, key: str, value: Any) -> None:
        self.cache[key] = {'value': value, 'timestamp': datetime.utcnow()}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache: return None
        entry = self.cache[key]
        age = (datetime.utcnow() - entry['timestamp']).total_seconds()
        if age > self.ttl_seconds:
            del self.cache[key]
            return None
        return entry['value']

    def delete(self, key: str) -> None:
        if key in self.cache: del self.cache[key]

    def clear(self) -> None:
        self.cache.clear()

    def get_size(self) -> int:
        return len(self.cache)