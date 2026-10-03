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
            "Golang": ["Go Lang", "Go language", "Golang", "Go"],
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
            "LLM": ["Large Language Models"],
            "LangChain": ["Langchain", "Lang Chain"],
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
            "Hugging Face Transformers": ["Hugging Face", "HuggingFace Transformers", "HF Transformers", "Transformers", "HuggingFace"],
            "spaCy": ["Spacy"],
            "NLTK": [],
            "Matplotlib": [],
            "Seaborn": [],
            "Plotly": [],
            "PySpark": [],
            "Bash": ["Shell Scripting", "Shell Script", "Bash Scripting"],
            "PowerShell": [],
            "Postman": [],
            "gRPC": ["GRPC"],
            "WebSockets": ["Websocket", "WebSocket"],
            "Firebase": [],
            "Supabase": [],
            "Unit Testing": [],
            "A/B Testing": ["AB Testing"],
            # Software engineering, filling gaps found testing against real resumes
            "JUnit": [],
            "MCP": ["Model Context Protocol", "FastMCP"],
            # Named tools from non-engineering disciplines. HireAI is a general
            # hiring platform (finance, retail, HR, sales and marketing resumes
            # all need accurate matching too, not just engineering ones) — these
            # are specific named software/platforms, not generic competency
            # words like "negotiation" or "budgeting", which stay unrecognized
            # on purpose since they're not a tool a candidate either does or
            # doesn't have experience with.
            "Salesforce": [],
            "Tally": ["Tally Prime", "TallyPrime"],
            "SAP": ["SAP FI", "SAP ERP", "SAP FICO"],
            "Google Analytics": ["GA4", "Google Analytics 4"],
            "Google Ads": ["Google AdWords", "AdWords"],
            "Meta Ads": ["Facebook Ads"],
            "Canva": [],
            "POS Systems": ["Point of Sale", "POS System"],
            # Found scanning real resumes' "unrecognised skills" output.
            "Bun": [],
            "WebRTC": [],
            "Socket.io": ["Socket.IO", "SocketIO"],
            "Vite": [],
            "Webpack": [],
            "Jupyter": ["Jupyter Notebook", "Jupyter Notebooks"],
            "Google Colab": ["Colab"],
            "IntelliJ IDEA": ["IntelliJ"],
            "LLM-as-Judge": ["LLM as Judge", "LLM-as-a-Judge"],
            "Guardrails": [],
            "Playwright": [],
            "Cypress": [],
            "Jest": [],
            "Hibernate": [],
            "Maven": [],
            "Gradle": [],
            "Pydantic": [],
            "Alembic": [],
            "Swagger": ["OpenAPI"],
            "Datadog": [],
            "Splunk": [],
            "ServiceNow": [],
            "HubSpot": [],
            "QuickBooks": ["Quick Books"],
        }
        # Short or dictionary-word terms that must match with the exact casing
        # used for the technology, otherwise "C" matches "Grade C", "R" matches
        # "R&D", "CV" matches the resume's own title and "express" matches prose.
        self.case_sensitive_terms = {
            "C", "R", "Go", "CV", "ES", "ML", "DL", "TS", "JS", "TF", "Express", "Swift",
            "Rust", "Ruby", "Spark", "Rails", "Node", "Torch", "Dart", "Agile", "Scrum",
            "Excel", "Chroma", "SAP", "Tally", "Canva", "Bun", "Vite",
        }
        self._known_lower = set()
        self._canonical_lower = {canonical.lower() for canonical in self.skill_map}
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
        if term in {"C", "R", "Go"}:
            # Ambiguous short names only count when they stand alone in a
            # list-like position ("Languages: Python, R, Go, SQL"), not in
            # "Grade C", "R&D" or "go-to-market".
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

    def is_known(self, skill: str) -> bool:
        """True when `skill` is a canonical taxonomy name (as returned by extract)."""
        return (skill or "").strip().lower() in self._canonical_lower

    def normalize_list(self, skills: List[str], max_items: int = 60) -> List[str]:
        """Cleans a curated skill list (a job's required skills, a candidate's
        stored skills) item by item. Taxonomy hits are replaced by their
        canonical name ("postgres" -> "PostgreSQL"). Anything the taxonomy does
        not know ("Negotiation", "Cold calling", an in-house tool) is KEPT as
        the user wrote it instead of being silently dropped: a job that
        requires it must still be able to match on it. Duplicates are removed,
        order is preserved, and sentence-length junk is discarded."""
        out: List[str] = []
        seen = set()
        for raw in skills or []:
            item = " ".join(str(raw or "").split()).strip(" ,;|-")
            if not item or len(item) > 60 or len(item.split()) > 6:
                continue
            canon = self.extract(item, strict_case=False)
            entries = canon if canon else [item]
            for entry in entries:
                key = entry.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(entry)
            if len(out) >= max_items:
                break
        return out[:max_items]

    @staticmethod
    def mentions(text: str, skill: str) -> bool:
        """Whole-word, case-insensitive check that `skill` appears in `text`.
        Used as evidence for skills outside the taxonomy. A trailing 's'/'es'
        is tolerated so 'negotiation' matches 'negotiations'."""
        if not text or not skill:
            return False
        words = [re.escape(w) for w in re.split(r"[\s\-/]+", skill.strip()) if w]
        if not words:
            return False
        pattern = r"(?<![A-Za-z0-9])" + r"[\s\-/]+".join(words) + r"(?:e?s)?(?![A-Za-z0-9])"
        return re.search(pattern, text, re.IGNORECASE) is not None

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
