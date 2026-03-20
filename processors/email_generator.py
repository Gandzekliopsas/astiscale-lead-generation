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
5. Rašyk TIK apie VIENĄ paslaugą. NIEKADA neminėk kitų paslaugų ar paketų viename laiške.
6. Problema — konkretus skausmas susijęs TIK su ta viena paslauga
7. Sprendimas — trumpai ir aiškiai, be techninio žargono
8. CTA — VIENAS aiškus kvietimas: 15 minučių pokalbis telefonu
9. Ilgis: 120–200 žodžių. NE ILGIAU.
10. Tonas: šiltas, paprastas, žmogiškas — NE korporatyvinis
11. Jokių buzzwords kaip "sinergija", "holistinis", "inovatyvus"

⚠️ DRAUDŽIAMA:
- Minėti kitas paslaugas (chatbot, meta ads, svetainę, valdymo sistemas) — TIKTAI siūloma paslauga
- Siūlyti paketus, kompleksus ar kelias paslaugas viename laiške
- Išgalvoti konkurentų pavadinimus, statistikas ar skaičius
- Rašyti detalių apie įmonę, kurių negavai iš pateiktų duomenų

STRUKTŪRA: viena problema → vienas sprendimas (tik pasirinkta paslauga) → vienas CTA (15 min. skambutis)

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

    # Always use ONLY the first (primary) service key — one email, one service.
    valid_keys = [k for k in service_keys if k in SERVICES]
    primary_key = valid_keys[0] if valid_keys else None
    if primary_key:
        svc = SERVICES[primary_key]
        services_text = f"{svc['lt']}: {svc['pitch_lt']}"
    else:
        services_text = "skaitmeninės rinkodaros paslauga"

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

    # Chatbot-specific hooks: social proof + angle guidance
    chatbot_guidance = ""
    if service_target == "chatbot":
        chatbot_guidance = """
CHATBOT KAMPAS — NAUDOK ŠIUOS KABLIUKUS:
- Pabrėžk: daugelis klientų rašo vakarais/savaitgaliais kai verslas neveikia — chatbot atsako iš karto
- Konkretus ROI: vidutiniškai 60-80% dažniausių klausimų automatizuojama
- Kaina: €300 vienkartinis įdiegimas + €50/mėn — pigiau nei vienas darbuotojo valanda per savaitę
- Tikslingas skausmo taškas pagal industriją:
  * Odontologas/klinika → rezervacijos klausimas, darbo laiko, kainų klausimai naktį
  * Restoranas/kavinė → stalo rezervacijos, meniu, darbo laikas
  * Viešbutis → kambario kainos, laisvos datos, papildomos paslaugos
  * Advokatai → pirminis klientų atrankos pokalbis, konsultacijos laiko klausimas
  * NT agentūra → objektų klausimai, apžiūros organizavimas
TEMOS PAVYZDŽIAI (naudok panašų stilių):
- "Klientai rašo po 18:00 — kas jiems atsako?"
- "Klausimas apie {lead.company_name} klientų aptarnavimą"
- "Idėja: {lead.industry} chatbot, kuris veikia 24/7"
- "{lead.company_name}: automatinis asistentas klientams"
"""

    user_prompt = f"""Parašyk personalizuotą šaltą el. laišką šiam potencialiam klientui:

ĮMONĖ: {lead.company_name}
KREIPINYS: {vadovas_first or 'Laba diena!'}
MIESTAS: {lead.city.capitalize() if lead.city else 'Lietuva'}
INDUSTRIJA: {lead.industry}
SITUACIJA: {situation}
SKAUSMO TAŠKAS: {pain}
SIŪLOMA PASLAUGA (TIKTAI ŠI — NERAŠYK KITŲ): {services_text}
{chatbot_guidance}
Formato reikalavimai:
Tema: [konkreti, intriguojanti tema iki 55 simbolių — klausimas arba konkretus skausmo taškas]

[Laiškas — TIKTAI apie vieną siūlomą paslaugą, 120-180 žodžių]

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
