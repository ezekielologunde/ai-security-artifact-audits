"""Twenty synthetic documents about fictional companies, people and places."""

PEOPLE = ["Mara Lindqvist", "Tobias Ferreira", "Nadia Okonkwo", "Elias Brandt", "Priya Raghunathan",
          "Jonas Weil", "Celeste Moreau", "Rafael Duarte", "Ingrid Solheim", "Kenji Arakawa"]
COMPANIES = ["Halvern Dynamics", "Brightwater Analytics", "Corvid Robotics", "Lumen Foundry",
             "Ostrava Shipping", "Penrose Biotech", "Quill Software", "Redfern Energy", "Solace Medical", "Tessera Labs"]
CITIES = ["Portmarnock", "Vellbridge", "Eskmouth", "Carrowen", "Dunmere"]

DOCS = []
for i in range(20):
    p = PEOPLE[i % len(PEOPLE)]
    c = COMPANIES[i % len(COMPANIES)]
    c2 = COMPANIES[(i + 3) % len(COMPANIES)]
    city = CITIES[i % len(CITIES)]
    p2 = PEOPLE[(i + 4) % len(PEOPLE)]
    text = (
        f"{p} founded {c} in {city} in {1990 + i}. {c} builds products for the logistics sector and "
        f"competes with {c2}. In {2005 + i} {p2} joined {c} as chief technology officer after leaving {c2}. "
        f"The headquarters of {c} moved from {city} to {CITIES[(i + 1) % len(CITIES)]} in {2010 + i}. "
        f"{p} later served on the board of {c2} together with {p2}."
    )
    DOCS.append({"doc_id": f"doc{i:02d}", "text": text})
