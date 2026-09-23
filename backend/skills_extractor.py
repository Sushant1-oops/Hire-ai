
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
        }
        
        self.patterns = []
        for canonical, aliases in self.skill_map.items():
            terms = [canonical] + aliases
            for term in terms:
                escaped = re.escape(term)
                if any(c in escaped for c in ['\\+', '\\#', '\\/', '\\.']):
                    pattern = r'(?<![A-Za-z0-9])' + escaped + r'(?![A-Za-z0-9])'
                else:
                    pattern = r'\b' + escaped + r'\b'
                self.patterns.append((re.compile(pattern, re.IGNORECASE), canonical))

    def extract(self, text: str) -> List[str]:
        if not text:
            return []
        found = set()
        for pattern, canonical in self.patterns:
            if pattern.search(text):
                found.add(canonical)
        return sorted(list(found))

    def extract_from_list(self, skills: List[str]) -> List[str]:
        if not skills:
            return []
        return self.extract(" ".join(skills))