"""
Email Generator — Hybrid model: fixed template per service + Claude-personalized subject & hook.
Claude generates ONLY 2 things per email:
  1. Subject line (≤55 chars)
  2. Opening hook (2-3 sentences specific to the company/city/industry)
Everything else is hand-crafted fixed copy assembled in Python.
"""
import json
import logging
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, AGENCY_NAME, AGENCY_EMAIL, AGENCY_WEBSITE,
    AGENT_NAME, SERVICES, SERVICE_TARGETS
)

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Fixed benefit + CTA blocks per service (hand-crafted, never changes) ──────
EMAIL_TEMPLATES = {
    "chatbot": {
        "benefit": (
            "Daugelis klientų rašo klausimus vakare ar savaitgaliais — kai verslas jau nedirba. "
            "AI asistentas jūsų svetainėje atsakytų jiems iš karto, 24/7, be papildomų darbuotojų. "
            "Įdiegimas: €300 vienkartinai + €50/mėn."
        ),
        "cta": (
            "Ar turėtumėte 15 minučių šią savaitę trumpam skambučiui? "
            "Mielai parodysiu kaip tai veikia su realia demo."
        ),
    },
    "website": {
        "benefit": (
            "Moderni svetainė padidina pasitikėjimą ir leidžia rasti jus Google paieškoje. "
            "Sukuriame per 2 savaites — su mobiliuoju pritaikymu, SEO ir kontaktų forma. "
            "Kaina nuo €499."
        ),
        "cta": "Ar turėtumėte 15 minučių šią savaitę trumpam pokalbiui?",
    },
    "meta_ads": {
        "benefit": (
            "Facebook ir Instagram reklama pasiekia žmones jūsų mieste, kurie jau ieško "
            "tokių paslaugų kaip jūsiškės — ir moka už jas. "
            "Valdymas nuo €299/mėn."
        ),
        "cta": "Ar turėtumėte 15 minučių šią savaitę pasikalbėti?",
    },
    "verslo_valdymas": {
        "benefit": (
            "Automatizuojame maršrutus, dokumentus ir darbo laiko apskaitą — "
            "kad nebereikėtų to daryti rankiniu būdu. "
            "Sistema pritaikoma jūsų esamiems procesams. Nuo €299/mėn."
        ),
        "cta": "Ar turėtumėte 15 minučių šią savaitę trumpam pokalbiui?",
    },
    # Fallback for unknown service keys
    "_default": {
        "benefit": "Padedame Lietuvos verslo įmonėms augti naudojant skaitmenines priemones.",
        "cta": "Ar turėtumėte 15 minučių šią savaitę trumpam pokalbiui?",
    },
}

# ── System prompt (stays cached by Anthropic prompt caching) ──────────────────
SYSTEM_PROMPT = """Tu esi patyrės pardavimų tekstų rašytojas, rašantis šaltus el. laiškus \
lietuvių verslininkams.

Tavo užduotis: sugeneruoti TIK 2 personalizuotus elementus šaltam el. laiškui.
Grąžink TIKTAI galiojantį JSON objektą be jokio kito teksto:
{"subject": "...", "hook": "..."}

TAISYKLĖS:
- subject: iki 55 simbolių, lietuvių kalba, intriguojantis klausimas arba konkretus skausmo taškas
- hook: 2-3 sakiniai, LABAI specifiškai apie pateiktą įmonę — minėk jų pavadinimą, miestą, industriją arba svetainės situaciją
- Tonas: draugiškas, žmogiškas, kaip kalbėtų žmogus žmogui — ne reklama, ne korporatyvinė kalba
- NE: jokių statistikų, jokių išgalvotų faktų apie jų įmonę
- NE: jokio sprendimo ar paslaugos paminėjimo hook dalyje — tik stebėjimas apie jų situaciją
- subject ir hook VISADA lietuvių kalba"""


