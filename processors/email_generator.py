"""
Email Generator — Claude writes the full hyper-personalized cold email.
Each email is unique and researched for the specific business.
Per-service required elements ensure every email hits the right points.
"""
import logging
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, AGENCY_NAME, AGENCY_EMAIL, AGENCY_WEBSITE,
    AGENT_NAME, SERVICES, SERVICE_TARGETS
)

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

_CHATBOT_BASE = "https://astiscale-chatbot.up.railway.app"

# ── Industry → demo URL mapping (pick closest matching demo by feel/industry) ──
INDUSTRY_DEMO_MAP = {
    # Medical / clinical
    "odontologas":              f"{_CHATBOT_BASE}/demo/sypsenaok",
    "veterinarija":             f"{_CHATBOT_BASE}/demo/sypsenaok",
    # Beauty / wellness
    "grožio salonas":           f"{_CHATBOT_BASE}/demo/auraplus",
    "kirpykla":                 f"{_CHATBOT_BASE}/demo/auraplus",
    "masažo salonas":           f"{_CHATBOT_BASE}/demo/auraplus",
    "nagų salonas":             f"{_CHATBOT_BASE}/demo/auraplus",
    "sporto klubas":            f"{_CHATBOT_BASE}/demo/auraplus",
    # Hospitality / F&B
    "restoranas":               f"{_CHATBOT_BASE}/demo/auraplus",
    "kavinė":                   f"{_CHATBOT_BASE}/demo/auraplus",
    "viešbutis":                f"{_CHATBOT_BASE}/demo/auraplus",
    # Retail / boutique
    "picerija":                 f"{_CHATBOT_BASE}/demo/spkrautuvele",
    # Professional B2B / services
    "advokatų kontora":         f"{_CHATBOT_BASE}/demo/klinkera",
    "buhalterinės paslaugos":   f"{_CHATBOT_BASE}/demo/klinkera",
    "nekilnojamasis turtas":    f"{_CHATBOT_BASE}/demo/klinkera",
    "saugos paslaugos":         f"{_CHATBOT_BASE}/demo/klinkera",
    "statybos":                 f"{_CHATBOT_BASE}/demo/klinkera",
    "interjero dizainas":       f"{_CHATBOT_BASE}/demo/klinkera",
}
_DEFAULT_DEMO = f"{_CHATBOT_BASE}/demo/klinkera"

def get_demo_url(industry: str) -> str:
    """Return the best-matching demo URL for this industry."""
    return INDUSTRY_DEMO_MAP.get(industry.lower(), _DEFAULT_DEMO)

# ── Per-service required elements (what Claude MUST include in every email) ────
SERVICE_REQUIREMENTS = {
    "chatbot": {
        "must_include": [
            "Konkreti pastaba apie JŲ verslą — ką pastebėjai apie jų svetainę, darbo laiką, ar kaip jie priima klientus",
            "Skausmo taškas: klientai rašo vakare/savaitgaliais kai verslas nedirba — niekas neatsakinėja",
            "CTA: paklausti ar norėtų kad SUKURTUM jiems nemokamą AI asistento demo — specialiai pagal jų verslą, be jokių įsipareigojimų. Jei patiks — gali svarstyti toliau. Jei ne — nieko nepraranda.",
            "NEKALBĖTI apie kainą pirmame laiške",
            "Pabrėžti: demo sukuriamas BŪTENT jiems, ne bendras — pagal jų verslą, klausimus, stilių",
        ],
        "avoid": [
            "Neminėk kainos pirmame laiške",
            "Nesiūlyk jau paruošto demo — KLAUSK ar sukurti jiems naują",
            "Neišgalvok statistikų ar skaičių apie jų verslą",
            "Neminėk kitų paslaugų (svetainės, reklamos)",
            "Nenaudok žodžių: 'inovatyvus', 'revoliucinis', 'sinergija'",
        ],
    },
    "website": {
        "must_include": [
            "Konkreti pastaba apie JŲ svetainę — kas pasenę, kas neveikia, kas atrodo blogai mobiliajame",
            "Skausmo taškas: pasenusi/lėta/neturima svetainė = prarasti klientai Google paieškoje",
            "Sprendimas: moderni svetainė su SEO, mobiliuoju pritaikymu, per 2 savaites",
            "Kaina: nuo €499",
            "CTA: 15 min pokalbis",
        ],
        "avoid": [
            "Neminėk chatbot ar kitų paslaugų",
            "Neišgalvok faktų apie jų svetainę kurių nežinai",
        ],
    },
    "meta_ads": {
        "must_include": [
            "Konkreti pastaba apie jų verslą arba industriją mieste",
            "Skausmo taškas: potencialūs klientai mieste kasdien ieško tokių paslaugų, bet neranda JŲ",
            "Sprendimas: Facebook/Instagram reklama tiksliai tų žmonių mieste kurie ieško jų paslaugų",
            "Kaina: nuo €299/mėn valdymas",
            "CTA: 15 min pokalbis apie galimybes",
        ],
        "avoid": [
            "Neminėk chatbot ar svetainės kūrimo",
            "Neišgalvok reklamos rezultatų ar statistikų",
        ],
    },
    "verslo_valdymas": {
        "must_include": [
            "Konkreti pastaba apie jų veiklos specifiką (transportas/logistika/gamyba/statyba)",
            "Skausmo taškas: rankinis darbas — maršrutai, dokumentai, darbo laikas — eikvojamas laikas",
            "Sprendimas: sistema automatizuoja jų konkrečius procesus",
            "Kaina: nuo €299/mėn",
            "CTA: 15 min pokalbis",
        ],
        "avoid": [
            "Neminėk chatbot ar reklamos",
            "Neišgalvok skaičių apie jų verslą",
        ],
    },
}

