"""High-recall, evidence-first extraction of explicit market skills.

The taxonomy models terms an employer can write down, rather than trying to
infer a capability from a job title.  That keeps this pass auditable and gives
the later AI pass a clean boundary: it can add inferred skills without guessing
whether an explicit term was missed.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    name: str
    patterns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorpusPart:
    source: str
    text: str


@dataclass(frozen=True, slots=True)
class SkillMatch:
    name: str
    dimension: str
    importance: str
    source: str
    matched_text: str
    source_text: str


# This is deliberately a plain, version-controlled taxonomy. Adding an alias
# is a data change, not an opaque model change, and every alias is testable.
# Icelandic aliases cover local listings alongside English technical vocabulary.
SKILL_TAXONOMY: tuple[SkillDefinition, ...] = (
    SkillDefinition("Python", (r"\bpython\b",)),
    SkillDefinition("SQL", (r"\bsql\b", r"structured query language")),
    SkillDefinition("JavaScript", (r"\bjavascript\b", r"\becmascript\b", r"\bjs\b")),
    SkillDefinition("TypeScript", (r"\btypescript\b", r"\bts\b")),
    SkillDefinition("HTML", (r"\bhtml(?:5)?\b",)),
    SkillDefinition("CSS", (r"\bcss(?:3)?\b", r"cascading style sheets")),
    SkillDefinition("Sass", (r"\bsass\b", r"\bscss\b")),
    SkillDefinition("React", (r"\breact(?:\.js)?\b",)),
    SkillDefinition("React Native", (r"\breact native\b",)),
    SkillDefinition("Angular", (r"\bangular(?:\.js)?\b",)),
    SkillDefinition("Vue.js", (r"\bvue(?:\.js)?\b",)),
    SkillDefinition("Node.js", (r"\bnode(?:\.js)?\b", r"\bnodejs\b")),
    SkillDefinition("Next.js", (r"\bnext\.js\b", r"\bnextjs\b")),
    SkillDefinition("Svelte", (r"\bsvelte(?:kit)?\b",)),
    SkillDefinition("PHP", (r"\bphp\b",)),
    SkillDefinition("Laravel", (r"\blaravel\b",)),
    SkillDefinition("Ruby", (r"\bruby\b",)),
    SkillDefinition("Ruby on Rails", (r"\bruby on rails\b", r"\brails\b")),
    SkillDefinition("Java", (r"\bjava\b",)),
    SkillDefinition("Spring", (r"\bspring boot\b", r"\bspring framework\b")),
    SkillDefinition("Kotlin", (r"\bkotlin\b",)),
    SkillDefinition("C#", (r"(?<!\w)c#(?!\w)", r"\bc-sharp\b", r"\bc sharp\b")),
    SkillDefinition(".NET", (r"(?<!\w)\.net\b", r"\bdotnet\b", r"\basp\.net\b")),
    SkillDefinition("C++", (r"(?<!\w)c\+\+(?!\w)", r"\bc plus plus\b")),
    SkillDefinition("Go", (r"\bgolang\b", r"\bgo language\b")),
    SkillDefinition("Rust", (r"\brust\b",)),
    SkillDefinition("Scala", (r"\bscala\b",)),
    SkillDefinition("Swift", (r"\bswift\b",)),
    SkillDefinition("Objective-C", (r"\bobjective-c\b", r"\bobjective c\b")),
    SkillDefinition("Dart", (r"\bdart\b",)),
    SkillDefinition("Flutter", (r"\bflutter\b",)),
    SkillDefinition("R", (r"\br programming\b", r"\br language\b", r"\bRStudio\b")),
    SkillDefinition("MATLAB", (r"\bmatlab\b",)),
    SkillDefinition("VBA", (r"\bvba\b", r"visual basic for applications")),
    SkillDefinition("Bash", (r"\bbash\b", r"\bshell scripting\b")),
    SkillDefinition("PowerShell", (r"\bpowershell\b",)),
    SkillDefinition("Git", (r"\bgit\b", r"\bgithub\b", r"\bgitlab\b", r"\bbitbucket\b")),
    SkillDefinition("REST APIs", (r"\brest(?:ful)?\s+apis?\b", r"\bapi integrations?\b")),
    SkillDefinition("GraphQL", (r"\bgraphql\b",)),
    SkillDefinition("SOAP", (r"\bsoap\s+(?:apis?|web services?)\b",)),
    SkillDefinition("Microservices", (r"\bmicroservices?\b",)),
    SkillDefinition("WordPress", (r"\bwordpress\b",)),
    SkillDefinition("Microsoft Excel", (r"\bmicrosoft excel\b", r"\bexcel\b")),
    SkillDefinition("Power Query", (r"\bpower query\b",)),
    SkillDefinition("Power Pivot", (r"\bpower pivot\b",)),
    SkillDefinition("Power BI", (r"\bpower\s*bi\b",)),
    SkillDefinition("Tableau", (r"\btableau\b",)),
    SkillDefinition("Qlik", (r"\bqlik(?:sense|view)?\b",)),
    SkillDefinition("Looker", (r"\blooker(?: studio)?\b",)),
    SkillDefinition("Google Analytics", (r"\bgoogle analytics\b", r"\bga4\b")),
    SkillDefinition("Google Tag Manager", (r"\bgoogle tag manager\b", r"\bgtm\b")),
    SkillDefinition("Data Analysis", (r"\bdata analy(?:sis|tics)\b", r"\bgagnagreining")),
    SkillDefinition("Data Visualization", (r"\bdata visuali[sz]ation\b", r"\bgagnasjónræn")),
    SkillDefinition("Statistics", (r"\bstatistics?\b", r"\btölfræði")),
    SkillDefinition("Machine Learning", (r"\bmachine learning\b", r"\bvélanám")),
    SkillDefinition("Artificial Intelligence", (r"\bartificial intelligence\b", r"\bgervigreind")),
    SkillDefinition("Natural Language Processing", (r"\bnatural language processing\b", r"\bNLP\b")),
    SkillDefinition("Computer Vision", (r"\bcomputer vision\b",)),
    SkillDefinition("PostgreSQL", (r"\bpostgres(?:ql)?\b",)),
    SkillDefinition("MySQL", (r"\bmysql\b",)),
    SkillDefinition("Microsoft SQL Server", (r"\b(?:microsoft )?sql server\b", r"\bmssql\b")),
    SkillDefinition("Oracle Database", (r"\boracle (?:database|db)\b",)),
    SkillDefinition("MongoDB", (r"\bmongodb\b",)),
    SkillDefinition("Redis", (r"\bredis\b",)),
    SkillDefinition("Elasticsearch", (r"\belasticsearch\b", r"\belk stack\b")),
    SkillDefinition("Snowflake", (r"\bsnowflake\b",)),
    SkillDefinition("Databricks", (r"\bdatabricks\b",)),
    SkillDefinition("Apache Spark", (r"\bapache spark\b", r"\bpyspark\b", r"\bspark sql\b")),
    SkillDefinition("AWS", (r"\baws\b", r"\bamazon web services\b")),
    SkillDefinition("Microsoft Azure", (r"\bmicrosoft azure\b", r"\bazure\b")),
    SkillDefinition("Google Cloud", (r"\bgoogle cloud(?: platform)?\b", r"\bgcp\b")),
    SkillDefinition("Docker", (r"\bdocker\b",)),
    SkillDefinition("Kubernetes", (r"\bkubernetes\b", r"\bk8s\b")),
    SkillDefinition("Terraform", (r"\bterraform\b",)),
    SkillDefinition("Ansible", (r"\bansible\b",)),
    SkillDefinition("CI/CD", (r"\bci/cd\b", r"\bcontinuous integration\b", r"\bcontinuous delivery\b")),
    SkillDefinition("Jenkins", (r"\bjenkins\b",)),
    SkillDefinition("Linux", (r"\blinux\b",)),
    SkillDefinition("Windows Server", (r"\bwindows server\b",)),
    SkillDefinition("Networking", (r"\bcomputer networking\b", r"\bnetkerfi")),
    SkillDefinition("Cybersecurity", (r"\bcyber ?security\b", r"\binformation security\b", r"\bupplýsingaöryggi")),
    SkillDefinition("ISO 27001", (r"\biso[ -]?27001\b",)),
    SkillDefinition("GDPR", (r"\bgdpr\b", r"\bpersónuvernd")),
    SkillDefinition("Figma", (r"\bfigma\b",)),
    SkillDefinition("Adobe Creative Cloud", (r"\badobe creative cloud\b", r"\badobe cc\b")),
    SkillDefinition("Adobe Photoshop", (r"\bphotoshop\b",)),
    SkillDefinition("Adobe Illustrator", (r"\billustrator\b",)),
    SkillDefinition("Adobe InDesign", (r"\bindesign\b",)),
    SkillDefinition("AutoCAD", (r"\bautocad\b",)),
    SkillDefinition("Revit", (r"\brevit\b",)),
    SkillDefinition("SolidWorks", (r"\bsolidworks\b",)),
    SkillDefinition("Jira", (r"\bjira\b",)),
    SkillDefinition("Confluence", (r"\bconfluence\b",)),
    SkillDefinition("Microsoft Office", (r"\bmicrosoft office\b", r"\boffice[- ]pakk")),
    SkillDefinition("Microsoft Word", (r"\bmicrosoft word\b", r"\bword[- ]vinnsla\b", r"\britvinnsla\b")),
    SkillDefinition("Microsoft PowerPoint", (r"\bpower ?point\b",)),
    SkillDefinition("Microsoft Outlook", (r"\boutlook\b",)),
    SkillDefinition("Microsoft Teams", (r"\bmicrosoft teams\b",)),
    SkillDefinition("SAP", (r"\bsap\b",)),
    SkillDefinition("Microsoft Dynamics 365", (r"\bmicrosoft dynamics(?: 365)?\b", r"\bdynamics 365\b")),
    SkillDefinition("Business Central", (r"\bbusiness central\b", r"\bdynamics nav\b", r"\bnavision\b")),
    SkillDefinition("Salesforce", (r"\bsalesforce\b",)),
    SkillDefinition("HubSpot", (r"\bhubspot\b",)),
    SkillDefinition("Visma", (r"\bvisma\b",)),
    SkillDefinition("Odoo", (r"\bodoo\b",)),
    SkillDefinition("Accounting", (r"\baccounting\b", r"\bbókhald")),
    SkillDefinition("Financial Analysis", (r"\bfinancial analysis\b", r"\bfjármálagreining")),
    SkillDefinition("Auditing", (r"\baudit(?:ing)?\b", r"\bendurskoðun")),
    SkillDefinition("Payroll", (r"\bpayroll\b", r"\blauna(?:vinnsla|útreikningur|kerfi)")),
    SkillDefinition("Procurement", (r"\bprocurement\b", r"\binnkaup")),
    SkillDefinition("Project Management", (r"\bproject management\b", r"\bverkefnastjórn")),
    SkillDefinition("Agile", (r"\bagile\b", r"\bskrum\b", r"\bscrum\b")),
    SkillDefinition("Lean", (r"\blean\b", r"\b6 sigma\b", r"\bsix sigma\b")),
    SkillDefinition("Sales", (r"\bsales\b", r"\bsölu(?:reynsla|mennska|störf)?\b")),
    SkillDefinition("Marketing", (r"\bmarketing\b", r"\bmarkaðs(?:setning|mál)")),
    SkillDefinition("SEO", (r"\bseo\b", r"\bleitarvélabestun")),
    SkillDefinition("Content Marketing", (r"\bcontent marketing\b", r"\befnismarkaðssetning")),
    SkillDefinition("Customer Service", (r"\bcustomer service\b", r"\bþjónusta (?:við )?viðskiptavina\b", r"\bþjónustustörf\b", r"\bþjónustulund\b")),
    SkillDefinition("Human Resources", (r"\bhuman resources\b", r"\bmannauðs(?:mál|stjórnun)")),
    SkillDefinition("Recruitment", (r"\brecruitment\b", r"\bráðningar")),
    SkillDefinition("HACCP", (r"\bhaccp\b", r"\bmatvælaöryggi")),
    SkillDefinition("Food Safety", (r"\bfood safety\b",)),
    SkillDefinition("Health and Safety", (r"\bhealth and safety\b", r"\bvinnuvernd\b", r"\böryggismál")),
    SkillDefinition("First Aid", (r"\bfirst aid\b", r"\bskyndihjálp")),
    SkillDefinition("Forklift Licence", (r"\bforklift licen[cs]e\b", r"\blyftararéttindi")),
    SkillDefinition("Driving Licence", (r"\bdriving licen[cs]e\b", r"\bdriver'?s license\b", r"\bökuskírteini\b", r"\bbílpróf\b")),
    SkillDefinition("Nursing", (r"\bnursing\b", r"\bhjúkrun")),
    SkillDefinition("Healthcare", (r"\bhealthcare\b", r"\bheilbrigðis(?:þjónusta|störf)")),
    SkillDefinition("Patient Care", (r"\bpatient care\b", r"\bumönnun sjúklinga")),
    SkillDefinition("Icelandic", (r"\bicelandic\b", r"\bíslenskukunnátta\b", r"\bíslen[sk]a\b")),
    SkillDefinition("English", (r"\benglish\b", r"\benskukunnátta\b", r"\bgóð ensk[au]\b")),
    SkillDefinition("Danish", (r"\bdanish\b", r"\bdönskukunnátta\b")),
    SkillDefinition("Norwegian", (r"\bnorwegian\b", r"\bnorskukunnátta\b")),
    SkillDefinition("Swedish", (r"\bswedish\b", r"\bsænskukunnátta\b")),
    SkillDefinition("German", (r"\bgerman\b", r"\bþýskukunnátta\b")),
    SkillDefinition("Polish", (r"\bpolish\b", r"\bpólskukunnátta\b")),
)

_REQUIRED = re.compile(r"\b(?:required|requirement|must(?:\s+have)?|mandatory|essential|krafist|skilyrði|þarf að|nauðsynleg(?:t|ur|a)?)\b", re.IGNORECASE)
_PREFERRED = re.compile(r"\b(?:preferred|desirable|advantage|nice to have|beneficial|æskilegt|kostur|reynsla af|ætti að hafa)\b", re.IGNORECASE)
_IMPORTANCE_RANK = {"mentioned": 0, "preferred": 1, "required": 2}
_LANGUAGE_SKILLS = {"Icelandic", "English", "Danish", "Norwegian", "Swedish", "German", "Polish"}
_CREDENTIAL_SKILLS = {"Driving Licence", "Forklift Licence", "HACCP", "ISO 27001", "First Aid"}
_EMPLOYER_QUALITY_NAMES = {
    "drifkraftur", "fagmennska", "frumkvæði", "jákvæðni", "mannleg samskipti",
    "samviskusemi", "sjálfstæð vinnubrögð", "skipulag", "stundvísi",
    "sveigjanleiki", "vinna undir álagi", "teymisvinna", "samskiptafærni",
}


def _importance(context: str) -> str:
    if _REQUIRED.search(context):
        return "required"
    if _PREFERRED.search(context):
        return "preferred"
    return "mentioned"


def _context(text: str, match: re.Match[str], radius: int = 220) -> str:
    return " ".join(text[max(match.start() - radius, 0):min(match.end() + radius, len(text))].split())


def canonical_skill_dimension(name: str) -> str:
    """Classify a canonical taxonomy entry for separate market facets."""
    if name in _LANGUAGE_SKILLS:
        return "language"
    if name in _CREDENTIAL_SKILLS:
        return "credential"
    return "professional_skill"


def alfred_skill_dimension(name: str, source_categories: Iterable[str]) -> str | None:
    """Classify an Alfreð-labelled skill without treating conditions as skills."""
    categories = {value.casefold() for value in source_categories}
    normalized = name.strip().casefold()
    if "almenn skilyrði" in categories or normalized in {"hreint sakavottorð", "reyklaus"}:
        return None
    if "ökuréttindi" in categories:
        return "credential"
    if "almennt" in categories or normalized in _EMPLOYER_QUALITY_NAMES:
        return "employer_quality"
    return "professional_skill"


def extract_explicit_skills(parts: Iterable[CorpusPart]) -> list[SkillMatch]:
    """Return one strongest, evidence-backed explicit match per canonical skill."""
    found: dict[str, SkillMatch] = {}
    for part in parts:
        if not part.text or not part.text.strip():
            continue
        for definition in SKILL_TAXONOMY:
            for pattern in definition.patterns:
                match = re.search(pattern, part.text, re.IGNORECASE)
                if not match:
                    continue
                context = _context(part.text, match)
                candidate = SkillMatch(
                    definition.name, canonical_skill_dimension(definition.name),
                    _importance(context), part.source, match.group(0), context,
                )
                current = found.get(definition.name)
                if current is None or _IMPORTANCE_RANK[candidate.importance] > _IMPORTANCE_RANK[current.importance]:
                    found[definition.name] = candidate
                break
    return sorted(found.values(), key=lambda item: item.name.casefold())
