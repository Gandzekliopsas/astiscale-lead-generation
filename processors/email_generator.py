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
            "Konkreti, tiksli pastaba apie jų situaciją internete — TIKTAI pagal faktus. Jei neturi svetainės — sakyk 'neturi savo svetainės', ne 'jūsų nėra Google'. Jie gali būti Google Maps, socialiniuose tinkluose.",
            "Draugiškas, šiltas tonas — kaip pažįstamas žmogus, kuris pastebėjo galimybę ir nori padėti",
            "Pasiūlyk sukurti NEMOKAMĄ demo svetainę — tikrą, veikiančią bandomąją versiją, kaip atrodytų jų naujas puslapis. Visiškai nemokama. Jei patiks — tada kalbame toliau. Jei ne — jokių įsipareigojimų, jokių išlaidų.",
            "CTA: paklausti ar norėtų pamatyti šią nemokamą demo svetainę. Įdėk DEMO URL.",
            "NEKALBĖTI apie kainą",
        ],
        "avoid": [
            "Neminėk kainos pirmame laiške",
            "Neminėk chatbot ar kitų paslaugų",
            "Neteigk kad jų 'nėra Google paieškoje' jei tai gali būti netiesa — sakyk 'neturi savo svetainės'",
            "Nesiūlyk '15 minučių skambučio'",
            "Nevartok: 'Jūsų konkurentai jau čia', 'kiekvienas mėnuo — tai išleista galimybė', 'Paprasta.'",
            "Nesiūlyk 'maketo eskizo' — siūlyk tikrą nemokamą demo svetainę",
            "Nekaltink ar negąsdink — siūlyk galimybę, ne problemą",
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
SYSTEM_PROMPT = f"""Tu esi {AGENT_NAME} iš {AGENCY_NAME} — Lietuvos skaitmeninės agentūros įkūrėjas.
Rašai TIKRUS šaltus el. laiškus realiems Lietuvos verslininkams LIETUVIŠKAI.

ESMINIS PRINCIPAS: Laiškas turi atrodyti kaip TU asmeniškai pažiūrejai į JŲ verslą ir parašei — ne šablonas, ne masinis siuntimas. Tonas: kaip pažįstamas, kuris pastebėjo galimybę ir ja dalinasi. Ne pardavėjas, ne gąsdintojas.

PRIVALOMA STRUKTŪRA:
1. Tema: konkreti, iki 55 simbolių — pastebėjimas arba klausimas. NIEKADA nepradėk "kodėl jūsų..." — tai kaltinantis tonas.
2. Kreipinys: vardu jei žinomas, "Laba diena!" jei ne
3. Atidarymas (1-2 sakiniai): konkreti, tiksli pastaba apie JŲ verslą — ką realiai pastebėjai
4. Galimybė (1-2 sakiniai): ką galima padaryti — be dramos, be bauginimo, natūraliai
5. Pasiūlymas (1-2 sakiniai): ką konkrečiai siūlai — BEZ KAINOS
6. CTA: paprašyk trumpo atsakymo. Įdėk pateiktą DEMO URL kaip nuorodą tekste.
7. Parašas: {AGENT_NAME} | {AGENCY_NAME} | {AGENCY_EMAIL} | {AGENCY_WEBSITE}

LIETUVIŠKA GRAMATIKA — DAŽNIAUSIOS KLAIDOS (PRIVALOMA ŽINOTI):
❌ NIEKADA nerašyk:
- "praranda" kai kalbama apie "jūs" → rašyk "prarandate"
- "gausime" kai siūlai kažką gavėjui → rašyk "gausite"
- "negranda" → rašyk "neranda"
- "bylotų" → rašyk "rodytų" arba "parodytų"
- "smagią dalį" — beprasmė frazė, nevartok
- "šitas" → rašyk "šis"
- Jokio vertimo iš anglų: "tai yra geras" → "tai gerai"

✅ GRAMATIKA:
- Veiksmažodžiai su "jūs": neranda**te**, praranda**te**, gaunate, matote, turite
- Veiksmažodžiai su "aš": pasiūlysiu, sukursiu, parodysiu, galiu
- Taisyklingi linksniai: "jūsų svetain**ė**", "jūsų verslui", "jūsų klientams"

TONAS — KO GRIEŽTAI VENGTI:
❌ "Jūsų konkurentai jau čia — ir klientai kreipiasi į juos"
❌ "Kiekvienas mėnuo — tai išleista galimybė"
❌ "Paprasta." (vienas žodis kaip sakinys — skamba arogantiškai)
❌ "kodėl klientai jūsų neranda?" (kaltinantis tonas)
❌ "Tai reiškia, kad žmonės jūsų apskritai neranda" (gali būti netiesa)

✅ VIETOJ TO:
- "Pastebėjau, kad [įmonės pavadinimas] dar neturi savo svetainės..."
- "Manau, kad su geru puslapiu galėtumėte pasiekti daugiau žmonių internete."
- "Norėčiau parodyti, kaip tai galėtų atrodyti."

DRAUDŽIAMI ŽODŽIAI: "inovatyvus", "revoliucinis", "holistinis", "sinergija", "optimizuoti", "ekosistema"
DRAUDŽIAMOS FRAZĖS: "Tikimės bendradarbiauti", "Džiaugiuosi galimybe", "Esu įsitikinęs", "15 minučių skambutis"

ILGIS: 100–150 žodžių. NE ILGIAU.
KAINA: Jokių skaičių susijusių su mokėjimu pirmame laiške.

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
        website_context = f"{lead.company_name} neturi savo svetainės."
        research_note = "Jie veikia ir turi klientų, bet internete neturi savo puslapio — tik galbūt socialiniai tinklai ar katalogai. Tai galimybė."
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

    # For chatbot service: include an actual working demo URL (industry-matched)
    # For website service: no demo URL — offer is to BUILD them one, not link to existing
    req_key_for_demo = service_target if service_target in SERVICE_REQUIREMENTS else primary_key
    if req_key_for_demo == "chatbot":
        demo_url = get_demo_url(lead.industry)
        demo_block = f"\nDEMO URL — įdėk šią nuorodą laiške kaip CTA nuorodą tekste: {demo_url}"
    else:
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
