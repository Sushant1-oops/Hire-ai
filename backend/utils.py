"""
Utility functions for the HR SaaS platform.
Includes logging, caching, text processing, and helper functions.
"""

import os
import json
import logging
import pickle
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# ==================== LOGGING ====================
def setup_logging(name: str = "ai_hr_saas") -> logging.Logger:
    """Setup logging configuration."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # File handler
    fh = logging.FileHandler(f"logs/{name}_{datetime.now().strftime('%Y%m%d')}.log")
    fh.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


logger = setup_logging()


# ==================== FILE OPERATIONS ====================
def ensure_directory(directory: str) -> Path:
    """Ensure a directory exists, create if not."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_pickle(data: Any, filepath: str) -> bool:
    """Save data using pickle."""
    try:
        ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✓ Saved pickle to {filepath}")
        return True
    except Exception as e:
        logger.error(f"✗ Error saving pickle to {filepath}: {str(e)}")
        return False


def load_pickle(filepath: str) -> Optional[Any]:
    """Load data from pickle file."""
    try:
        if not os.path.exists(filepath):
            logger.warning(f"Pickle file not found: {filepath}")
            return None
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        logger.info(f"✓ Loaded pickle from {filepath}")
        return data
    except Exception as e:
        logger.error(f"✗ Error loading pickle from {filepath}: {str(e)}")
        return None


def save_json(data: Any, filepath: str) -> bool:
    """Save data as JSON."""
    try:
        ensure_directory(os.path.dirname(filepath))
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"✓ Saved JSON to {filepath}")
        return True
    except Exception as e:
        logger.error(f"✗ Error saving JSON to {filepath}: {str(e)}")
        return False


def load_json(filepath: str) -> Optional[Dict]:
    """Load data from JSON file."""
    try:
        if not os.path.exists(filepath):
            logger.warning(f"JSON file not found: {filepath}")
            return None
        with open(filepath, 'r') as f:
            data = json.load(f)
        logger.info(f"✓ Loaded JSON from {filepath}")
        return data
    except Exception as e:
        logger.error(f"✗ Error loading JSON from {filepath}: {str(e)}")
        return None


# ==================== COMPREHENSIVE SKILLS DATABASE ====================
# Organized by category for maintainability.  Each entry is the canonical
# display name.  During matching we normalise both the resume text and the
# skill name to lowercase so casing doesn't matter.

