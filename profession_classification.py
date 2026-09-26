"""Provisional, auditable profession assignments for the static public snapshot.

Alfreð's jobTags are multi-label evidence, not a single occupation. This
curated layer groups clear title variants and only uses a tag alone when it
unambiguously names one supported profession. Raw titles and all original tags
remain in the private, versioned market tables for later reclassification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfessionRule:
    key: str
    label: str
    title: str
    tags: tuple[str, ...] = ()


# Ordered from distinctive occupations to broader titles. A title match is
# provisional evidence, not a claim that the employer supplied this taxonomy.
RULES = (
    ProfessionRule("data-engineer", "Data Engineer", r"\bdata engineer\b|gagnaverkfræð|gagnainnviða", ("Gagnaverkfræðingur",)),
    ProfessionRule("data-scientist", "Data Scientist", r"\bdata scientist\b|gagnavísind", ("Gagnavísindamaður",)),
    ProfessionRule("data-analyst", "Data Analyst", r"\bdata analyst\b|gagnagrein|gagnasérfræð|viðskiptagreind|business intelligence|\bbi analyst\b", ("Gagnagreinir", "Viðskiptagreinir")),
    ProfessionRule("cybersecurity-specialist", "Security Specialist", r"cyber.?security|upplýsingaörygg|netörygg|\bsecurity engineer\b", ("Öryggissérfræðingur",)),
    ProfessionRule("qa-engineer", "Software Tester", r"\bqa (?:engineer|analyst|tester)\b|quality assurance|hugbúnaðarpróf|prófunarsérfræð", ("Hugbúnaðarprófanir",)),
    ProfessionRule("devops-engineer", "DevOps Engineer", r"\bdevops\b|\bsite reliability engineer\b", ("DevOps",)),
    ProfessionRule("machine-learning-engineer", "Machine Learning Engineer", r"machine learning engineer|vélanámsverkfræð", ("Vélanámsverkfræðingur",)),
    ProfessionRule("product-manager", "Product Manager", r"\bproduct (?:manager|owner)\b|vörustjór|vörueigand", ("Vörustjóri",)),
    ProfessionRule("it-support", "IT Support Specialist", r"\bit support\b|\bhelp.?desk\b|tölvuþjónust|tækniaðstoð|notendaþjónust|\bservice desk\b", ("Notendaþjónusta",)),
    ProfessionRule("network-engineer", "Network Engineer", r"\bnetwork (?:engineer|administrator|specialist)\b|netsérfræð|netstjór", ("Netsérfræðingur", "Netstjóri")),
    ProfessionRule("systems-administrator", "Systems Administrator", r"\bsystem(?:s)? administrator\b|kerfisstjór|kerfisumsjón|kerfissérfræð", ("Kerfisstjóri", "Kerfisumsjón")),
    ProfessionRule("ux-designer", "UX Designer", r"\b(?:ux|ui|user experience) (?:designer|researcher)\b|viðmótshönn", ("Viðmótshönnuður",)),
    ProfessionRule("software-architect", "Software Architect", r"\bsoftware architect\b|hugbúnaðararkitekt", ("Hugbúnaðararkitekt",)),
    ProfessionRule("software-developer", "Software Developer", r"\b(?:software|frontend|front.end|backend|back.end|full.?stack|web|mobile|app|ai|automation|embedded) (?:developer|engineer|programmer)\b|forritar|hugbúnaðar(?:verkfræð|sérfræð|þróun)|vefforrit", ("Forritari", "Hugbúnaðarverkfræðingur", "Vefforritari")),
    ProfessionRule("nurse", "Nurse", r"hjúkrunarfræð|\bregistered nurse\b|\bnurse\b|svæfingahjúkrun", ("Hjúkrunarfræðingur",)),
    ProfessionRule("practical-nurse", "Practical Nurse", r"sjúkralið|\bpractical nurse\b", ("Sjúkraliði",)),
    ProfessionRule("physician", "Physician", r"\blæknir\b|\blæknis\b|\bphysician\b|\bmedical doctor\b", ("Læknir", "Sérfræðilæknir")),
    ProfessionRule("physiotherapist", "Physiotherapist", r"(?<!aðstoðarmaður )sjúkraþjálf|physiotherap", ("Sjúkraþjálfari",)),
    ProfessionRule("occupational-therapist", "Occupational Therapist", r"(?<!aðstoðarmaður )iðjuþjálf|occupational therap", ("Iðjuþjálfi",)),
    ProfessionRule("psychologist", "Psychologist", r"sálfræð|psycholog", ("Sálfræðingur",)),
    ProfessionRule("social-worker", "Social Worker", r"félagsráðgjaf|social worker", ("Félagsráðgjafi",)),
    ProfessionRule("pharmacist", "Pharmacist", r"lyfjafræð|pharmacist", ("Lyfjafræðingur",)),
    ProfessionRule("pharmacy-technician", "Pharmacy Technician", r"lyfjatækn|pharmacy technician", ("Lyfjatæknir",)),
    ProfessionRule("dental-assistant", "Dental Assistant", r"aðstoð.*tannlæk|dental assistant", ("Tanntæknir",)),
    ProfessionRule("disability-support", "Disability Support Worker", r"þroskaþjálf|stuðningsfulltrú|liðveit|npa aðstoð|starfsmaður.*heimili.*fatlað|disability support", ("Þroskaþjálfi", "Stuðningsfulltrúi")),
    ProfessionRule("care-worker", "Care Worker", r"aðhlynning|umönnun|heimahjálp|heimilisþjónust|care worker|care assistant", ("Aðhlynning", "Umönnun")),
    ProfessionRule("special-education-teacher", "Special Education Teacher", r"sérkenn|special education teacher", ("Sérkennsla",)),
    ProfessionRule("preschool-teacher", "Preschool Teacher", r"leikskólakennar|preschool teacher|kindergarten teacher", ("Leikskólakennari",)),
    ProfessionRule("primary-teacher", "Primary School Teacher", r"grunnskólakennar|umsjónarkennar|primary school teacher", ("Grunnskólakennari", "Umsjónarkennari")),
    ProfessionRule("secondary-teacher", "Secondary School Teacher", r"framhaldsskólakennar|secondary school teacher", ("Framhaldsskólakennari",)),
    ProfessionRule("school-principal", "School Principal", r"skólastjór|school principal|headteacher", ("Skólastjóri", "Leikskólastjóri")),
    ProfessionRule("school-support", "School Support Worker", r"skólalið|kennsluaðstoð|teaching assistant|classroom assistant", ("Skólaliði",)),
    ProfessionRule("after-school-educator", "After-school Educator", r"frístundaleiðbein|frístundaheimil|after.school", ("Frístundaleiðbeinandi",)),
    ProfessionRule("teaching-assistant", "Teaching Assistant", r"\bleiðbeinandi\b|\bkennsluleiðbein", ("Leiðbeinandi",)),
    ProfessionRule("researcher", "Researcher", r"rannsóknar(?:maður|kona|sérfræð|starf)|\bresearch(?:er| scientist| fellow)\b", ("Rannsóknarmaður",)),
    ProfessionRule("chef", "Chef / Cook", r"matreiðslumaður|matreiðslukona|\bkokkur\b|\bchef\b|\bcook\b", ("Kokkur", "Matreiðslumeistari")),
    ProfessionRule("kitchen-assistant", "Kitchen Assistant", r"eldhús(?:starf|aðstoð|fólk)|aðstoð.*eldhús|kitchen (?:assistant|staff|worker)|uppvask", ("Eldhússtörf",)),
    ProfessionRule("waiter", "Waiter / Server", r"\bþjónn\b|\bþjónust(?:a|u) í veitingasal\b|\bwaiter\b|\bserver\b|framreiðslumaður", ("Þjónn", "Framreiðslumaður")),
    ProfessionRule("bartender", "Bartender", r"barþjón|bartend", ("Barþjónn",)),
    ProfessionRule("barista", "Barista", r"kaffibarþjón|barista", ("Kaffibarþjónn",)),
    ProfessionRule("hotel-receptionist", "Hotel Receptionist", r"hótel.*móttaka|gestamóttaka|hotel reception", ("Gestamóttaka",)),
    ProfessionRule("restaurant-manager", "Restaurant Manager", r"veitingastjór|restaurant manager", ("Veitingastjóri",)),
    ProfessionRule("electrician", "Electrician", r"rafvirk|electrician", ("Rafvirki",)),
    ProfessionRule("carpenter", "Carpenter", r"húsasmíð|húsasmið|\bcarpenter\b|\bjoiner\b", ("Húsasmiður", "Smiður")),
    ProfessionRule("plumber", "Plumber", r"pípulagning|pípulagningamaður|\bplumber\b", ("Pípulagningamaður",)),
    ProfessionRule("auto-mechanic", "Auto Mechanic", r"bifvélavirk|bílaverkstæð|\bauto mechanic\b", ("Bifvélavirki",)),
    ProfessionRule("machine-operator", "Machine Operator", r"vélamaður|vinnuvélamaður|machine operator|lyftaramaður", ("Vélamaður", "Vinnuvélamaður", "Lyftaramaður")),
    ProfessionRule("driver", "Driver", r"bílstjór|ökumaður|\bdriver\b|sendibílstjór", ("Bílstjóri", "Meiraprófsbílstjóri")),
    ProfessionRule("warehouse-worker", "Warehouse Worker", r"lager(?:starf|maður|fólk)|vöruhús|warehouse|birgðastarfs", ("Lagerstörf",)),
    ProfessionRule("production-worker", "Production Worker", r"framleiðslustarf|framleiðslumaður|production worker", ("Framleiðslustarf",)),
    ProfessionRule("cleaner", "Cleaner", r"ræsting|\bþrif\b|\bcleaner\b|housekeep", ("Ræstingar", "Þrif")),
    ProfessionRule("security-guard", "Security Guard", r"öryggisvörð|öryggisgæsl|security guard", ("Öryggisgæsla",)),
    ProfessionRule("retail-associate", "Retail Associate", r"afgreiðslustarf|verslunarstarf|starfsmaður.*verslun|retail assistant|store associate|\bafgreiðsla\b", ("Verslunarstörf", "Afgreiðsla")),
    ProfessionRule("store-manager", "Store Manager", r"verslunarstjór|store manager", ("Verslunarstjóri", "Aðstoðarverslunarstjóri")),
    ProfessionRule("customer-service-representative", "Customer Service Representative", r"þjónustufulltrú|þjónusturáðgjaf|customer (?:service|support) (?:representative|agent|specialist)", ("Þjónustufulltrúi", "Þjónusturáðgjafi")),
    ProfessionRule("sales-representative", "Sales Representative", r"sölufulltrú|sölumaður|söluráðgjaf|sales (?:representative|consultant|associate|person)|\bsalesperson\b", ("Sölufulltrúi", "Sölumaður")),
    ProfessionRule("telemarketer", "Telemarketer", r"símasala|úthringistarf|telemarket", ("Símasala",)),
    ProfessionRule("travel-advisor", "Travel Advisor", r"ferðaráðgjaf|travel (?:advisor|consultant)", ("Ferðaráðgjafi",)),
    ProfessionRule("receptionist", "Receptionist", r"móttökufulltrú|\breceptionist\b|\bmóttaka\b", ("Móttaka",)),
    ProfessionRule("accountant", "Accountant / Bookkeeper", r"\bbókari\b|\baðalbókari\b|bókhaldsfulltrú|\baccountant\b|bookkeep", ("Bókari", "Aðalbókari")),
    ProfessionRule("auditor", "Auditor", r"endurskoð|\bauditor\b", ("Endurskoðandi",)),
    ProfessionRule("payroll-specialist", "Payroll Specialist", r"launafulltrú|launasérfræð|payroll", ("Launafulltrúi",)),
    ProfessionRule("lawyer", "Lawyer", r"lögfræð|\blawyer\b|\battorney\b", ("Lögfræðingur",)),
    ProfessionRule("architect", "Architect", r"\barkitekt\b|\barchitect\b", ("Arkitekt",)),
    ProfessionRule("graphic-designer", "Graphic Designer", r"grafísk.*hönnuð|graphic design", ("Grafískur hönnuður",)),
    ProfessionRule("hr-specialist", "HR Specialist", r"mannauðs(?:ráðgjaf|sérfræð|fulltrú)|\bhr specialist\b|human resources specialist", ("Mannauðsráðgjafi",)),
    ProfessionRule("financial-analyst", "Financial Analyst", r"fjármála(?:sérfræð|ráðgjaf|grein)|\bfinancial analyst\b|\bfinance specialist\b", ("Fjármálafræðingur",)),
    ProfessionRule("civil-engineer", "Civil Engineer", r"byggingarverkfræð|burðarvirkja|\bcivil engineer\b", ("Byggingarverkfræðingur",)),
    ProfessionRule("engineer", "Engineer", r"\bverkfræðingur\b|tæknifræðingur|\bmechanical engineer\b|\belectrical engineer\b", ("Verkfræðingur", "Tæknifræðingur")),
    ProfessionRule("project-manager", "Project Manager", r"verkefnastjór|\bproject manager\b", ("Verkefnastjóri",)),
    ProfessionRule("marketing-specialist", "Marketing Specialist", r"markaðs(?:fulltrú|sérfræð|ráðgjaf)|marketing (?:specialist|coordinator|consultant)", ("Markaðsfulltrúi",)),
    ProfessionRule("digital-marketer", "Digital Marketing Specialist", r"stafræn.*markaðs|digital marketing|\bseo specialist\b", ("Sérfræðingur í stafrænni markaðssetningu",)),
    ProfessionRule("account-manager", "Account Manager", r"viðskiptastjór|\baccount manager\b|\bkey account\b", ("Viðskiptastjóri",)),
    ProfessionRule("sales-manager", "Sales Manager", r"sölustjór|\bsales manager\b", ("Sölustjóri",)),
    ProfessionRule("marketing-manager", "Marketing Manager", r"markaðsstjór|marketing manager", ("Markaðsstjóri",)),
    ProfessionRule("finance-manager", "Finance Manager", r"fjármálastjór|finance manager|cfo\b", ("Fjármálastjóri",)),
    ProfessionRule("hr-manager", "HR Manager", r"mannauðsstjór|\bhr manager\b", ("Mannauðsstjóri",)),
    ProfessionRule("operations-manager", "Operations Manager", r"rekstrarstjór|operations manager", ("Rekstrarstjóri",)),
    ProfessionRule("department-manager", "Department Manager", r"deildarstjór|forstöðumaður|sviðsstjór|department manager", ("Deildarstjóri", "Forstöðumaður")),
    ProfessionRule("team-lead", "Team Lead", r"teymisstjór|vaktstjór|team lead|shift manager", ("Teymisstjóri",)),
    ProfessionRule("managing-director", "Managing Director", r"framkvæmdastjór|managing director|\bceo\b", ("Framkvæmdastjóri",)),
    ProfessionRule("office-administrator", "Office Administrator", r"skrifstofufulltrú|skrifstofustarf|office admin|administrative assistant|\britari\b", ("Skrifstofufulltrúi", "Ritari")),
)

_COMPILED = [(rule, re.compile(rule.title, re.I)) for rule in RULES]
_BY_TAG: dict[str, list[ProfessionRule]] = {}
for _rule in RULES:
    for _tag in _rule.tags:
        _BY_TAG.setdefault(_tag.casefold(), []).append(_rule)

# A broad activity tag does not establish an occupation. These specific source
# tags can be used alone when they identify one and only one profession here.
TAG_ONLY_ALLOW = {
    "Hjúkrunarfræðingur", "Sjúkraliði", "Sérfræðilæknir", "Læknir",
    "Sjúkraþjálfari", "Iðjuþjálfi", "Sálfræðingur", "Félagsráðgjafi",
    "Lyfjafræðingur", "Lyfjatæknir", "Leikskólakennari", "Grunnskólakennari",
    "Framhaldsskólakennari", "Skólaliði", "Skólastjóri", "Leikskólastjóri",
    "Kokkur", "Barþjónn", "Kaffibarþjónn", "Rafvirki", "Bifvélavirki",
    "Pípulagningamaður", "Bókari", "Lögfræðingur", "Endurskoðandi",
    "Launafulltrúi", "Framkvæmdastjóri", "Sölustjóri", "Markaðsstjóri",
    "Fjármálastjóri", "Mannauðsstjóri", "Verslunarstjóri",
}
_TAG_ONLY = {tag.casefold() for tag in TAG_ONLY_ALLOW}


def classify_profession(title: str, source_tags: set[str]) -> tuple[str | None, str | None]:
    """Return a provisional canonical key and auditable evidence method.

    These rules have not been calibrated against human-labelled examples, so
    they deliberately do not claim a numeric probability or confidence.
    """
    normalized = title.strip()
    if re.search(r"almenn umsókn|general application|open application", normalized, re.I):
        return None, None
    tags = {tag.casefold() for tag in source_tags}
    for rule, pattern in _COMPILED:
        if pattern.search(normalized):
            corroborated = bool(tags.intersection(tag.casefold() for tag in rule.tags))
            return rule.key, "title+source_tag" if corroborated else "title_rule"
    candidates = {rule.key for tag in tags.intersection(_TAG_ONLY) for rule in _BY_TAG.get(tag, ())}
    if len(candidates) == 1:
        return next(iter(candidates)), "specific_source_tag"
    return None, None
