"""Source registry for the AP government jobs aggregator.

Levels:  central | state | district
Kinds:   s3waas   -> NIC S3WaaS district site, standard recruitment notice category
         generic  -> server-rendered page; parsed with the tolerant generic parser
         portal   -> JS-heavy or auth-walled portal we cannot scrape cheaply;
                     surfaced in the UI as a "check directly" link and counted
                     in source-health so coverage gaps are visible, not silent.
"""

DISTRICTS = [
    ("Srikakulam", "srikakulam"),
    ("Parvathipuram Manyam", "manyam"),
    ("Vizianagaram", "vizianagaram"),
    ("Visakhapatnam", "visakhapatnam"),
    ("Alluri Sitharama Raju", "alluriseetharamaraju"),
    ("Anakapalli", "anakapalli"),
    ("Kakinada", "kakinada"),
    ("East Godavari", "eastgodavari"),
    ("Dr. B.R. Ambedkar Konaseema", "konaseema"),
    ("West Godavari", "westgodavari"),
    ("Eluru", "eluru"),
    ("Krishna", "krishna"),
    ("NTR", "ntr"),
    ("Guntur", "guntur"),
    ("Palnadu", "palnadu"),
    ("Bapatla", "bapatla"),
    ("Prakasam", "prakasam"),
    ("Sri Potti Sriramulu Nellore", "spsnellore"),
    ("Kurnool", "kurnool"),
    ("Nandyal", "nandyal"),
    ("Ananthapuramu", "ananthapuramu"),
    ("Sri Sathya Sai", "srisathyasai"),
    ("YSR Kadapa", "kadapa"),
    ("Annamayya", "annamayya"),
    ("Tirupati", "tirupati"),
    ("Chittoor", "chittoor"),
]


def build_sources():
    sources = []

    # ---- 26 district collectorate sites (uniform NIC S3WaaS platform) ----
    for name, slug in DISTRICTS:
        sources.append({
            "id": f"dist-{slug}",
            "name": f"{name} District Collectorate",
            "level": "district",
            "district": name,
            "kind": "s3waas",
            "url": f"https://{slug}.ap.gov.in/en/notice_category/recruitment/",
            "home": f"https://{slug}.ap.gov.in",
        })

    # ---- AP state government ----
    sources += [
        {
            "id": "appsc",
            "name": "APPSC — AP Public Service Commission",
            "level": "state", "district": None, "kind": "generic",
            "url": "https://psc.ap.gov.in/Notifications",
            "home": "https://psc.ap.gov.in",
        },
        {
            "id": "slprb",
            "name": "SLPRB — AP Police Recruitment Board",
            "level": "state", "district": None, "kind": "generic",
            "url": "https://slprb.ap.gov.in/Home.aspx",
            "home": "https://slprb.ap.gov.in",
        },
        {
            "id": "ap-cse",
            "name": "AP School Education / DSC",
            "level": "state", "district": None, "kind": "generic",
            "url": "https://cse.ap.gov.in/",
            "home": "https://cse.ap.gov.in",
        },
        {
            "id": "ap-hmfw",
            "name": "AP Health, Medical & Family Welfare",
            "level": "state", "district": None, "kind": "generic",
            "url": "https://hmfw.ap.gov.in/",
            "home": "https://hmfw.ap.gov.in",
        },
    ]

    # ---- Central government ----
    sources += [
        {
            "id": "upsc",
            "name": "UPSC — Union Public Service Commission",
            "level": "central", "district": None, "kind": "generic",
            "url": "https://upsc.gov.in/whats-new",
            "home": "https://upsc.gov.in",
        },
        {
            "id": "ssc",
            "name": "SSC — Staff Selection Commission",
            "level": "central", "district": None, "kind": "portal",
            "url": "https://ssc.gov.in",
            "home": "https://ssc.gov.in",
        },
        {
            "id": "rrb",
            "name": "Railway Recruitment Boards (RRB)",
            "level": "central", "district": None, "kind": "portal",
            "url": "https://www.rrbapply.gov.in",
            "home": "https://www.rrbapply.gov.in",
        },
        {
            "id": "ibps",
            "name": "IBPS — Banking Personnel Selection",
            "level": "central", "district": None, "kind": "generic",
            "url": "https://www.ibps.in/",
            "home": "https://www.ibps.in",
        },
    ]
    return sources
