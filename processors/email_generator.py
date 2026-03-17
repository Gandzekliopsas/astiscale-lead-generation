"""
Email Generator — Claude-powered hyper-personalized cold emails in Lithuanian.
Each email is unique, references the specific business, and offers the right services.
"""
import logging
from anthropic import Anthropic
from config import (
    ANTHROPIC_API_KEY, AGENCY_NAME, AGENCY_EMAIL, AGENCY_WEBSITE,
    AGENT_NAME, SERVICES
)

logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ── System prompt (stays cached) ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""Tu esi {AGENCY_NAME} — Lietuvos AI ir skaitmeninės rinkodaros agentūros pardavimų ekspertas.

Tavo tikslas — rašyti LABAI ASMENINIUS šaltus el. laiškus lietuvių verslininkams.

TAISYKLĖS:
1. Laiškas VISADA rašomas lietuvių kalba
2. Kreipiamasi VARDU (jei žinomas) — draugiškai, bet profesionaliai
3. Laiške VISADA minima konkreti įmonė — parodyk, kad tikrai žiūrėjai jų situaciją
4. Problema — konkretus jų situacijos skausmas (nėra svetainės / sena svetainė / nėra automatizacijos)
5. Sprendimas — trumpai ir aiškiai, be techninio žargono
6. Socialinis įrodymas — mini, kad jau padedame kitoms Lietuvos įmonėms
7. CTA — VIENAS aiškus kvietimas (15 min. skambutis arba demo)
8. Ilgis: 150–250 žodžių. NE ILGIAU.
9. Tonas: šiltas, paprastas, žmogiškas — NE korporatyvinis
10. Jokių buzzwords kaip "sinergija", "holistinis", "inovatyvus"

APIE {AGENCY_NAME}:
- Kuriame AI pokalbių robotus svetainėms (veikia 24/7, lietuvių kalba)
- Tvarkome Facebook/Instagram reklamas (Meta Ads) — mokame tik už rezultatus
- Automatizuojame verslo procesus su AI (rezervacijos, el. laiškai, ataskaitos)
- Kuriame ir modernizuojame svetaines
- Klientai: grožio salonai, restoranai, odontologai, NT agentūros, sporto klubai ir kt.
- El. paštas: {AGENCY_EMAIL}
- Svetainė: {AGENCY_WEBSITE}
- Kontaktinis asmuo: {AGENT_NAME}

Grąžink TIK laišką — be jokių paaiškinimų, antraščių ar metaduomenų.
"""


def generate_email(lead, service_keys: list[str]) -> str:
    """
    Generate a personalized cold email for a BusinessLead.
    Returns the email as a plain string (with subject line at the top).
    """
    # Build context for Claude
    vadovas_first = lead.vadovas.split()[0] if lead.vadovas else ""

    services_text = "\n".join(
        f"- {SERVICES[k]['name']}: {SERVICES[k]['pitch_lt']}"
        for k in service_keys if k in SERVICES
    )

    if lead.website_status == "none":
        situation = f"{lead.company_name} visiškai neturi svetainės internete."
        pain = "Klientai negali rasti informacijos internete, o konkurentai, turintys svetaines, pritraukia tuos klientus, kurie galėtų ateiti pas jus."
    elif lead.website_status == "old":
        year_note = f" (paskutinį kartą atnaujinta apie {lead.website_year} m.)" if lead.website_year else ""
        situation = f"{lead.company_name} svetainė yra pasenusi{year_note}."
        pain = "Senos svetainės nekelia pasitikėjimo, blogai rodo Google paieškoje ir nėra pritaikytos mobiliesiems."
    else:
        situation = f"{lead.company_name} turi veikiančią svetainę."
        pain = "Bet svetainė tikriausiai nerenka klientų kontaktų automatiškai ir neatsakinėja į klausimus ne darbo valandomis."

    user_prompt = f"""Parašyk personalizuotą šaltą el. laišką šiam potencialiam klientui:

ĮMONĖ: {lead.company_name}
VADOVAS / KREIPINYS: {vadovas_first or 'Gerbiamas Vadove'}
MIESTAS: {lead.city or 'Lietuva'}
INDUSTRIJA: {lead.industry}
SITUACIJA: {situation}
SKAUSMO TAŠKAS: {pain}
SIŪLOMOS PASLAUGOS:
{services_text}

Formato pavyzdys:
Tema: [temos eilutė — intriguojanti, konkreti, iki 60 simbolių]

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
        return _fallback_email(lead, service_keys, vadovas_first)


def _fallback_email(lead, service_keys: list[str], vadovas_first: str) -> str:
    """Static fallback template if Claude API fails."""
    services_lt = " + ".join(SERVICES[k]["lt"] for k in service_keys if k in SERVICES)

    if lead.website_status == "none":
        body = (
            f"pastebėjau, kad {lead.company_name} dar neturi svetainės internete. "
            "Šiomis dienomis tai gali reikšti daug prarastų klientų."
        )
    elif lead.website_status == "old":
        body = (
            f"apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji atrodo šiek tiek pasenusi. "
            "Senos svetainės dažnai atbaido potencialius klientus."
        )
    else:
        body = (
            f"žiūrėjau {lead.company_name} veiklą internete ir manau, kad galėtumėte gauti "
            "žymiai daugiau klientų su tinkamomis skaitmeninėmis priemonėmis."
        )

    return f"""Tema: {lead.company_name} — galimybė pritraukti daugiau klientų

Laba diena{', ' + vadovas_first if vadovas_first else ''}!

Skambinu iš {AGENCY_NAME} — AI ir skaitmeninės rinkodaros agentūros.

{body}

Mes siūlome: {services_lt}.

Ar turėtumėte 15 minučių trumpam pokalbiui šią savaitę? Mielai parodysiu, kaip tai veikia kitoms Lietuvos įmonėms.

Pagarbiai,
{AGENT_NAME}
{AGENCY_NAME}
{AGENCY_EMAIL}
{AGENCY_WEBSITE}"""