def generate_email(lead, service_keys: list[str], service_target: str = "") -> str:
    """
    Generate a personalized cold email for a BusinessLead.
    Returns the email as a plain string (Tema: on first line, then body).

    Hybrid approach:
    - Claude generates: subject line + personalized hook (JSON)
    - Python assembles: greeting + hook + fixed benefit block + CTA + signature
    """
    vadovas_first = lead.vadovas.split()[0] if lead.vadovas else ""
    greeting = f"Laba diena{', ' + vadovas_first if vadovas_first else ''}!"

    # Pick service template
    valid_keys = [k for k in service_keys if k in SERVICES]
    primary_key = valid_keys[0] if valid_keys else None

    # Map service_target → template key
    template_key = service_target if service_target in EMAIL_TEMPLATES else (
        primary_key if primary_key in EMAIL_TEMPLATES else "_default"
    )
    tmpl = EMAIL_TEMPLATES[template_key]

    # Build situation context for Claude
    if lead.website_status == "none":
        situation = f"{lead.company_name} šiuo metu neturi svetainės internete"
    elif lead.website_status == "old":
        year_note = f" (apie {lead.website_year} m.)" if lead.website_year else ""
        situation = f"{lead.company_name} svetainė pasenusi{year_note}"
    elif lead.website_status == "unreachable":
        situation = f"{lead.company_name} svetainė sunkiai pasiekiama arba lėtai kraunasi"
    else:
        situation = f"{lead.company_name} turi veikiančią svetainę"

    user_prompt = f"""Sugeneruok 2 personalizuotus elementus šaltam el. laiškui.

ĮMONĖ: {lead.company_name}
MIESTAS: {lead.city.capitalize() if lead.city else 'Lietuva'}
INDUSTRIJA: {lead.industry}
SITUACIJA: {situation}
KREIPINYS: {vadovas_first or '(nežinomas)'}

Grąžink TIKTAI JSON:
{{"subject": "...", "hook": "..."}}"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()

        # Parse JSON — strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        subject = data.get("subject", "").strip()
        hook = data.get("hook", "").strip()

        if not subject or not hook:
            raise ValueError("Empty subject or hook from Claude")

        return _assemble_email(subject, greeting, hook, tmpl)

    except Exception as e:
        logger.error(f"Email generation failed for {lead.company_name}: {e}")
        return _fallback_email(lead, primary_key, vadovas_first, tmpl, situation)


def _assemble_email(subject: str, greeting: str, hook: str, tmpl: dict) -> str:
    """Assemble the full email from parts."""
    return (
        f"Tema: {subject}\n\n"
        f"{greeting}\n\n"
        f"{hook}\n\n"
        f"{tmpl['benefit']}\n\n"
        f"{tmpl['cta']}\n\n"
        f"Pagarbiai,\n"
        f"{AGENT_NAME}\n"
        f"{AGENCY_NAME}\n"
        f"{AGENCY_EMAIL}\n"
        f"{AGENCY_WEBSITE}"
    )


def _fallback_email(lead, primary_key, vadovas_first: str, tmpl: dict, situation: str) -> str:
    """Static fallback — same template structure, static hook based on situation."""
    greeting = f"Laba diena{', ' + vadovas_first if vadovas_first else ''}!"

    # Static hook from website status
    if lead.website_status == "none":
        hook = (
            f"Pastebėjau, kad {lead.company_name} šiuo metu neturi svetainės internete. "
            f"Šiomis dienomis potencialūs klientai {lead.city or 'Lietuvoje'} pirmiausia ieško paslaugų Google — "
            "ir jei ten jūsų nėra, jie randa konkurentus."
        )
    elif lead.website_status in ("old", "unreachable"):
        hook = (
            f"Apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji galėtų būti atnaujinta. "
            f"Šiuolaikiniai klientai {lead.city or 'Lietuvoje'} sprendžia greičiau — "
            "pasenusi svetainė dažnai atbaido dar prieš pirmą skambutį."
        )
    else:
        hook = (
            f"Žiūrėjau {lead.company_name} veiklą internete ir manau, kad yra keletas dalykų, "
            f"kurie galėtų padėti pritraukti daugiau klientų {lead.city or 'jūsų mieste'}."
        )

    subject = f"{lead.company_name} — klausimas"
    return _assemble_email(subject, greeting, hook, tmpl)
