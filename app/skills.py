"""A catalogue of skills with the different ways people write them, grouped by what they are for.

Groups let the app say "you have GitHub Actions, which is related to Jenkins" without ever
claiming you know Jenkins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    group: str
    aliases: tuple[str, ...] = ()
    case_sensitive: bool = False  # for names that are also ordinary words: "react", "excel at", "rust"
    regex: str | None = None  # for names too short to match safely by themselves (Go, R)


def _s(name: str, group: str, *aliases: str, case_sensitive: bool = False, regex: str | None = None) -> Skill:
    return Skill(name, group, aliases, case_sensitive, regex)


SKILLS: tuple[Skill, ...] = (
    # Programming and scripting languages
    _s("Python", "language"),
    _s("Java", "language"),
    _s("JavaScript", "language", "JS", "ECMAScript"),
    _s("TypeScript", "language"),
    _s("C#", "language", "C Sharp"),
    _s("C++", "language", "CPP"),
    # "Go" and "R" are ordinary words, so only count them in a list or with "language"/"programming".
    _s(
        "Go",
        "language",
        regex=r"\b[Gg]olang\b|\bGo(?=\s*(?:[,/);]|$)|\s+(?:programming|language|lang)\b|\s+and\s+[A-Z])",
    ),
    _s("Rust", "language", case_sensitive=True),
    _s("Ruby", "language"),
    _s("PHP", "language"),
    _s("Kotlin", "language"),
    _s("Swift", "language", case_sensitive=True),
    _s("Scala", "language"),
    _s("R", "language", regex=r"\bRStudio\b|\bR(?=\s*(?:[,/);]|$)|\s+(?:programming|language|Markdown)\b)"),
    _s("Bash", "scripting", "shell scripting", "shell scripts"),
    _s("PowerShell", "scripting"),
    _s("VBA", "scripting", "Excel VBA", "macros"),
    _s("SQL", "query", "T-SQL", "PL/SQL"),
    # Web
    _s("React", "frontend", "React.js", "ReactJS", case_sensitive=True),
    _s("Next.js", "frontend", "NextJS"),
    _s("Angular", "frontend", "AngularJS"),
    _s("Vue", "frontend", "Vue.js", "VueJS"),
    _s("HTML", "markup", "HTML5"),
    _s("CSS", "markup", "CSS3", "Sass", "SCSS"),
    _s("Node.js", "backend", "NodeJS", "Node JS"),
    _s("Express", "backend", "Express.js", case_sensitive=True),
    _s("Django", "backend"),
    _s("Flask", "backend"),
    _s("FastAPI", "backend"),
    _s("Spring Boot", "backend", "Spring Framework", "Spring MVC"),
    _s(".NET", "backend", "dotnet", "ASP.NET"),
    _s("REST APIs", "api", "REST", "RESTful", "REST API"),
    _s("GraphQL", "api"),
    _s("JAX-RS", "api", "Jersey"),
    # Cloud
    _s("AWS", "cloud", "Amazon Web Services"),
    _s("Azure", "cloud", "Microsoft Azure"),
    _s("GCP", "cloud", "Google Cloud", "Google Cloud Platform"),
    _s("EC2", "aws-compute"),
    _s("Lambda", "aws-compute", "AWS Lambda"),
    _s("S3", "aws-storage", "Amazon S3"),
    _s("IAM", "access", "AWS IAM", "identity and access management"),
    _s("CloudWatch", "monitoring", "AWS CloudWatch"),
    _s("Secrets Manager", "secrets", "AWS Secrets Manager"),
    # Infrastructure as code and configuration
    _s("Terraform", "iac"),
    _s("CloudFormation", "iac", "AWS CloudFormation"),
    _s("Pulumi", "iac"),
    _s("Ansible", "config-mgmt"),
    _s("Chef", "config-mgmt", case_sensitive=True),
    _s("Puppet", "config-mgmt"),
    # Containers
    _s("Docker", "containers", "Dockerfile", "docker-compose", "Docker Compose"),
    _s("Podman", "containers"),
    _s("Kubernetes", "orchestration", "K8s", "kubectl"),
    _s("OpenShift", "orchestration"),
    _s("Amazon ECS", "orchestration", "ECS"),
    _s("Helm", "orchestration", case_sensitive=True),
    # CI/CD
    _s(
        "CI/CD",
        "cicd-practice",
        "continuous integration",
        "continuous delivery",
        "continuous deployment",
        "CI pipelines",
    ),
    _s("GitHub Actions", "ci"),
    _s("Jenkins", "ci"),
    _s("GitLab CI", "ci", "GitLab CI/CD"),
    _s("Azure Pipelines", "ci"),
    _s("CircleCI", "ci"),
    _s("Git", "vcs", "GitHub", "GitLab", "Bitbucket"),
    # Monitoring and observability
    _s("Prometheus", "monitoring"),
    _s("Grafana", "monitoring"),
    _s("Datadog", "monitoring"),
    _s("Splunk", "monitoring"),
    _s("New Relic", "monitoring"),
    _s("ELK", "monitoring", "Elasticsearch", "Kibana", "Logstash"),
    # Security
    _s("DevSecOps", "security-practice"),
    _s("SAST", "security-testing", "static analysis", "static application security testing"),
    _s("DAST", "security-testing", "OWASP ZAP", "ZAP"),
    _s("CodeQL", "security-scanner"),
    _s("SonarQube", "security-scanner", "Sonar"),
    _s("Snyk", "security-scanner"),
    _s("Trivy", "security-scanner"),
    _s("Semgrep", "security-scanner"),
    _s("OWASP", "security-practice", "OWASP Top 10"),
    _s("Vulnerability management", "security-practice", "vulnerability scanning"),
    _s("SBOM", "supply-chain", "software bill of materials"),
    _s("Secrets management", "secrets", "secret management", "HashiCorp Vault"),
    _s("Least privilege", "access", "least-privilege", "RBAC", "role-based access control"),
    _s("SOC 2", "compliance", "SOC2"),
    _s("SOX", "compliance", "Sarbanes-Oxley", case_sensitive=True),
    _s("ISO 27001", "compliance"),
    _s("NIST", "compliance", "NIST CSF", case_sensitive=True),
    _s("IT audit", "compliance", "IT auditing", "internal audit"),
    # Testing and QA
    _s("Selenium", "ui-testing", "Selenium WebDriver", "WebDriver"),
    _s("Playwright", "ui-testing"),
    _s("Cypress", "ui-testing"),
    _s("Appium", "mobile-testing"),
    _s("pytest", "test-framework", "pytest-bdd"),
    _s("JUnit", "test-framework"),
    _s("TestNG", "test-framework"),
    _s("Jest", "test-framework", case_sensitive=True),
    _s("Vitest", "test-framework"),
    _s("Cucumber", "bdd", "Gherkin", "BDD", "behavior-driven development"),
    _s("Postman", "api-testing"),
    _s("REST Assured", "api-testing", "RestAssured"),
    _s("API testing", "api-testing"),
    _s("JMeter", "load-testing", "Apache JMeter"),
    _s("Locust", "load-testing"),
    _s("k6", "load-testing", case_sensitive=True),
    _s("Test automation", "qa-practice", "automated testing", "automation testing", "test automation framework"),
    _s("Regression testing", "qa-practice", "regression"),
    _s("Functional testing", "qa-practice"),
    _s("Manual testing", "qa-practice"),
    _s("Test cases", "qa-practice", "test case design", "test plans", "test plan"),
    _s("UAT", "qa-practice", "user acceptance testing"),
    _s("Defect tracking", "qa-practice", "bug tracking", "defect management"),
    # Data
    _s("PostgreSQL", "sql-db", "Postgres"),
    _s("MySQL", "sql-db"),
    _s("SQL Server", "sql-db", "MSSQL", "Microsoft SQL Server"),
    _s("Oracle", "sql-db", "Oracle Database"),
    _s("SQLite", "sql-db"),
    _s("MongoDB", "nosql-db", "Mongo"),
    _s("DynamoDB", "nosql-db"),
    _s("Redis", "nosql-db"),
    _s("Snowflake", "warehouse"),
    _s("BigQuery", "warehouse"),
    _s("Redshift", "warehouse"),
    _s("pandas", "data-library", "Pandas"),
    _s("NumPy", "data-library"),
    _s("Spark", "big-data", "PySpark", "Apache Spark", case_sensitive=True),
    _s("Airflow", "orchestration-data", "Apache Airflow"),
    _s("dbt", "transformation", case_sensitive=True),
    _s("ETL", "data-practice", "ELT", "data pipelines", "data pipeline"),
    _s("Power BI", "bi", "PowerBI"),
    _s("Tableau", "bi"),
    _s("Looker", "bi"),
    _s("Excel", "spreadsheet", "Microsoft Excel", case_sensitive=True),
    _s("Data analysis", "data-practice", "data analytics"),
    _s("Machine learning", "ml", "scikit-learn"),
    _s("LLMs", "ml", "large language models", "LLM", "generative AI", "GenAI"),
    # Systems and IT
    _s("Linux", "os", "Ubuntu", "RHEL", "CentOS"),
    _s("Windows Server", "os"),
    _s("macOS", "os"),
    _s("Active Directory", "directory", "Entra ID", "Microsoft Entra ID", "Azure AD"),
    _s("LDAP", "directory", "OpenLDAP"),
    _s("Networking", "network", "TCP/IP", "DNS", "DHCP"),
    _s("Help desk", "it-support", "service desk", "technical support", "IT support", "desktop support"),
    _s("ServiceNow", "itsm"),
    _s("ITIL", "itsm"),
    _s("Microsoft 365", "productivity", "Office 365", "M365"),
    # Ways of working and tools
    _s("Agile", "methodology", "Scrum", "Kanban", "sprint"),
    _s("JIRA", "issue-tracking", "Jira"),
    _s("Azure DevOps", "issue-tracking", "Azure Boards"),
    _s("Confluence", "docs"),
    _s("Documentation", "docs", "technical writing", "runbooks", "runbook"),
    _s("Root cause analysis", "troubleshooting", "RCA", "root cause"),
    _s("Incident response", "operations", "incident management", "on-call", "outages"),
    _s("Stakeholder communication", "communication", "stakeholder management", "stakeholders"),
    _s("Mentoring", "leadership", "mentor", "mentored", "mentoring", "training new hires", "trained new hires"),
)

_BY_NAME = {s.name: s for s in SKILLS}


def _pattern(term: str) -> str:
    # Skills like C++, C#, .NET, CI/CD, and Node.js contain symbols, so instead of \b use explicit
    # "not part of a longer word" boundaries on both sides.
    return rf"(?<![A-Za-z0-9+#/.\-]){re.escape(term)}(?![A-Za-z0-9+#]|\.[A-Za-z0-9])"


def _compile(skill: Skill) -> re.Pattern[str]:
    if skill.regex:
        return re.compile(skill.regex)
    terms = sorted((skill.name, *skill.aliases), key=len, reverse=True)  # longest first: "GitLab CI" before "Git"
    return re.compile("|".join(_pattern(t) for t in terms), 0 if skill.case_sensitive else re.IGNORECASE)


_MATCHERS: tuple[tuple[Skill, re.Pattern[str]], ...] = tuple((skill, _compile(skill)) for skill in SKILLS)


def find_skills(text: str) -> set[str]:
    """Every catalogued skill mentioned anywhere in the text, by its standard name."""
    return {skill.name for skill, rx in _MATCHERS if rx.search(text)}


def mentions(skill_name: str, text: str) -> bool:
    for skill, rx in _MATCHERS:
        if skill.name == skill_name:
            return bool(rx.search(text))
    return term_in_text(skill_name, text)


def term_in_text(term: str, text: str) -> bool:
    """Whole-word, case-insensitive search for a term that is not in the catalogue."""
    term = term.strip()
    if not term:
        return False
    return re.search(_pattern(term), text, re.IGNORECASE) is not None


def group_of(skill_name: str) -> str | None:
    skill = _BY_NAME.get(skill_name)
    return skill.group if skill else None


def related(skill_name: str, available: set[str]) -> list[str]:
    """Skills you have that do the same job as one you are missing (Jenkins -> GitHub Actions)."""
    group = group_of(skill_name)
    if group is None:
        return []
    return sorted(s for s in available if s != skill_name and group_of(s) == group)