# ── System prompt (stays cached) ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""Tu esi {AGENT_NAME} iš {AGENCY_NAME} — Lietuvos AI agentūros įkūrėjas.
Rašai TIKRUS šaltus el. laiškus realiems Lietuvos verslininkams LIETUVIŠKAI.

ESMINIS PRINCIPAS: Laiškas turi atrodyti kaip TU asmeniškai pažiūrejai į JŲ verslą ir parašei jiems — ne šablonas, ne masinė siuntinėjimas. Natūrali lietuvių kalba, kaip rašytų tikras lietuvis.

PRIVALOMA STRUKTŪRA:
1. Tema: konkreti, iki 55 simbolių — klausimas arba pastebėjimas apie JŲ verslą
2. Kreipinys: vardu jei žinomas, "Laba diena!" jei ne
3. Atidarymas (1-2 sakiniai): konkreti pastaba apie JŲ verslą — ką pastebėjai
4. Problemos sakinys (1-2 sakiniai): prarastos galimybės — natūraliai, be dramos
5. Sprendimas (1-2 sakiniai): trumpai ką siūlai — BEZ KAINOS pirmame laiške
6. CTA: pasiūlyk pažiūrėti NEMOKAMĄ demo — įdėk DEMO_URL nuorodą tekste
7. Parašas: {AGENT_NAME} | {AGENCY_NAME} | {AGENCY_EMAIL} | {AGENCY_WEBSITE}

LIETUVIŠKOS KALBOS TAISYKLĖS (LABAI SVARBU):
- Rašyk kaip tikras lietuvis — natūralūs sakiniai, teisingi linksniai, taisyklinga rašyba
- Naudok lietuviškus žodžius: "puiku" ne "ok", "pavyzdžiui" ne "pvz.", taisyklingos galūnės
- Jokio vertimo iš anglų — jokie "šitas yra geras" tipo konstrukcijos
- Tonas: šiltas, draugiškas, tikras — kaip žinutė pažįstamam verslininkui
- Jokių buzzwordų: "inovatyvus", "revoliucinis", "holistinis", "sinergija"
- Jokių frazių: "Tikimės bendradarbiauti", "Džiaugiuosi galimybe", "Esu įsitikinęs"
- Ilgis: 110–160 žodžių. NE ILGIAU.

