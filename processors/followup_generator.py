"""
Follow-up email generator — creates 3 follow-up emails using Claude Haiku.
Called right after the first email is sent so all 3 are ready to auto-send later.
"""
import logging
import os

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu esi AstiScale pardavimų asistentas, rašantis follow-up laiškus lietuvių kalba.

Taisyklės:
- Laiškai LABAI TRUMPI: 50-80 žodžiai
- Kiekvienas follow-up turi SKIRTINGĄ kampą
- Būk žmogiškas ir nuoširdus, ne robotiškas
- Niekada neminėk visų paslaugų — tik vieną
- NIEKADA neišgalvok statistikų, faktų ar klientų pavardžių
- Parašas: Astijus | AstiScale | info@astiscale.com"""


def generate_followups(lead: dict, initial_email_body: str, service_target: str) -> tuple:
    """Generate 3 follow-up emails. Returns (body1, body2, body3)."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    except Exception as e:
        logger.warning(f"Anthropic init failed: {e}")
        return _fallbacks(lead)

    company = lead.get("company_name", "Jūsų įmonė")
    manager = lead.get("manager_name", "")
    city = lead.get("city", "")
    greeting = f"Sveiki, {manager.split()[0]}!" if manager and manager.strip() else "Laba diena!"

    # Build service-specific angle hints
    if service_target == "chatbot":
        angle1 = "Paprastas priminimasas — ar turėjo progą pagalvoti apie pasiūlymą sukurti nemokamą demo? Vienas klausimas, be spaudimo, natūralus tonas."
        angle2 = "Papasakok kaip demo kūrimas atrodo praktiškai: paruoši per 1-2 dienas, jie išbando, jei patinka — kalbame toliau. Kaina: €300 įdiegimas + €149/mėn — paminėk natūraliai, be spaudimo."
        angle3 = "Draugiškas paskutinis laiškas — supranti jei ne laikas, palik duris atviras. Paminėk kad pasiūlymas sukurti nemokamą demo galioja bet kada."
    elif service_target == "svetaine":
        angle1 = "Primink apie nemokamą svetainės auditą/eskizą — vienas klausimas, be spaudimo. Paminėk kad auditas atskleidžia kur jie praranda klientus Google paieškoje."
        angle2 = "Pasiūlyk nemokamą maketo eskizą — per 48 val. paruoštu kaip atrodytų JŲ nauja svetainė. Paminėk kainą natūraliai: nuo €499, sukuriama per 2 savaites. Be įsipareigojimų."
        angle3 = "Draugiškas paskutinis laiškas — supranti jei ne laikas. Palik duris atviras. Paminėk kad nemokamo audito/eskizo pasiūlymas galioja bet kada."
    else:
        angle1 = "Vienas konkretus klausimas apie jų verslą + minkštas kvietimas."
        angle2 = "Pasiūlyk 15 min video demo kaip alternatyvą skambučiui. Paminėk konkretų privalumą jų industrijoje."
        angle3 = "Draugiškas breakup — supranti jei ne laikas, palik duris atviras. Sukurk lengvą FOMO."

    prompts = [
        f"""Parašyk PIRMĄ follow-up laišką (3 dienos po pirmojo).
Įmonė: {company}, {city}. Paslauga: {service_target}.
Kampas: {angle1}
Pradėk: "{greeting}\n\n"
NE: "Ar gavote mano laišką?"
Max 70 žodžių.
""",
        f"""Parašyk ANTRĄ follow-up (7 dienos po pirmojo).
Įmonė: {company}. Paslauga: {service_target}.
Kampas: {angle2}
Pradėk: "{greeting}\n\n"
Max 80 žodžių.
""",
        f"""Parašyk TREČIĄ (paskutinį) follow-up laišką (14 dienų po pirmojo).
Įmonė: {company}.
Kampas: {angle3}
Pradėk: "{greeting}\n\n"
Baik: "Linkiu sėkmės versle! 🙏"
Max 70 žodžių.
""",
    ]

    bodies = []
    for prompt in prompts:
        try:
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=250,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            bodies.append(msg.content[0].text.strip())
        except Exception as e:
            logger.warning(f"Follow-up #{len(bodies)+1} generation failed: {e}")
            bodies.append(_fallbacks(lead)[len(bodies)])

    return tuple(bodies) if len(bodies) == 3 else _fallbacks(lead)


def _fallbacks(lead: dict) -> tuple:
    company = lead.get("company_name", "Jūsų įmonė")
    manager = lead.get("manager_name", "")
    greeting = f"Sveiki, {manager.split()[0]}!" if manager and manager.strip() else "Laba diena!"
    sig = "Pagarbiai,\nAstijus | AstiScale\ninfo@astiscale.com"

    return (
        f"{greeting}\n\nPreš kelias dienas parašiau apie galimybę sustiprinti {company} buvimą internete.\n\nAr turite 10 minučių šią savaitę?\n\n{sig}",
        f"{greeting}\n\nGal patogiau susitikti trumpam video skambučiui? Aš prisitaikau prie jūsų laiko — net 15 min pakanka.\n\n{sig}",
        f"{greeting}\n\nTai mano paskutinis laiškas — nenoriu trukdyti. Jei ateityje atsiras poreikis, žinokite kad esu čia.\n\nLinkiu sėkmės versle! 🙏\nAstijus | AstiScale\ninfo@astiscale.com",
    )
