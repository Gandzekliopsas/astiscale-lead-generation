"""
Service Recommender
Decides which AstiScale services to offer based on the chosen service target
and/or website status + industry.
"""
from config import SERVICES


def recommend(website_status: str, industry: str = "", service_target: str = "") -> list[str]:
    """
    Returns ordered list of service keys to offer.

    service_target (primary):
      "svetaine"       → website creation / modernization
      "meta_ads"       → Facebook/Instagram ads
      "chatbot"        → AI chatbot
      "verslo_valdymas"→ business management system

    website_status (secondary, used when no service_target):
      "none"        → no website at all
      "old"         → website exists but is outdated
      "modern"      → website exists and is relatively modern
      "unreachable" → website URL exists but couldn't be fetched
    """
    # ── Service-target-first logic ─────────────────────────────────────────────
    if service_target == "svetaine":
        if website_status == "none":
            return ["website", "chatbot", "meta_ads"]
        else:  # old or unreachable
            return ["website", "chatbot", "meta_ads"]

    elif service_target == "meta_ads":
        if website_status in ("old", "unreachable"):
            return ["website", "meta_ads", "chatbot"]
        else:  # modern
            return ["meta_ads", "chatbot"]

    elif service_target == "chatbot":
        if website_status in ("old", "unreachable"):
            return ["chatbot", "website", "meta_ads"]
        else:  # modern
            return ["chatbot", "meta_ads"]

    elif service_target == "verslo_valdymas":
        return ["verslo_valdymas", "chatbot"]

    # ── Fallback: website-status-only logic (no service_target chosen) ─────────
    if website_status == "none":
        return ["website", "chatbot", "meta_ads"]
    elif website_status in ("old", "unreachable"):
        return ["website", "chatbot", "meta_ads", "verslo_valdymas"]
    else:  # modern
        return ["chatbot", "meta_ads", "verslo_valdymas"]


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
    service_target = getattr(lead, "service_target", "")

    if service_target == "verslo_valdymas":
        problem = (
            f"specializuojamės verslo valdymo sistemų diegime transporto ir logistikos įmonėms — "
            f"maršrutų planavimas, dokumentų valdymas, darbo laiko apskaita."
        )
        offer = "galėtume aptarti, kokios sistemos geriausiai tiktų jūsų įmonei — tai padeda sutaupyti laiko ir sumažinti klaidas."
    elif ws == "none":
        problem = (
            f"pastebėjau, kad {lead.company_name} neturi svetainės internete. "
            "Šiandien be svetainės labai sunku pritraukti naujus klientus."
        )
        offer = "galėtume sukurti modernią svetainę su integruotu AI pokalbių robotu — klientai galėtų rasti informaciją ir gauti atsakymus bet kuriuo metu."
    elif ws in ("old", "unreachable"):
        problem = (
            f"apsilankiau {lead.company_name} svetainėje ir pastebėjau, kad ji galėtų būti atnaujinta. "
            "Pasenusios svetainės blogai rodo Google paieškoje ir atbaido lankytojus."
        )
        offer = "galėtume atnaujinti svetainę ir pridėti AI chatbotą, kuris atsakytų į klientų klausimus 24/7."
    else:
        problem = (
            f"žiūrėjau {lead.company_name} svetainę — ji atrodo gerai. "
            "Norėčiau paklauti — ar šiuo metu naudojate Facebook/Instagram reklamas?"
        )
        offer = "galėtume padėti su tikslinėmis Meta reklamomis ir AI chatbotu, kuris konvertuotų lankytojus į klientus."

    script = f"""📞 SKAMBUČIO SCENARIJUS — {lead.company_name}
{'─'*55}
{greeting}

Skambinu iš AstiScale — tai AI ir skaitmeninės rinkodaros agentūra.

{problem}

Mūsų siūlomas sprendimas — {offer}

Tai nekainuoja nieko pasikalbėti — ar turėtumėte 10 minučių savaitę susitikti virtualiai?

Jei susidomėjote — siųsiu jums išsamesnę informaciją el. paštu: {lead.email or '[el. paštas]'}
{'─'*55}
Siūlomos paslaugos: {build_service_summary(services)}
"""
    return script