SKILLS_DATABASE = {
    # ── Programming Languages ──────────────────────────────────────
    "Python", "JavaScript", "TypeScript", "Java", "C", "C++", "C#",
    "Go", "Golang", "Rust", "PHP", "Ruby", "Perl", "Scala", "Kotlin",
    "Swift", "Objective-C", "Dart", "R", "MATLAB", "Julia", "Lua",
    "Haskell", "Elixir", "Erlang", "Clojure", "F#", "Assembly",
    "Shell Scripting", "Bash", "PowerShell", "VBA", "COBOL", "Fortran",
    "Groovy", "Visual Basic", "Solidity",

    # ── Web Frontend ───────────────────────────────────────────────
    "HTML", "CSS", "React", "React.js", "Vue", "Vue.js", "Angular",
    "Svelte", "Next.js", "Nuxt.js", "Gatsby", "Remix", "Astro",
    "jQuery", "Bootstrap", "Tailwind CSS", "Material UI", "Chakra UI",
    "Sass", "SCSS", "Less", "Styled Components", "Webpack", "Vite",
    "Babel", "Redux", "MobX", "Zustand", "Context API",

    # ── Web Backend ────────────────────────────────────────────────
    "Node.js", "Express", "Express.js", "Fastify", "NestJS", "Koa",
    "Django", "Flask", "FastAPI", "Spring Boot", "Spring", "Quarkus",
    "Ruby on Rails", "Rails", "Laravel", "Symfony", "CodeIgniter",
    "ASP.NET", ".NET", ".NET Core", "Gin", "Echo", "Fiber",
    "Phoenix", "Actix", "Rocket",

    # ── Mobile Development ─────────────────────────────────────────
    "React Native", "Flutter", "SwiftUI", "Jetpack Compose",
    "Xamarin", "Ionic", "Cordova", "Capacitor", "Android SDK",
    "iOS Development", "Android Development", "Mobile Development",

    # ── Databases ──────────────────────────────────────────────────
    "SQL", "MySQL", "PostgreSQL", "SQLite", "MariaDB", "Oracle DB",
    "Microsoft SQL Server", "MongoDB", "Cassandra", "CouchDB",
    "DynamoDB", "Redis", "Memcached", "Neo4j", "ArangoDB",
    "InfluxDB", "TimescaleDB", "CockroachDB", "Supabase",
    "Firebase", "Firestore", "Elasticsearch", "OpenSearch",
    "Pinecone", "Weaviate", "Milvus", "FAISS",

    # ── Cloud & DevOps ─────────────────────────────────────────────
    "AWS", "Amazon Web Services", "Azure", "Microsoft Azure",
    "GCP", "Google Cloud", "Google Cloud Platform",
    "Docker", "Kubernetes", "K8s", "Terraform", "Ansible",
    "Puppet", "Chef", "Vagrant", "Packer", "Helm",
    "CI/CD", "Jenkins", "GitHub Actions", "GitLab CI",
    "CircleCI", "Travis CI", "ArgoCD", "Spinnaker",
    "CloudFormation", "Pulumi", "Serverless",
    "AWS Lambda", "Azure Functions", "Cloud Functions",
    "ECS", "EKS", "AKS", "GKE", "Fargate",
    "S3", "EC2", "RDS", "CloudFront", "Route 53",
    "Nginx", "Apache", "Caddy", "HAProxy",
    "Linux", "Ubuntu", "CentOS", "RHEL", "Windows Server",

    # ── Data Engineering & Analytics ───────────────────────────────
    "Apache Spark", "Spark", "Hadoop", "Hive", "Pig",
    "Apache Kafka", "Kafka", "RabbitMQ", "Apache Flink",
    "Apache Airflow", "Airflow", "Luigi", "Prefect", "Dagster",
    "dbt", "Snowflake", "BigQuery", "Redshift", "Databricks",
    "Apache Beam", "Presto", "Trino", "Delta Lake",
    "ETL", "Data Warehousing", "Data Modeling", "Data Pipeline",
    "Pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn",
    "Plotly", "Tableau", "Power BI", "Looker", "Metabase",
    "Excel", "Google Sheets", "Data Visualization",

    # ── AI / ML / Deep Learning ────────────────────────────────────
    "Machine Learning", "Deep Learning", "Neural Networks", "CNN", "RNN", "LSTM", "GRU", "ANN",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "sklearn",
    "XGBoost", "LightGBM", "CatBoost", "Random Forest",
    "Natural Language Processing", "NLP", "Computer Vision",
    "OpenCV", "YOLO", "Object Detection", "Image Classification",
    "Hugging Face", "Transformers", "BERT", "GPT",
    "LLM", "Large Language Models", "Prompt Engineering",
    "RAG", "Retrieval Augmented Generation",
    "Langchain", "LlamaIndex", "Vector Databases",
    "Reinforcement Learning", "GANs",
    "MLOps", "MLflow", "Kubeflow", "SageMaker", "Vertex AI",
    "Feature Engineering", "Model Deployment", "A/B Testing",
    "Recommendation Systems", "Time Series", "Forecasting",
    "Statistical Analysis", "Bayesian Methods",
    "Sentence Transformers", "Embeddings", "Fine-tuning",
    "ONNX", "TensorRT", "Triton",

    # ── Testing & QA ───────────────────────────────────────────────
    "Unit Testing", "Integration Testing", "E2E Testing",
    "Jest", "Mocha", "Chai", "Cypress", "Playwright", "Selenium",
    "Pytest", "JUnit", "TestNG", "RSpec",
    "TDD", "BDD", "Test Automation", "Load Testing",
    "JMeter", "Locust", "k6", "Postman", "SoapUI",

    # ── API & Architecture ─────────────────────────────────────────
    "REST API", "RESTful", "GraphQL", "gRPC", "WebSocket",
    "Microservices", "Monolith", "Event-Driven Architecture",
    "CQRS", "Domain-Driven Design", "DDD",
    "System Design", "Software Architecture", "Design Patterns",
    "SOLID Principles", "Clean Architecture", "Hexagonal Architecture",
    "API Gateway", "Service Mesh", "Istio", "Envoy",
    "OAuth", "OAuth2", "JWT", "SAML", "OpenID Connect",
    "API Design", "Swagger", "OpenAPI",

    # ── Version Control & Collaboration ────────────────────────────
    "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
    "Code Review", "Pull Requests", "Branching Strategies",

    # ── Project Management & Methodology ───────────────────────────
    "Agile", "Scrum", "Kanban", "Lean", "SAFe",
    "Jira", "Confluence", "Trello", "Asana", "Monday.com",
    "Project Management", "Product Management", "Sprint Planning",
    "Waterfall", "Six Sigma",

    # ── Security ───────────────────────────────────────────────────
    "Cybersecurity", "Information Security", "Network Security",
    "Penetration Testing", "Vulnerability Assessment",
    "OWASP", "Encryption", "SSL/TLS", "PKI",
    "IAM", "RBAC", "Zero Trust", "SOC 2", "GDPR", "HIPAA",
    "Firewalls", "IDS/IPS", "SIEM", "Security Auditing",
    "Authentication", "Authorization",

    # ── Soft Skills ────────────────────────────────────────────────
    "Communication", "Leadership", "Teamwork", "Problem Solving",
    "Critical Thinking", "Time Management", "Adaptability",
    "Creativity", "Negotiation", "Presentation Skills",
    "Mentoring", "Coaching", "Decision Making",
    "Conflict Resolution", "Stakeholder Management",
    "Cross-functional Collaboration", "Strategic Planning",
    "Public Speaking", "Technical Writing", "Documentation",

    # ── Domain Skills ──────────────────────────────────────────────
    "FinTech", "Healthcare IT", "E-commerce", "EdTech",
    "SaaS", "B2B", "B2C", "ERP", "CRM", "Salesforce",
    "SAP", "Blockchain", "Web3", "DeFi", "NFT",
    "IoT", "Embedded Systems", "Robotics", "AR/VR",
    "Game Development", "Unity", "Unreal Engine",
    "GIS", "Geospatial", "CAD", "3D Modeling",
}

