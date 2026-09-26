export type Language = 'is' | 'en';

export function preferredLanguage(): Language {
  try {
    const saved = window.localStorage.getItem('vinnsyn-language');
    if (saved === 'is' || saved === 'en') return saved;
  } catch { /* Storage is optional; browser preference is still useful. */ }
  return navigator.languages.some(language => language.toLowerCase().startsWith('is')) ? 'is' : 'en';
}

export function setPreferredLanguage(language: Language) {
  try { window.localStorage.setItem('vinnsyn-language', language); } catch { /* Keep the in-session choice. */ }
  document.documentElement.lang = language === 'is' ? 'is' : 'en';
}

const icelandicFields: Record<string, string> = {
  'Health & care': 'Heilbrigðis- og umönnunarstörf',
  Technology: 'Tækni',
  'Education & research': 'Menntun og rannsóknir',
  'Hospitality & food': 'Veitinga- og ferðaþjónusta',
  'Industrial & trades': 'Iðnaður og iðngreinar',
  'Customer service': 'Þjónusta við viðskiptavini',
  'Professional services': 'Sérfræðistörf',
  Administration: 'Skrifstofu- og stjórnsýslustörf',
  Management: 'Stjórnun',
  'Sales & marketing': 'Sala og markaðsmál',
  'Not yet classified': 'Ekki enn flokkað',
};

export function localizeField(language: Language, label: string) {
  return language === 'is' ? icelandicFields[label] ?? label : label;
}

// Terms that are idiomatic in English (SQL, Python, React, GDPR and so on)
// intentionally remain unchanged. This is a display translation only: the
// archived source value is never rewritten.
const icelandicSkills: Record<string, string> = {
  'Customer Service': 'Þjónusta við viðskiptavini', Sales: 'Sala', Recruitment: 'Ráðningar', Nursing: 'Hjúkrun',
  'Project Management': 'Verkefnastjórnun', 'Counter service': 'Afgreiðsla', Procurement: 'Innkaup', Accounting: 'Bókhald', Marketing: 'Markaðsmál',
  'Human Resources': 'Mannauðsmál', 'Kitchen work': 'Eldhússtörf', Healthcare: 'Heilbrigðisþjónusta', Leadership: 'Leiðtogafærni',
  'Health and Safety': 'Heilbrigði og öryggi', Agile: 'Sveigjanleg aðferðafræði', 'General technical skills': 'Almenn tæknikunnátta',
  'Delivery driving': 'Akstur við dreifingu', 'Data Analysis': 'Gagnagreining', 'Warehouse operations': 'Vöruhúsastörf', Auditing: 'Endurskoðun',
  'Public administration': 'Opinber stjórnsýsla', Planning: 'Skipulagning', Statistics: 'Tölfræði', 'Financial closing': 'Ársuppgjör',
  'Process implementation': 'Innleiðing ferla', Payroll: 'Launavinnsla', 'Auto mechanics': 'Bifvélavirkjun', Cleaning: 'Þrif',
  'Strategy development': 'Stefnumótun', Bartending: 'Barþjónusta', 'Artificial Intelligence': 'Gervigreind', 'Report writing': 'Skýrslugerð',
  'Goods transport': 'Vöruflutningar', Invoicing: 'Reikningagerð', 'Process design': 'Ferlahönnun', 'Table service': 'Borðþjónusta',
  Cybersecurity: 'Netöryggi', 'Engine repair': 'Vélaviðgerðir', Merchandising: 'Vöruframsetning', 'Steel fabrication': 'Stálvinnsla',
  'Digital marketing': 'Stafræn markaðssetning', 'Lubrication service': 'Smurþjónusta', 'IT Project Management': 'Upplýsingatækniverkefnastjórnun',
  'First Aid': 'Skyndihjálp', 'Customer relationships': 'Viðskiptatengsl', 'Annual financial statements': 'Ársreikningar',
  'Automotive electrical repair': 'Rafmagnsviðgerðir ökutækja', 'Research data processing': 'Vinnsla rannsóknargagna', Carpentry: 'Trésmíði',
  Budgeting: 'Fjárhagsáætlanagerð', 'Risk analysis': 'Áhættugreining', 'Tire service': 'Hjólbarðaþjónusta', Plumbing: 'Pípulagnir',
  'Quality management systems': 'Gæðastjórnunarkerfi', 'Website administration': 'Vefumsjón',
};

