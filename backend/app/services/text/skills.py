"""Deterministic skill normalisation and extraction — zero LLM tokens.

A taxonomy maps aliases to one canonical name ("ReactJS", "react.js" → "react"),
so matching is a set operation, and LLM output can be checked against the job text.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "data" / "skills_taxonomy.json"
ROLES_PATH = TAXONOMY_PATH.with_name("roles.json")

# parent skill → skills that imply it. Having the child means you have the parent: a React developer knows
# JavaScript, HTML and CSS, so a posting asking for them must not count as "missing". Chains are followed
# (redux → react → javascript). Every name must be in the taxonomy (tests check it).
IMPLIED_BY = {
    "javascript": ["mern", "mean", "react", "angular", "vue", "node.js", "typescript", "jquery", "nuxt.js", "lwc",
                   "sapui5", "gatsby", "remix", "rxjs", "htmx", "next.js", "react native"],
    "html": ["react", "angular", "vue", "wordpress", "nuxt.js", "webflow"],
    "css": ["react", "angular", "vue", "tailwind", "sass", "bootstrap", "material ui", "styled-components",
            "wordpress", "webflow"],
    "typescript": ["angular", "nestjs"],
    "react": ["mern", "next.js", "redux", "react native", "react query", "react router", "material ui", "gatsby",
              "remix", "styled-components", "react testing library"],
    "vue": ["nuxt.js", "pinia"],
    "angular": ["mean", "ngrx"],
    "node.js": ["mern", "mean", "express", "nestjs"],
    "mongodb": ["mern", "mean"],
    "express": ["mern", "mean"],
    "rest api": ["express", "fastapi", "flask", "django", "spring boot", "asp.net core", "nestjs", "laravel",
                 "ruby on rails", "swagger", "postman", "rest assured"],
    "python": ["fastapi", "django", "flask", "pandas", "numpy", "scikit-learn", "pyspark", "pytest", "scrapy",
               "streamlit", "jupyter"],
    "java": ["spring boot", "hibernate", "spring cloud", "spring security", "spring mvc", "junit", "mockito",
             "maven", "gradle", "jsp", "testng"],
    "spring boot": ["spring cloud", "spring security"],
    "c#": [".net", "asp.net core", "entity framework", "linq", "wpf", "blazor", "xamarin", ".net maui"],
    ".net": ["asp.net core", "entity framework", "blazor", "wpf"],
    "php": ["laravel", "symfony", "codeigniter", "wordpress", "magento", "drupal", "woocommerce"],
    "ruby": ["ruby on rails"],
    "kotlin": ["jetpack compose"],
    "android": ["jetpack compose", "android studio"],
    "swift": ["swiftui", "uikit"],
    "ios": ["swiftui", "uikit", "xcode"],
    "dart": ["flutter"],
    "sql": ["postgresql", "mysql", "sql server", "oracle database", "pl/sql", "t-sql", "sqlite", "mariadb",
            "snowflake", "bigquery", "redshift", "dbt", "stored procedures"],
    "sql server": ["t-sql", "ssis", "ssrs", "ssas"],
    "oracle database": ["pl/sql", "rac", "data guard"],
    "data visualization": ["power bi", "tableau", "looker", "qlik", "microstrategy", "cognos", "d3.js", "chart.js"],
    "data warehouse": ["snowflake", "bigquery", "redshift", "azure synapse", "teradata"],
    "etl": ["informatica", "talend", "ssis", "azure data factory", "aws glue", "apache nifi"],
    "spark": ["pyspark", "databricks"],
    "machine learning": ["scikit-learn", "xgboost", "tensorflow", "pytorch", "keras", "mlops", "hugging face",
                         "deep learning", "model deployment", "feature engineering"],
    "deep learning": ["tensorflow", "pytorch", "keras", "cnn", "lstm", "transformers", "bert", "computer vision"],
    "nlp": ["transformers", "bert", "spacy", "nltk", "sentiment analysis"],
    "computer vision": ["opencv", "yolo", "object detection", "image processing"],
    "generative ai": ["llm", "diffusion models", "gans"],
    "llm": ["rag", "langchain", "langgraph", "llamaindex", "prompt engineering", "fine-tuning", "llm evaluation"],
    "ai agents": ["langgraph", "mcp"],
    "aws": ["ec2", "s3", "lambda", "rds", "vpc", "cloudfront", "eks", "ecs", "cloudformation", "aws sagemaker",
            "aws glue", "redshift", "cloudwatch"],
    "azure": ["azure devops", "azure functions", "aks", "azure active directory", "azure data factory",
              "azure synapse", "azure machine learning", "bicep", "microsoft sentinel"],
    "gcp": ["gke", "bigquery", "vertex ai"],
    "docker": ["docker compose", "kubernetes"],
    "kubernetes": ["helm", "argocd", "eks", "aks", "gke", "istio", "openshift", "kubeflow"],
    "ci/cd": ["jenkins", "github actions", "gitlab ci", "azure devops", "circleci", "teamcity", "argocd"],
    "git": ["github actions", "gitlab ci", "gitops"],
    "infrastructure as code": ["terraform", "ansible", "cloudformation", "pulumi", "bicep", "puppet",
                               "chef automation"],
    "linux": ["linux administration", "red hat", "kali linux", "bash", "linux kernel"],
    "networking": ["tcp/ip", "cisco", "ccna", "ccnp", "juniper", "bgp", "ospf", "mpls", "wireshark", "dns", "dhcp",
                   "vpn", "firewalls", "sd-wan", "nmap"],
    "observability": ["prometheus", "grafana", "datadog", "new relic", "elk stack", "opentelemetry", "dynatrace",
                      "appdynamics", "cloudwatch", "nagios", "zabbix"],
    "unit testing": ["junit", "pytest", "jest", "mocha", "jasmine", "vitest", "mockito", "react testing library"],
    "test automation": ["selenium", "cypress", "playwright", "appium", "testng", "cucumber", "robot framework",
                        "puppeteer"],
    "performance testing": ["jmeter", "loadrunner", "k6"],
    "siem": ["splunk", "qradar", "microsoft sentinel"],
    "edr": ["crowdstrike"],
    "identity and access management": ["okta", "sailpoint", "privileged access management", "azure active directory",
                                       "keycloak", "auth0", "sso", "ldap"],
    "penetration testing": ["burp suite", "metasploit", "red teaming"],
    "application security": ["owasp", "secure coding", "sast/dast", "threat modeling"],
    "cybersecurity": ["iso 27001", "siem", "incident response", "penetration testing", "network security",
                      "vulnerability assessment", "cloud security", "application security"],
    "salesforce": ["salesforce apex", "lwc", "soql", "visualforce", "sales cloud", "service cloud",
                   "salesforce administration", "salesforce cpq", "salesforce marketing cloud"],
    "power platform": ["power apps", "power automate"],
    "rpa": ["uipath", "automation anywhere", "blue prism"],
    "mainframe": ["cobol", "jcl", "cics", "vsam"],
    "sap": ["abap", "sapui5", "sap s/4hana", "sap fico", "sap fi", "sap co", "sap mm", "sap sd", "sap pp",
            "sap qm", "sap pm", "sap ewm", "sap wm", "sap tm", "sap ps", "sap hcm", "sap successfactors", "sap ariba",
            "sap fiori", "sap hana", "sap basis", "sap bw", "sap businessobjects", "sap analytics cloud", "sap btp",
            "sap cpi", "sap pi/po", "sap cap", "sap rap", "sap security", "sap grc", "sap solution manager",
            "sap crm", "sap scm", "sap ibp", "sap mdg", "sap commerce cloud", "sap bpc", "sap slt", "sap is-u",
            "sap netweaver", "sap business one", "sap data migration"],
    "sap fi": ["sap fico"],
    "sap co": ["sap fico"],
    "abap": ["abap on hana", "alv reports", "smartforms", "bapi", "badi", "idoc", "sap rap"],
    "scrum": ["scaled agile framework"],
    "agile": ["scrum", "kanban", "scaled agile framework"],
    "ux design": ["ui design", "wireframing", "prototyping", "figma", "adobe xd", "interaction design"],
}

IMPLIES: dict[str, list[str]] = {}
for _parent, _children in IMPLIED_BY.items():
    for _child in _children:
        IMPLIES.setdefault(_child, []).append(_parent)


@lru_cache
def _taxonomy() -> dict[str, list[str]]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


@lru_cache
def _alias_map() -> dict[str, str]:
    mapping = {}
    for canonical, aliases in _taxonomy().items():
        mapping[canonical] = canonical
        for alias in aliases:
            mapping[alias.lower()] = canonical
    return mapping


def _alias_regex(alias: str) -> str:
    # Word boundaries that also respect symbols in names like c++, c#, node.js, ci/cd.
    return r"(?<![\w+#.])" + re.escape(alias) + r"(?![\w+#]|\.\w)"


@lru_cache
def _pattern() -> re.Pattern:
    # Longest aliases first so "react native" wins over "react".
    aliases = sorted(_alias_map(), key=len, reverse=True)
    return re.compile("|".join(_alias_regex(a) for a in aliases), re.IGNORECASE)


def known_skills() -> list[str]:
    return sorted(_taxonomy())


def skill_catalog() -> list[dict]:
    """[{name, aliases}] for the skill dropdown: typing "js" or "reactjs" can still suggest the canonical name.

    Kept in file order, which lists the most common skills first; the dropdown breaks ties with it."""
    return [{"name": name, "aliases": [a for a in aliases if a != name]} for name, aliases in _taxonomy().items()]


@lru_cache
def role_catalog() -> list[dict]:
    """[{role, category, skills, aliases}] — every IT role with the skills usually asked for it."""
    return json.loads(ROLES_PATH.read_text(encoding="utf-8"))


def canonical(skill: str) -> str:
    """Canonical name for a known skill, else the cleaned lower-case input."""
    cleaned = re.sub(r"\s+", " ", skill.strip().lower())
    return _alias_map().get(cleaned, cleaned)


def normalize_skills(skills: list[str]) -> list[str]:
    """Canonicalise, de-duplicate (order-preserving) and drop empties."""
    seen: dict[str, None] = {}
    for s in skills:
        c = canonical(s)
        # LLMs often write "javascript/typescript" as one item; split it when every part is a known skill.
        parts = [canonical(p) for p in c.split("/")] if "/" in c and c not in _taxonomy() else [c]
        if len(parts) > 1 and not all(p in _taxonomy() for p in parts):
            parts = [c]
        for p in parts:
            if p and len(p) <= 40:
                seen.setdefault(p, None)
    return list(seen)


def expand_implied(skills: list[str] | set[str]) -> set[str]:
    out = set(skills)
    pending = list(out)
    while pending:  # transitive: redux → react → javascript
        for implied in IMPLIES.get(pending.pop(), []):
            if implied not in out:
                out.add(implied)
                pending.append(implied)
    if any(s.startswith("sap ") for s in out):  # any SAP module implies SAP itself
        out.add("sap")
    return out


def extract_skills(text: str) -> list[str]:
    """All known skills mentioned in free text, canonicalised, in first-seen order."""
    found: dict[str, None] = {}
    for m in _pattern().finditer(text or ""):
        found.setdefault(_alias_map()[m.group(0).lower()], None)
    return list(found)


NICE_RE = re.compile(r"nice[- ]to[- ]have|good[- ]to[- ]have|preferred|bonus|\bplus\b|desirable|optional", re.IGNORECASE)
HEADING_RE = re.compile(r"^[^.]{0,60}:\s*$")


def split_requirements(text: str) -> tuple[list[str], list[str]]:
    """(required, nice_to_have) skills, using 'nice to have / preferred / plus' cues per line or section."""
    required: dict[str, None] = {}
    nice: dict[str, None] = {}
    in_nice_section = False
    for line in (text or "").splitlines():
        if HEADING_RE.match(line.strip()):
            in_nice_section = bool(NICE_RE.search(line))
        target = nice if in_nice_section or NICE_RE.search(line) else required
        for s in extract_skills(line):
            target.setdefault(s, None)
    return list(required), [s for s in nice if s not in required]


def is_grounded(skill: str, text: str) -> bool:
    """True when the skill (or any alias of it) literally appears in the text.

    Used to drop skills an LLM invented that the job posting never mentions.
    """
    c = canonical(skill)
    if c in _taxonomy():
        return c in extract_skills(text)
    return re.search(_alias_regex(c), text or "", re.IGNORECASE) is not None