# Build a lowercase lookup map: lowercase_skill -> canonical_name
_SKILLS_LOWER_MAP = {s.lower(): s for s in SKILLS_DATABASE}

# Multi-word skills sorted longest-first so we match "React Native" before "React"
_SKILLS_BY_LENGTH = sorted(SKILLS_DATABASE, key=lambda s: -len(s))


def extract_skills_from_text(text: str) -> List[str]:
    """
    Extract skills from resume text using comprehensive keyword matching.
    Uses substring matching with word-boundary awareness for accuracy.
    """
    if not text:
        return []

    text_lower = text.lower()
    found_skills = set()

    for skill in _SKILLS_BY_LENGTH:
        skill_lower = skill.lower()

        # Skip if we already found a longer variant that contains this skill
        # e.g. if "React Native" matched, don't also add "React"
        already_covered = False
        for found in list(found_skills):
            if skill_lower in found.lower() and skill_lower != found.lower():
                already_covered = True
                break
        if already_covered:
            continue

        # For single-char skills like "C" or "R", require word boundaries
        if len(skill_lower) <= 2:
            pattern = r'\b' + re.escape(skill_lower) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.add(skill)
        else:
            # For multi-char skills, do substring search
            if skill_lower in text_lower:
                found_skills.add(skill)

    # Normalize: if both "React.js" and "React" found, keep only "React"
    # (the canonical short form)
    normalized = set()
    for skill in found_skills:
        base = skill.replace(".js", "").replace("JS", "").strip()
        # Check if the base form is also in found_skills
        if base != skill and base in found_skills:
            continue  # Skip the .js variant
        normalized.add(skill)

    return sorted(normalized)


def extract_experience_years(text: str) -> Optional[float]:
    """
    Extract years of experience from resume text.
    Handles multiple formats including date ranges.
    """
    if not text:
        return None

    text_lower = text.lower()

    # Pattern 1: Explicit statements like "5+ years of experience"
    patterns = [
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?(?:work\s+)?experience',
        r'(\d+)\s*\+?\s*yrs?\s+(?:of\s+)?(?:professional\s+)?experience',
        r'total\s+(?:work\s+)?experience\s*:?\s*(\d+)\s*\+?\s*years?',
        r'experience\s*:?\s*(\d+)\s*\+?\s*years?',
        r'(\d+)\s*\+?\s*years?\s+(?:in\s+)?(?:software|development|engineering|it|programming)',
        r'over\s+(\d+)\s+years?',
        r'more\s+than\s+(\d+)\s+years?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                years = float(match.group(1))
                if 0 < years <= 50:  # Sanity check
                    return years
            except (ValueError, IndexError):
                continue

    # Pattern 2: Calculate from date ranges like "2019 - 2024" or "Jan 2019 – Present"
    date_range_pattern = r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*(\d{4})\s*[-–—to]+\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*(\d{4})|present|current|now|ongoing)'
    ranges = re.findall(date_range_pattern, text_lower)

    if ranges:
        current_year = datetime.now().year
        min_year = current_year
        max_year = 0

        for start_str, end_str in ranges:
            try:
                start_year = int(start_str)
                end_year = int(end_str) if end_str else current_year

                if 1970 <= start_year <= current_year:
                    min_year = min(min_year, start_year)
                if end_year == 0 or end_year > current_year:
                    end_year = current_year
                max_year = max(max_year, end_year)
            except ValueError:
                continue

        if max_year > min_year:
            calculated = float(max_year - min_year)
            if 0 < calculated <= 50:
                return calculated

    # Pattern 3: Word-based like "five years"
    word_numbers = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20,
    }
    for word, num in word_numbers.items():
        pattern = rf'{word}\s+years?\s+(?:of\s+)?experience'
        if re.search(pattern, text_lower):
            return float(num)

    return None