Grąžink TIK laišką — be komentarų, be metaduomenų."""


def generate_email(lead, service_keys: list[str], service_target: str = "") -> str:
    """
    Generate a hyper-personalized cold email for a BusinessLead.
    Claude writes the full email based on rich business context + per-service requirements.
    """
    vadovas_first = lead.vadovas.split()[0] if lead.vadovas else ""

    # Pick primary service
    valid_keys = [k for k in service_keys if k in SERVICES]
    primary_key = valid_keys[0] if valid_keys else None
    if primary_key:
        svc = SERVICES[primary_key]
        service_text = f"{svc['lt']} ({svc['price']}): {svc['pitch_lt']}"
    else:
        service_text = "skaitmeninės rinkodaros paslauga"

    # Map to requirements
    req_key = service_target if service_target in SERVICE_REQUIREMENTS else (
        primary_key if primary_key in SERVICE_REQUIREMENTS else None
    )
    requirements = SERVICE_REQUIREMENTS.get(req_key, {})
    must_include = requirements.get("must_include", [])
    avoid = requirements.get("avoid", [])

    # Website situation research context
    if lead.website_status == "none":
        website_context = f"{lead.company_name} neturi svetainės internete."
        research_note = "Jų nėra Google paieškoje. Potencialūs klientai jų neranda."
    elif lead.website_status == "old":
        year_note = f" (~{lead.website_year} m.)" if lead.website_year else ""
        website_context = f"{lead.company_name} svetainė pasenusi{year_note}."
        research_note = "Svetainė neatnaujinta, gali blogai rodyti mobiliajame, galbūt lėta."
    elif lead.website_status == "unreachable":
        website_context = f"{lead.company_name} svetainė neveikia arba lėtai kraunasi."
        research_note = "Lankytojai negali pasiekti svetainės arba ji palieka blogą įspūdį."
    else:
        website_context = f"{lead.company_name} turi veikiančią svetainę."
        research_note = "Svetainė veikia — fokusas į konversiją ir klientų aptarnavimą."

    # Build requirements block for prompt
    must_block = ""
    if must_include:
        items = "\n".join(f"  • {item}" for item in must_include)
        must_block = f"\nŠIAME LAIŠKE PRIVALOMA ĮTRAUKTI:\n{items}"

    avoid_block = ""
    if avoid:
        items = "\n".join(f"  • {item}" for item in avoid)
        avoid_block = f"\nVENGTI:\n{items}"

    demo_block = ""

    user_prompt = f"""Parašyk personalizuotą šaltą el. laišką:

TYRIMŲ DUOMENYS APIE ĮMONĘ:
  Pavadinimas: {lead.company_name}
  Miestas: {lead.city.capitalize() if lead.city else 'Lietuva'}
  Industrija: {lead.industry}
  Vadovas: {vadovas_first or '(nežinomas)'}
  Interneto situacija: {website_context}
  Pastaba: {research_note}

SIŪLOMA PASLAUGA (TIKTAI ŠI):
  {service_text}
{must_block}
{avoid_block}
{demo_block}

Formato reikalavimai:
Tema: [konkreti tema iki 55 simbolių]

[Laiškas]

Pagarbiai,
{AGENT_NAME}
{AGENCY_NAME}
{AGENCY_EMAIL}
{AGENCY_WEBSITE}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text.strip()

    except Exception as e:
        logger.error(f"Email generation failed for {lead.company_name}: {e}")
        return _fallback_email(lead, valid_keys, vadovas_first)


def _fallback_email(lead, service_keys: list[str], vadovas_first: str) -> str:
    """Static fallback template if Claude API fails."""
    services_lt = " + ".join(SERVICES[k]["lt"] for k in service_keys if k in SERVICES)
    greeting = f"Laba diena{', ' + vadovas_first if vadovas_first else ''}!"

    if lead.website_status == "none":
        observation = (
            f"pastebėjau, kad {lead.company_name} šiuo metu neturi svetainės internete. "
            "Potencialūs klientai ieško paslaugų Google — ir jei ten jūsų nėra, jie randa konkurentus."
        )
    elif lead.website_status in ("old", "unreachable"):
        observation = (
            f"apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji galėtų būti atnaujinta. "
            "Pasenusi svetainė dažnai atbaido klientus dar prieš pirmą skambutį."
        )
    else:
        observation = (
            f"žiūrėjau {lead.company_name} veiklą internete ir manau, kad galėtumėte gauti "
            "daugiau klientų su tinkamomis skaitmeninėmis priemonėmis."
        )

    return f"""Tema: {lead.company_name} — klausimas

{greeting}

Rašau iš {AGENCY_NAME} — {observation}

Siūlome: {services_lt}.

Ar turėtumėte 15 minučių trumpam pokalbiui šią savaitę?

Pagarbiai,
{AGENT_NAME}
{AGENCY_NAME}
{AGENCY_EMAIL}
{AGENCY_WEBSITE}"""
