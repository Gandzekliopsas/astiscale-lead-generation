"""
Service Recommender
Decides which AstiScale services to offer based on website status and industry.
"""
from config import SERVICES


def recommend(website_status: str, industry: str = "") -> list[str]:
    """
    Returns ordered list of service keys to offer.

    website_status:
      "none"   → no website at all
      "old"    → website exists but is outdated
      "modern" → website exists and is relatively modern
    """
    industry_lower = industry.lower()

    if website_status == "none":
        # No website → build one + chatbot. Meta ads can follow once they have a site.
        return ["website", "chatbot", "meta_ads"]

    elif website_status == "old":
        # Old website → modernize it, add chatbot, run ads
        return ["website", "chatbot", "meta_ads", "ai_automation"]

    else:  # modern
        # Good website → focus on chatbot + ads + automation
        return ["chatbot", "meta_ads", "ai_automation"]


def build_service_summary(service_keys: list[str]) -> str:
    """Human-readable service list for the lead sheet."""
    names = [SERVICES[k]["name"] for k in service_keys if k in SERVICES]
    return " + ".join(names)


def build_pitch_summary(service_keys: list[str], industry: str = "") -> str:
    """Short pitch in Lithuanian, used in cold call prep."""
    pitches = [SERVICES[k]["pitch_lt"] for k in service_keys if k in SERVICES]
    return "; ".join(pitches)


def cold_call_script(lead) -> str:
    """
    Returns a short Lithuanian cold-call opening script.
    lead: BusinessLead object
    """
    vadovas = lead.vadovas.split()[0] if lead.vadovas else ""
    greeting = f"Laba diena, ar galiu kalbėti su {vadovas}?" if vadovas else "Laba diena!"

    services = lead.recommended_services
    ws = lead.website_status

    if ws == "none":
        problem = (
            f"pastebėjau, kad {lead.company_name} neturi svetainės internete. "
            "Šiandien be svetainės labai sunku pritraukti naujus klientus."
        )
        offer = "galėtume sukurti jums modernią svetainę su integruotu AI pokalbių robotu — klientai galėtų gauti atsakymus bet kuriuo paros metu."
    elif ws == "old":
        problem = (
            f"apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji atrodo šiek tiek pasenusi. "
            "Senos svetainės atbaido klientus ir blogai rodo Google paieškoje."
        )
        offer = "galėtume atnaujinti svetainę ir pridėti AI chatbotą, kuris atsakytų į klientų klausimus 24/7 — be papildomų darbuotojų."
    else:
        problem = (
            f"žiūrėjau {lead.company_name} svetainę — ji atrodo gerai. "
            "Klausimas — ar dabar aktyviai naudojate Facebook/Instagram reklamas ir ar turite automatizuotą klientų aptarnavimą?"
        )
        offer = "galėtume padėti su Meta reklamomis, kurios atneštų daugiau klientų, ir su AI chatbotu, kuris atsakytų į klausimus automatiškai."

    script = f"""📞 SKAMBUČIO SCENARIJUS — {lead.company_name}
{'─'*55}
Labas rytas/diena! Skambinu iš AstiScale — tai AI ir skaitmeninės rinkodaros agentūra.

{greeting}

Skambinu, nes {problem}

Mūsų siūlomas sprendimas — {offer}

Tai nekainuoja nieko pasikalbėti — ar turėtumėte 10 minučių savaitę sutikti virtualiai?

Jei susidomėjote — siųsiu jums išsamesnę informaciją el. paštu: {lead.email or '[el. paštas]'}
{'─'*55}
Siūlomos paslaugos: {build_service_summary(services)}
"""
    return script