export function localizeSkill(language: Language, label: string) {
  return language === 'is' ? icelandicSkills[label] ?? label : label;
}

export function translations(language: Language) {
  const is = language === 'is';
  return {
    locale: is ? 'is-IS' : 'en-GB',
    languageName: is ? 'Íslenska' : 'English',
    developmentBadge: is ? 'Í þróun' : 'In development',
    developmentNotice: is ? {
      title: 'Vinnsýn er í þróun',
      body: 'Vinnsýn er enn í virkri þróun. Gögn, flokkun starfa og greining færni eru í stöðugri vinnslu og geta því innihaldið villur eða ófullkomna flokkun. Umfang gagnasafnsins er einnig enn að aukast.',
      otherTitle: 'Vinnsýn is in development',
      otherBody: 'Vinnsýn is still under active development. Job and skill classifications are being refined and may contain errors or incomplete classifications, and coverage of the underlying dataset is still expanding.',
      continue: 'Halda áfram í Vinnsýn',
      dialogLabel: 'Upplýsingar um þróunarstöðu Vinnsýnar',
    } : {
      title: 'Vinnsýn is in development',
      body: 'Vinnsýn is still under active development. Job and skill classifications are being refined and may contain errors or incomplete classifications, and coverage of the underlying dataset is still expanding.',
      otherTitle: 'Vinnsýn er í þróun',
      otherBody: 'Vinnsýn er enn í virkri þróun. Gögn, flokkun starfa og greining færni eru í stöðugri vinnslu og geta því innihaldið villur eða ófullkomna flokkun. Umfang gagnasafnsins er einnig enn að aukast.',
      continue: 'Continue to Vinnsýn',
      dialogLabel: 'Vinnsýn development notice',
    },
    switchLanguage: is ? 'Skipta yfir á ensku' : 'Switch to Icelandic',
    brandDescription: is ? 'Vinnsýn, skoða allan vinnumarkaðinn' : 'Vinnsýn, view the whole market',
    masthead: is ? 'Mæling á störfum á Íslandi' : 'An observed view of work in Iceland',
    loading: is ? 'Les vinnumarkaðinn…' : 'Reading the market…',
    back: is ? '← Til baka' : '← Back',
    backLabel: is ? 'Fara til baka í skoðunarferlinu' : 'Go back in interaction history',
    scope: is ? 'Svið' : 'Scope',
    market: is ? 'Markaður' : 'Market',
    remove: (label: string) => is ? `Fjarlægja afmörkun: ${label}` : `Remove ${label} constraint`,
    more: (count: number) => is ? ` + ${count} í viðbót` : ` + ${count} more`,
    viewBy: is ? 'Skoða eftir' : 'View by',
    lenses: is ? { fields: 'Svið', professions: 'Starfsgreinar', skills: 'Færni', geography: 'Staðsetning', employers: 'Atvinnurekendur' } : { fields: 'Fields', professions: 'Professions', skills: 'Skills', geography: 'Geography', employers: 'Employers' },
    detailedTrend: is ? 'Nánari þróun ↗' : 'Detailed trend ↗',
    trendUnavailable: is ? 'Ekki eru nægar dagsettar athuganir á þessu sviði til að sýna áreiðanlega þróun.' : 'Trend needs more dated observations in this scope.',
    time: is ? 'Tími' : 'Time',
    all: is ? 'Allt' : 'All',
    allAvailableTime: is ? 'Allur tiltækur tími' : 'All available time',
    startYear: is ? 'Upphafsár' : 'Start year',
    endYear: is ? 'Lokaár' : 'End year',
    thinCoverage: (years: string) => is ? `Gagnasafnið er gisnara árin ${years}. Ódagsettar auglýsingar birtast aðeins þegar allt tímabilið er valið.` : `Thin archive coverage in ${years}. Undated listings appear only in All.`,
    archiveOverline: is ? 'Íslenska starfaauglýsingasafnið' : 'The Icelandic job archive',
    listingsObserved: is ? 'auglýsingar skráðar.' : 'listings observed.',
    openingThought: is ? 'Sýn yfir það sem Ísland\nhefur verið að ráða í.' : 'A view of what Iceland\nhas been hiring for.',
    openingDescription: is ? 'Einn punktur fyrir hverja auglýsingu í safninu.\nÞetta er sýn á safnið, ekki allan íslenskan vinnumarkað.' : 'One point for every archived listing.\nAn archive view, not all of Icelandic hiring.',
    exploreMarket: is ? 'Skoða vinnumarkaðinn' : 'Explore the market',
    watchIceland: is ? 'Sjá störfin lýsa upp Ísland ↗' : 'Watch the jobs light up Iceland ↗',
    reorganizedByField: is ? 'endurskipulagt eftir starfssviði' : 'reorganized by field',
    whereWorkGathers: is ? 'Þar sem störfin safnast saman.' : 'Where work gathers.',
    listingsInScope: (count: string) => is ? `${count} auglýsingar í safninu á þessu sviði, flokkaðar eftir starfssviði.` : `${count} archived listings in this scope, organized by field.`,
    exploreFields: is ? 'Skoða starfssvið' : 'Explore fields of work',
    inspectGroup: is ? 'skoða flokk' : 'inspect group',
    listings: is ? 'auglýsingar' : 'listings',
    closerLook: is ? 'Nánar skoðað' : 'A closer look',
    archivedListings: is ? 'auglýsingar í safninu' : 'archived listings',
    ofScope: is ? 'af þessu sviði' : 'of this scope',
    unclassifiedDescription: is ? 'Ekkert starfssvið frá uppruna fannst í þessari útgáfu safnsins.' : 'No source job area was found in this snapshot.',
    categoryDescription: is ? 'Hver auglýsing birtist hér á einu sviði, þótt uppruninn hafi merkt hana með fleiri en einu.' : 'Each listing appears in one field here, even if the source assigned more than one.',
    chooseField: is ? 'Veldu annað starfssvið' : 'Explore another field',
    anotherView: is ? 'önnur leið til að sjá sömu störfin' : 'another way of seeing the same jobs',
    workByProfession: is ? 'Störf eftir starfsgrein.' : 'Work, by profession.',
    professionIntro: (count: string) => is ? `${count} auglýsingar, nú flokkaðar eftir starfsgrein. Veldu stjörnuþyrpingu til að skoða nánar.` : `${count} listings now regrouped by occupation. Select a constellation to continue exploring.`,
    provisionalClassified: (coverage: string, count: string) => is ? `${coverage}% flokkuð til bráðabirgða · ${count} enn óflokkuð` : `${coverage}% provisionally classified · ${count} remain unclassified`,
    professionsIn: (name: string) => is ? `Starfsgreinar í ${name}` : `Professions in ${name}`,
    namedProfessions: (count: number, unclassified: string) => is ? `Stærstu ${count} nafngreindu starfsgreinarnar · ${unclassified} óflokkaðar athuganir varðveittar. Merkingar eru til bráðabirgða.` : `Largest ${count} named professions · ${unclassified} unclassified observations retained. Labels are provisional.`,
    exploreSmallerProfessions: (count: number) => is ? `Skoða ${count} minni starfsgreinar` : `Explore ${count} smaller professions`,
    profession: is ? 'starfsgrein' : 'profession',
    classifiedListings: is ? 'flokkaðar auglýsingar á þessu sviði' : 'classified listings in this scope',
    professionDescription: is ? 'Bráðabirgðaflokkun á titlum og starfsgreinamerkjum frá upprunanum. Þetta er hluti safnsins, ekki mat á öllum störfum á Íslandi.' : 'A provisional grouping of observed titles and source occupation tags. This is an archive subset, not an estimate of all jobs in Iceland.',
    noSkillEvidence: is ? 'Engar skýrar vísbendingar um faglega færni eru tiltækar fyrir þetta úrtak enn.' : 'No explicit professional skill evidence is available for this subset yet.',
    anotherProfession: (name: string) => is ? `Önnur starfsgrein í ${name}` : `Another profession in ${name}`,
    advertiser: is ? 'auglýsandi' : 'advertiser',
    recruitmentIntermediaryDescription: is ? 'Þetta nafn tilheyrir ráðningarmiðlara. Sumar auglýsingar geta verið fyrir viðskiptavini hans; safnið tilgreinir ekki alltaf endanlegan atvinnurekanda.' : 'This name belongs to a recruitment intermediary. Some listings may be for clients; the archive does not consistently identify the final employer.',
    unidentifiedEmployerDescription: is ? 'Uppruninn greindi ekki frá fyrirtæki eða stofnun fyrir þessar auglýsingar.' : 'The source did not identify an organization for these listings.',
    employerDescription: is ? 'Þessar auglýsingar bera nafn þessa auglýsanda. Uppruninn staðfestir ekki alltaf endanlegan ráðningaraðila.' : 'These listings carry this advertiser name. The source does not always establish the final hiring organization.',
    gatheredByAdvertiser: is ? 'sömu athuganir, flokkaðar eftir auglýsanda' : 'the same observations, gathered by advertiser',
    whoPosted: is ? 'Hver birti störfin?' : 'Who posted these jobs?',
    advertisersIntro: (listings: string, advertisers: string) => is ? `${listings} auglýsingar í safninu frá ${advertisers} nafngreindum auglýsendum á þessu sviði.` : `${listings} archived listings across ${advertisers} named advertisers in this scope.`,
    advertiserCaveat: is ? 'Þéttleikinn sýnir skráðar auglýsingar, ekki stærð fyrirtækja. Minni auglýsendur mynda sviðið í kring.' : 'Concentrations show observed listings, not company size. Smaller advertisers form the surrounding field.',
    exploreAdvertisers: (name: string) => is ? `Skoða auglýsendur í ${name}` : `Explore advertisers in ${name}`,
    intermediary: is ? 'ráðningarmiðlari' : 'intermediary',
    employerNotIdentified: is ? 'Atvinnurekandi óþekktur' : 'Employer not identified',
    exploreNamedAdvertisers: (count: string) => is ? `Skoða ${count} nafngreinda auglýsendur` : `Explore ${count} named advertisers`,
    findAdvertiser: is ? 'Finna auglýsanda á þessu sviði' : 'Find an advertiser in this scope',
    advertiserName: is ? 'Nafn auglýsanda' : 'Advertiser name',
    noAdvertiserMatch: is ? 'Enginn auglýsandi á þessu sviði ber þetta nafn.' : 'No advertiser in this scope matches that name.',
    showMore: is ? 'Sýna 20 til viðbótar' : 'Show 20 more',
    advertiserNote: is ? 'Nöfn auglýsenda · ráðningarmiðlarar geta komið fram fyrir hönd viðskiptavina · óþekktar auglýsingar varðveittar' : 'Advertiser names · recruiters may represent client organizations · unidentified listings retained',
    located: is ? 'sömu athuganir, staðsettar' : 'the same observations, located',
    whereJobsAppear: is ? 'Þar sem þessi störf birtast.' : 'Where these jobs appear.',
    whereJobsGather: is ? 'Þar sem störfin safnast saman.' : 'Where the jobs gather.',
    listingsInGroup: is ? 'auglýsingar í þessum flokki' : 'listings in this group',
    listingsInPlace: is ? 'auglýsingar á þessum stað' : 'listings in this place',
    mapDescription: (coverage: string) => is ? `${coverage}% eru með kortanlegt örnefni. Punktar safnast um miðju hvers staðar; dreifingin sýnir umfang, ekki nákvæmt heimilisfang.` : `${coverage}% have a mappable named place. Points gather around place centroids; their spread shows volume, not address precision.`,
    placeDescription: (kind: string) => is ? `Sýnt um miðpunkt ${kind}, ekki nákvæmt vinnustaðarheimilisfang.` : `Shown around a ${kind} reference point, not an exact workplace address.`,
    nonspatialDescription: (name: string) => is ? `Auglýsingar merktar ${name} eru varðveittar í safninu en falla utan staðakortsins.` : `${name} listings remain in the archive, outside the place map.`,
    selectedLocation: (name: string) => is ? `Valið: ${name}` : `Selected ${name}`,
    exploreLocations: (name: string) => is ? `Skoða staði fyrir ${name}` : `Explore locations for ${name}`,
    centroid: is ? 'miðpunktur' : 'centroid',
    alsoInArchive: is ? 'Einnig í safninu' : 'Also in the archive',
    exploreOtherPlaces: (count: number) => is ? `Skoða ${count} önnur örnefni` : `Explore ${count} other named places`,
    mapNote: is ? 'Miðpunktar örnefna · dreifing þéttleika til að bæta læsileika · Natural Earth / GeoNames' : 'Named place centroids · density spread for readability · Natural Earth / GeoNames',
    observedScope: is ? 'athugað svið' : 'observed scope',
    explicitSkills: is ? 'skýr fagleg færni' : 'explicit professional skills',
    skillsInMotion: is ? 'Færni á hreyfingu.' : 'Skills in motion.',
    skillIntro: (name: string) => is ? `Daufu punktarnir eru auglýsingar á ${name === 'íslenski vinnumarkaðurinn' ? 'íslenskum vinnumarkaði' : name}. Veldu færni til að sjá hvaða athuganir tengja hana við aðra.` : `The faint particles are listings in ${name}. Select a skill to see which observations connect it to others.`,
    skillHint: is ? 'Hver merkt hringur dregur saman eina færni; stærð hans sýnir fjölda tilvika. Tengingar sem birtast sýna færni sem fannst í sömu auglýsingum.' : 'Each labeled circle summarizes a skill; its size reflects mentions. Revealed connections show skills found in the same listings.',
    ecosystem: is ? 'Vistkerfi' : 'Ecosystem',
    trend: is ? 'Þróun' : 'Trend',
    oftenMentioned: is ? 'Oft nefnd samhliða' : 'Often mentioned alongside',
    sharedListings: (count: number) => is ? `${count} sameiginlegar auglýsingar` : `${count} shared listings`,
    noSkillMentions: is ? 'Engin skýr umfjöllun um faglega færni fannst í þessu úrtaki enn.' : 'No explicit professional skill mentions were found in this subset yet.',
    exploreSkills: is ? 'Skoða færni' : 'Explore skills',
    otherMentions: is ? 'Aðrar skýrar færnivísbendingar frá uppruna' : 'Other explicit source mentions',
    shareAmong: (name: string) => is ? `Hlutfall meðal dagsettra auglýsinga í ${name}` : `Share among dated listings in ${name}`,
    trendOverline: (kind: string, name: string) => is ? `${kind} meðal dagsettra auglýsinga í ${name}` : `${kind} among dated listings in ${name}`,
    archiveYears: is ? 'ár safnsins' : 'archive years',
    recentQuarters: is ? 'nýliðnir heilir ársfjórðungar' : 'recent complete quarters',
    timeRange: is ? 'Tímabil' : 'Time range',
    allYears: is ? 'Öll ár' : 'All years',
    recentQuartersButton: is ? 'Nýlegir ársfjórðungar' : 'Recent quarters',
    trendMeasure: is ? 'Mælikvarði þróunar' : 'Trend measure',
    absolute: is ? 'Fjöldi' : 'Absolute',
    shareOfJobs: is ? 'Hlutfall starfa' : 'Share of jobs',
    compareWithCare: (periods: string, suffix: string) => is ? `Gagnasafnið er gisnara: ${periods}${suffix}. Berðu þessi tímabil saman með varúð.` : `Thin archive coverage: ${periods}${suffix}. Compare those periods with care.`,
    andOthers: is ? ' og önnur' : ' and others',
    inspect: (unit: string) => is ? `Skoða ${unit}` : `Inspect ${unit}`,
    year: is ? 'ár' : 'a year',
    quarter: is ? 'árs­fjórðung' : 'a quarter',
    basedOn: (source: string, count: string) => is ? `Byggt á ${source} · ${count} einstökum auglýsingum í safninu` : `Based on ${source} · ${count} unique archived listings`,
    sourceFields: is ? 'Eitt aðalsvið fyrir hverja auglýsingu' : 'One primary field per listing',
    snapshot: (date: string) => is ? `Útgáfa ${date}` : `Snapshot ${date}`,
  };
}