def extract_education(text: str) -> List[Dict]:
    """Extract education information from resume text."""
    if not text:
        return []

    education = []
    text_lower = text.lower()

    degree_patterns = [
        (r'\b(?:ph\.?d|doctorate|doctor of philosophy)\b', "PhD"),
        (r'\b(?:m\.?b\.?a)\b', "MBA"),
        (r'\b(?:m\.?s\.?|master(?:\'?s)?(?:\s+of)?\s+(?:science|engineering|technology|arts|computer))\b', "Master's"),
        (r'\b(?:m\.?tech|m\.?\s*tech)\b', "M.Tech"),
        (r'\b(?:m\.?e\.?|master(?:\'?s)?\s+(?:of\s+)?engineering)\b', "M.E."),
        (r'\b(?:m\.?c\.?a)\b', "MCA"),
        (r'\b(?:b\.?tech|b\.?\s*tech)\b', "B.Tech"),
        (r'\b(?:b\.?e\.?|bachelor(?:\'?s)?\s+(?:of\s+)?engineering)\b', "B.E."),
        (r'\b(?:b\.?s\.?|bachelor(?:\'?s)?(?:\s+of)?\s+(?:science|engineering|technology|arts|computer))\b', "Bachelor's"),
        (r'\b(?:b\.?c\.?a)\b', "BCA"),
        (r'\b(?:b\.?b\.?a)\b', "BBA"),
        (r'\b(?:b\.?com|bachelor(?:\'?s)?\s+(?:of\s+)?commerce)\b', "B.Com"),
        (r'\b(?:associate(?:\'?s)?\s+degree)\b', "Associate's"),
        (r'\b(?:diploma)\b', "Diploma"),
        (r'\b(?:high\s+school|12th|hsc|intermediate)\b', "High School"),
        (r'\b(?:10th|ssc|matriculation)\b', "10th Grade"),
    ]

    for pattern, degree_name in degree_patterns:
        if re.search(pattern, text_lower):
            education.append({"degree": degree_name})

    return education


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\-.,@+()/:;]', '', text)
    return text.strip()


# ==================== VALIDATION ====================
def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str) -> bool:
    """Validate phone number format."""
    # Accept various phone formats including international
    pattern = r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{3,5}[-\s\.]?[0-9]{3,8}$'
    return re.match(pattern, phone) is not None


# ==================== CACHING ====================
class SimpleCache:
    """Simple in-memory cache with expiration."""

    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def set(self, key: str, value: Any) -> None:
        """Set cache value."""
        self.cache[key] = {
            'value': value,
            'timestamp': datetime.utcnow(),
        }
        logger.debug(f"Cache SET: {key}")

    def get(self, key: str) -> Optional[Any]:
        """Get cache value if exists and not expired."""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        age = (datetime.utcnow() - entry['timestamp']).total_seconds()

        if age > self.ttl_seconds:
            del self.cache[key]
            logger.debug(f"Cache EXPIRED: {key}")
            return None

        logger.debug(f"Cache HIT: {key}")
        return entry['value']

    def delete(self, key: str) -> None:
        """Delete cache entry."""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache DELETE: {key}")

    def clear(self) -> None:
        """Clear all cache."""
        self.cache.clear()
        logger.debug("Cache CLEARED")

    def get_size(self) -> int:
        """Get number of items in cache."""
        return len(self.cache)


# Global cache instance
embedding_cache = SimpleCache(ttl_seconds=3600 * 24)  # 24 hour TTL


# ==================== JSON HELPERS ====================
def safe_json_loads(json_str: str, default=None) -> Any:
    """Safely load JSON string."""
    try:
        return json.loads(json_str) if json_str else default
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default=None) -> str:
    """Safely dump object to JSON string."""
    try:
        return json.dumps(obj, default=str)
    except TypeError:
        return default or "[]"


# ==================== ERROR RESPONSES ====================
def error_response(code: int, message: str, details: Optional[str] = None) -> Dict:
    """Generate standard error response."""
    return {
        "error": True,
        "code": code,
        "message": message,
        "details": details,
        "timestamp": datetime.utcnow().isoformat(),
    }


def success_response(data: Any = None, message: str = "Success") -> Dict:
    """Generate standard success response."""
    return {
        "error": False,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }
