# skills_extractor.py
import re
from typing import List

class SkillsExtractor:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SkillsExtractor, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.skill_map = {
            "Python": ["Python3", "Python 3", "Python2", "Py3"],
            "JavaScript": ["JS", "ECMAScript", "ES6", "ES2015"],
            "TypeScript": ["TS"],
            "Java": ["Java SE", "Java EE", "Java 8", "Java 11", "Java 17"],
            "C": ["C Lang", "C programming", "C language"],
            "C++": ["CPP", "C plus plus"],
            "C#": ["CSharp", "C Sharp"],
            "Golang": ["Go Lang", "Go language", "Golang"],
            "Rust": [],
            "PHP": ["PHP7", "PHP8"],
            "Ruby": [],
            "Swift": [],
            "Kotlin": [],
            "Scala": [],
            "R": ["R Lang", "R programming", "R language"],
            "Dart": [],
            "React": ["React.js", "Reactjs", "React JS"],
            "Vue": ["Vue.js", "Vuejs", "Vue JS"],
            "Angular": ["AngularJS", "Angular.js", "Angular 2"],
            "Svelte": [],
            "Next.js": ["Nextjs", "Next js"],
            "Nuxt.js": ["Nuxtjs", "Nuxt js"],
            "Redux": [],
            "HTML": ["HTML5"],
            "CSS": ["CSS3"],
            "Tailwind CSS": ["Tailwindcss", "Tailwind"],
            "Sass": ["SCSS"],
            "Node.js": ["Nodejs", "Node js", "Node"],
            "Express": ["Express.js", "Expressjs"],
            "Django": [],
            "Flask": [],
            "FastAPI": ["Fast API"],
            "Spring Boot": ["SpringBoot", "Spring-Boot"],
            "Ruby on Rails": ["Rails", "RoR"],
            "Laravel": [],
            "ASP.NET": ["ASPNET", "ASP .NET"],
            ".NET Core": [".NET", "DotNet"],
            "NestJS": ["Nest JS"],
            "React Native": ["ReactNative"],
            "Flutter": [],
            "SQL": ["Structured Query Language"],
            "MySQL": [],
            "PostgreSQL": ["Postgres", "psql"],
            "MongoDB": ["Mongo"],
            "Redis": [],
            "Cassandra": [],
            "DynamoDB": [],
            "Neo4j": [],
            "Elasticsearch": ["ES"],
            "Oracle DB": ["Oracle Database"],
            "Microsoft SQL Server": ["MSSQL", "MS SQL"],
            "AWS": ["Amazon Web Services"],
            "Azure": ["Microsoft Azure"],
            "GCP": ["Google Cloud Platform", "Google Cloud"],
            "Docker": ["Containerization"],
            "Kubernetes": ["K8s"],
            "Terraform": [],
            "Ansible": [],
            "Jenkins": [],
            "GitHub Actions": [],
            "GitLab CI": [],
            "CI/CD": ["CICD", "CI CD"],
            "Nginx": [],
            "Linux": ["Ubuntu", "CentOS", "RHEL"],
            "Apache Spark": ["Spark"],
            "Hadoop": [],
            "Kafka": ["Apache Kafka"],
            "Airflow": ["Apache Airflow"],
            "Snowflake": [],
            "BigQuery": [],
            "Redshift": [],
            "Pandas": [],
            "NumPy": [],
            "Machine Learning": ["ML"],
            "Deep Learning": ["DL"],
            "TensorFlow": ["TF"],
            "PyTorch": ["Torch"],
            "Keras": [],
            "Scikit-learn": ["sklearn", "Scikit learn"],
            "NLP": ["Natural Language Processing"],
            "Computer Vision": ["CV"],
            "OpenCV": [],
            "Hugging Face": [],
            "LLM": ["Large Language Models"],
            "Langchain": [],
            "Git": ["GitHub", "GitLab", "Bitbucket"],
            "GraphQL": ["Graph QL"],
            "REST API": ["RESTful", "RESTful API", "REST APIs"],
            "Microservices": ["Microservice"],
            "OAuth2": ["OAuth 2.0", "OAuth"],
            "JWT": ["JSON Web Token"],
            "RAG": ["Retrieval Augmented Generation", "Retrieval-Augmented Generation"],
            "Generative AI": ["GenAI", "Gen AI"],
            "LangGraph": [],
            "LlamaIndex": ["Llama Index"],
            "OpenAI API": ["OpenAI"],
            "Prompt Engineering": [],
            "Fine-tuning": ["Finetuning", "Fine tuning", "LoRA", "QLoRA", "PEFT"],
            "FAISS": [],
            "pgvector": [],
            "Pinecone": [],
            "ChromaDB": ["Chroma"],
            "Vector Database": ["Vector DB", "Vector Databases"],
            "SQLite": [],
            "Celery": [],
            "RabbitMQ": [],
            "Prometheus": [],
            "Grafana": [],
            "Pytest": [],
            "Selenium": [],
            "Tableau": [],
            "Power BI": ["PowerBI"],
            "Excel": ["MS Excel", "Microsoft Excel"],
            "Agile": ["Scrum"],
            "Jira": [],
            "Figma": [],
            "SQLAlchemy": [],
            "Streamlit": [],
            "XGBoost": [],
            "Statistics": [],
        }
        # Short or dictionary-word terms that must match with the exact casing
        # used for the technology, otherwise "C" matches "Grade C", "R" matches
        # "R&D", "CV" matches the resume's own title and "express" matches prose.
        self.case_sensitive_terms = {
            "C", "R", "Go", "CV", "ES", "ML", "DL", "TS", "JS", "TF", "Express", "Swift",
            "Rust", "Ruby", "Spark", "Rails", "Node", "Torch", "Dart", "Agile", "Scrum",
            "Excel", "Chroma",
        }
        self._known_lower = set()
        for canonical, aliases in self.skill_map.items():
            self._known_lower.add(canonical.lower())
            self._known_lower.update(a.lower() for a in aliases)
        
        self.patterns = []
        self.loose_patterns = []
        for canonical, aliases in self.skill_map.items():
            for term in [canonical] + aliases:
                strict = self._compile(term, ignore_case=term not in self.case_sensitive_terms)
                loose = self._compile(term, ignore_case=True)
                self.patterns.append((strict, canonical))
                self.loose_patterns.append((loose, canonical))

    @staticmethod
    def _compile(term: str, ignore_case: bool):
        escaped = re.escape(term)
        flags = re.IGNORECASE if ignore_case else 0
        if term in {"C", "R"}:
            # One-letter names only count when they stand alone in a list-like
            # position ("Languages: Python, R, SQL"), not in "Grade C" or "R&D".
            pattern = (
                r"(?:^|[,;|/(:\n]|\band|\bor)[ \t]*" + escaped +
                r"[ \t]*(?=[,;|/)\n]|$|[ \t]+(?:and|or)\b)"
            )
            return re.compile(pattern, flags | re.MULTILINE)
        head = r"(?<![A-Za-z0-9])"
        if any(c in escaped for c in ["\\+", "\\#", "\\."]):
            pattern = head + escaped + r"(?![A-Za-z0-9])"
        else:
            pattern = head + escaped + r"(?![A-Za-z0-9])"
        return re.compile(pattern, flags)

    def extract(self, text: str, strict_case: bool = True) -> List[str]:
        if not text:
            return []
        patterns = self.patterns if strict_case else self.loose_patterns
        found = set()
        for pattern, canonical in patterns:
            if pattern.search(text):
                found.add(canonical)
        return sorted(found)

    def extract_from_list(self, skills: List[str]) -> List[str]:
        """Normalises an already-curated skill list (a job's required skills, a
        stored candidate skill list). Casing is not trusted here, so the strict
        casing rules used for free text are relaxed."""
        if not skills:
            return []
        return self.extract(", ".join(skills), strict_case=False)

    _SKILLS_HEADER = re.compile(
        r"^\s*(?:technical\s+skills|skills(?:\s*&\s*tools)?|key\s+skills|core\s+competencies|technologies|tools(?:\s*&\s*technologies)?)\s*:?\s*$",
        re.IGNORECASE,
    )
    _LABELS = {
        "languages", "frameworks", "databases", "tools", "libraries", "technologies", "platforms",
        "cloud", "others", "other", "soft skills", "programming languages", "web", "backend", "frontend",
    }

    def unrecognised_from_skills_section(self, text: str, limit: int = 25) -> List[str]:
        """Skills the candidate lists that are not in the taxonomy. Only reported
        (stored on the resume), never used in scoring: it is a to-do list for
        growing the taxonomy or for an LLM classification pass."""
        if not text:
            return []
        out: List[str] = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if not self._SKILLS_HEADER.match(line):
                continue
            for body in lines[i + 1:i + 8]:
                if not body.strip():
                    break
                if re.match(r"^\s*(experience|education|projects?|certifications?|achievements?)\b", body, re.IGNORECASE):
                    break
                if ":" in body:
                    body = body.split(":", 1)[1]
                for token in re.split(r"[,|;•·]+", body):
                    token = token.strip(" -\t")
                    low = token.lower()
                    if not (2 <= len(token) <= 30) or len(token.split()) > 4:
                        continue
                    if not token[0].isalpha() or low in self._known_lower or low in self._LABELS:
                        continue
                    if token not in out:
                        out.append(token)
        return out[:limit]
