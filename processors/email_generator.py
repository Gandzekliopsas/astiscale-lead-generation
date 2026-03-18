"""
Email Generator — Claude-powered hyper-personalized cold emails in Lithuanian.
Each email is unique, references the specific business, and offers the right services.
"""
import logging
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, AGENCY_NAME, AGENCY_EMAIL, AGENCY_WEBSITE,
    AGENT_NAME, SERVICES, SERVICE_TARGETS
)

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── System prompt (stays cached) ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""Tu esi {AGENCY_NAME} — Lietuvos skaitmeninės rinkodaros agentūros pardavimų ekspertas.

Tavo tikslas — rašyti LABAI ASMENINIUS šaltus el. laiškus lietuvių verslininkams.

TAISYKLĖS:
1. Laiškas VISADA rašomas lietuvių kalba
2. Kreipiamasi VARDU (jei žinomas) — draugiškai, bet profesionaliai. Jei vardas nežinomas, rašyk "Laba diena!"
3. Laiške VISADA minima konkreti įmonė ir jos industrija
4. ⚠️ SIŪLYK TIK VIENĄ PASLAUGĄ — tą, kuri nurodyta SIŪLOMA PASLAUGA laukelyje. NE daugiau. NE kitas paslaugas.
5. Problema — konkretus skausmas susijęs TIK su ta viena paslauga
6. Sprendimas — trumpai ir aiškiai, be techninio žargono
7. CTA — VIENAS aiškus kvietimas (15 min. skambutis arba demo)
8. Ilgis: 120–200 žodžių. NE ILGIAU.
9. Tonas: šiltas, paprastas, žmogiškas — NE korporatyvinis
10. Jokių buzzwords kaip "sinergija", "holistinis", "inovatyvus"

⚠️ DRAUDŽIAMA:
- Minėti kitas paslaugas (chatbot, meta ads, svetainę, valdymo sistemas) — TIKTAI siūloma paslauga
- Išgalvoti konkurentų pavadinimus, statistikas ar skaičius
- Rašyti detalių apie įmonę, kurių negavai iš pateiktų duomenų

KONTAKTAI: {AGENT_NAME} | {AGENCY_NAME} | {AGENCY_EMAIL} | {AGENCY_WEBSITE}

Grąžink TIK laišką — be jokių paaiškinimų ar metaduomenų.
"""


def generate_email(lead, service_keys: list[str], service_target: str = "") -> str:
    """
    Generate a personalized cold email for a BusinessLead.
    Returns the email as a plain string (with subject line at the top).

    service_target: one of "svetaine", "meta_ads", "chatbot", "verslo_valdymas"
    """
    vadovas_first = lead.vadovas.split()[0] if lead.vadovas else ""

    # When a service_target is selected, email is about THAT ONE service only.
    # Use only the first (primary) service key regardless of what recommend() returned.
    valid_keys = [k for k in service_keys if k in SERVICES]
    if service_target and valid_keys:
        primary_key = valid_keys[0]
        services_text = f"{SERVICES[primary_key]['name']}: {SERVICES[primary_key]['pitch_lt']}"
    else:
        services_text = "\n".join(
            f"- {SERVICES[k]['name']}: {SERVICES[k]['pitch_lt']}"
            for k in valid_keys
        )

    # Build situation based on website status
    if lead.website_status == "none":
        situation = f"{lead.company_name} šiuo metu neturi svetainės internete."
        pain = "Potencialūs klientai ieško paslaugų internete — jei ten jūsų nėra, jie randa konkurentus."
    elif lead.website_status == "old":
        year_note = f" (paskutinį kartą atnaujinta apie {lead.website_year} m.)" if lead.website_year else ""
        situation = f"{lead.company_name} svetainė yra pasenusi{year_note}."
        pain = "Pasenusios svetainės blogai rodo Google paieškoje ir nėra pritaikytos išmaniesiems telefonams."
    elif lead.website_status == "unreachable":
        situation = f"{lead.company_name} svetainė šiuo metu sunkiai pasiekiama arba lėtai kraunasi."
        pain = "Lėta arba neveikianti svetainė atbaido lankytojus ir kenkia Google reitingui."
    else:
        situation = f"{lead.company_name} turi veikiančią svetainę."
        pain = "Svetainė jau veikia, bet galima padidinti konversiją su automatiniu klientų aptarnavimu ir tiksline reklama."

    # Service-specific context
    service_context = ""
    if service_target and service_target in SERVICE_TARGETS:
        tgt = SERVICE_TARGETS[service_target]
        service_context = f"PAGRINDINIS TIKSLAS: {tgt['label']} — {tgt['description']}"

    user_prompt = f"""Parašyk personalizuotą šaltą el. laišką šiam potencialiam klientui:

ĮMONĖ: {lead.company_name}
KREIPINYS: {vadovas_first or 'Laba diena!'}
MIESTAS: {lead.city.capitalize() if lead.city else 'Lietuva'}
INDUSTRIJA: {lead.industry}
SITUACIJA: {situation}
SKAUSMO TAŠKAS: {pain}
SIŪLOMA PASLAUGA (TIKTAI ŠI — NERAŠYK KITŲ): {services_text}

Formato reikalavimai:
Tema: [konkreti tema, iki 60 simbolių]

[Laiškas — TIKTAI apie vieną siūlomą paslaugą]

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

    if lead.website_status == "none":
        body = (
            f"pastebėjau, kad {lead.company_name} dar neturi svetainės internete. "
            "Šiomis dienomis tai gali reikšti daug prarastų klientų."
        )
    elif lead.website_status in ("old", "unreachable"):
        body = (
            f"apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji galėtų būti atnaujinta. "
            "Šiuolaikinė svetainė padeda pritraukti daugiau klientų ir geriau rodo Google paieškoje."
        )
    else:
        body = (
            f"žiūrėjau {lead.company_name} veiklą internete ir manau, kad galėtumėte gauti "
            "daugiau klientų su tinkamomis skaitmeninėmis priemonėmis."
        )

    greeting = f"Laba diena{', ' + vadovas_first if vadovas_first else ''}!"

    return f"""Tema: {lead.company_name} — skaitmeninės galimybės

{greeting}

Skambinu iš {AGENCY_NAME} — AI ir skaitmeninės rinkodaros agentūros.

{body}

Mes siūlome: {services_lt}.

Ar turėtumėte 15 minučių trumpam pokalbiui šią savaitę? Mielai parodysiu, kaip tai veikia kitoms Lietuvos įmonėms.

Pagarbiai,
{AGENT_NAME}
{AGENCY_NAME}
{AGENCY_EMAIL}
{AGENCY_WEBSITE}"""
