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
SYSTEM_PROMPT = f"""Tu esi {AGENCY_NAME} — Lietuvos AI ir skaitmeninės rinkodaros agentūros pardavimų ekspertas.

Tavo tikslas — rašyti LABAI ASMENINIUS šaltus el. laiškus lietuvių verslininkams.

TAISYKLĖS:
1. Laiškas VISADA rašomas lietuvių kalba
2. Kreipiamasi VARDU (jei žinomas) — draugiškai, bet profesionaliai. Jei vardas nežinomas, rašyk "Laba diena!"
3. Laiške VISADA minima konkreti įmonė ir jos industrija — parodyk, kad tikrai žiūrėjai jų situaciją
4. Problema — konkretus jų situacijos skausmas (nėra svetainės / sena svetainė / nėra automatizacijos)
5. Sprendimas — trumpai ir aiškiai, be techninio žargono
6. Socialinis įrodymas — mini, kad jau padedame kitoms Lietuvos įmonėms tos pačios srities
7. CTA — VIENAS aiškus kvietimas (15 min. skambutis arba demo)
8. Ilgis: 150–250 žodžių. NE ILGIAU.
9. Tonas: šiltas, paprastas, žmogiškas — NE korporatyvinis
10. Jokių buzzwords kaip "sinergija", "holistinis", "inovatyvus"

⚠️ DRAUDŽIAMA IŠGALVOTI informaciją:
- Jokių konkurentų pavadinimų (nežinai jų)
- Jokių skaičių ar statistikų (nebent pateikta duomenyse)
- Jokių detalių apie įmonę, kurių negavai iš pateiktų duomenų
- Rašyk TIK tai, kas tikrai žinoma apie šią konkretią įmonę

APIE {AGENCY_NAME}:
- Kuriame AI pokalbių robotus svetainėms (veikia 24/7, lietuvių kalba)
- Tvarkome Facebook/Instagram reklamas (Meta Ads)
- Kuriame ir modernizuojame svetaines bei el. parduotuves
- Diegiame verslo valdymo sistemas transporto ir logistikos įmonėms
- Klientai: grožio salonai, restoranai, odontologai, NT agentūros, sporto klubai ir kt.
- El. paštas: {AGENCY_EMAIL}
- Svetainė: {AGENCY_WEBSITE}
- Kontaktinis asmuo: {AGENT_NAME}

Grąžink TIK laišką — be jokių paaiškinimų, antraščių ar metaduomenų.
"""


def generate_email(lead, service_keys: list[str], service_target: str = "") -> str:
    """
    Generate a personalized cold email for a BusinessLead.
    Returns the email as a plain string (with subject line at the top).

    service_target: one of "svetaine", "meta_ads", "chatbot", "verslo_valdymas"
    """
    vadovas_first = lead.vadovas.split()[0] if lead.vadovas else ""

    # Only include services that exist in SERVICES dict
    valid_keys = [k for k in service_keys if k in SERVICES]
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
VADOVAS / KREIPINYS: {vadovas_first or 'Laba diena!'}
MIESTAS: {lead.city.capitalize() if lead.city else 'Lietuva'}
INDUSTRIJA: {lead.industry}
SITUACIJA: {situation}
SKAUSMO TAŠKAS: {pain}
{service_context}
SIŪLOMOS PASLAUGOS:
{services_text}

Formato pavyzdys:
Tema: [temos eilutė — konkreti, iki 60 simbolių, be klaustukas ar šauktukų]

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
