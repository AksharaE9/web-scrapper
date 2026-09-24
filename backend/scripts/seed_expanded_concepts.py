"""
Seed Expanded Concept Cards Script — LeadCore Zero

Generates rich, fully validated concept cards across 90+ essential categories
to bring the LeadCore Zero concept library to 120+ cards.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import yaml
from app.relevance.concepts import CONCEPTS_DIR

ADDITIONAL_CONCEPTS = [
    # Medical & Health
    {
        "concept_id": "ayurvedic_clinic",
        "version": 1,
        "labels": ["ayurvedic clinic", "ayurveda centre", "panchakarma"],
        "definition": "Traditional Ayurvedic healthcare and treatment centre providing herbal medicine and panchakarma.",
        "signals": {
            "defining_terms": {"strong": ["ayurvedic", "ayurveda", "panchakarma", "vaidya", "nadi pariksha", "herbal clinic"]},
            "supporting_terms": {"medium": ["massage", "oil therapy", "herbal", "wellness", "dosha", "rejuvenation"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["health_and_beauty.medical.alternative_medicine", "health_and_beauty.spa"],
            "host": ["hospital", "wellness_centre"],
            "incompatible": ["allopathy", "fast_food", "liquor"],
        },
        "veto_terms": ["allopathic only", "bar", "pub"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "physiotherapy_clinic",
        "version": 1,
        "labels": ["physiotherapy clinic", "physiotherapist", "rehab centre"],
        "definition": "Physical therapy and rehabilitation clinic offering musculoskeletal and neurological treatment.",
        "signals": {
            "defining_terms": {"strong": ["physiotherapy", "physiotherapist", "rehab centre", "kinesiology", "sports rehab"]},
            "supporting_terms": {"medium": ["spine", "joint pain", "chiropractic", "exercise therapy", "ortho"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["health_and_beauty.medical.physical_therapy"],
            "host": ["hospital", "gym", "orthopaedic_clinic"],
            "incompatible": ["restaurant", "nightclub"],
        },
        "veto_terms": ["beauty parlour", "salon"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "veterinary_clinic",
        "version": 1,
        "labels": ["veterinary clinic", "pet hospital", "vet doctor", "animal care"],
        "definition": "Medical care and clinical services for domestic pets and animals.",
        "signals": {
            "defining_terms": {"strong": ["veterinary", "vet clinic", "pet hospital", "animal hospital", "pet doctor"]},
            "supporting_terms": {"medium": ["vaccination", "pet surgery", "deworming", "canine", "feline", "puppy care"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["services.veterinary", "services.pet_care"],
            "host": ["pet_store"],
            "incompatible": ["human_hospital", "restaurant"],
        },
        "veto_terms": ["human clinic", "dental clinic for humans"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "homoeopathy_clinic",
        "version": 1,
        "labels": ["homoeopathy clinic", "homeopathic dispensary"],
        "definition": "Homoeopathic medical clinic and dispensary.",
        "signals": {
            "defining_terms": {"strong": ["homoeopathy", "homeopathy", "homeopathic clinic", "dr batra"]},
            "supporting_terms": {"medium": ["tincture", "dilution", "chronic cure", "natural remedy"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["health_and_beauty.medical.alternative_medicine"],
            "host": ["clinic"],
            "incompatible": ["supermarket", "liquor"],
        },
        "veto_terms": ["allopathic pharmacy only"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Food & Hospitality
    {
        "concept_id": "ice_cream_parlour",
        "version": 1,
        "labels": ["ice cream parlour", "gelato shop", "frozen yogurt"],
        "definition": "Retail outlet serving scoops of ice cream, sundaes, gelato, and frozen desserts.",
        "signals": {
            "defining_terms": {"strong": ["ice cream", "gelato", "frozen dessert", "sundae parlour", "kulfi"]},
            "supporting_terms": {"medium": ["scoop", "cone", "waffle cone", "shakes", "falooda"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["food_and_drink.ice_cream", "food_and_drink.dessert"],
            "host": ["shopping_mall", "food_court"],
            "incompatible": ["hardware_store", "pharmacy"],
        },
        "veto_terms": ["dry cleaner", "hardware"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "pizzeria",
        "version": 1,
        "labels": ["pizzeria", "pizza restaurant", "pizza delivery"],
        "definition": "Dining or delivery restaurant specializing in pizza.",
        "signals": {
            "defining_terms": {"strong": ["pizza", "pizzeria", "wood fired pizza", "slice"]},
            "supporting_terms": {"medium": ["garlic bread", "pasta", "crust", "mozzarella", "calzone"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["food_and_drink.restaurant.pizza"],
            "host": ["restaurant", "food_court"],
            "incompatible": ["clothing_store", "optician"],
        },
        "veto_terms": ["jewellery", "pet shop"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "tea_stall",
        "version": 1,
        "labels": ["tea stall", "chai point", "tea bar", "chai shop"],
        "definition": "Shop or stall serving hot tea, chai, snacks, and biscuits.",
        "signals": {
            "defining_terms": {"strong": ["chai", "tea stall", "chai point", "tea bar", "kadak chai", "irani chai"]},
            "supporting_terms": {"medium": ["samosa", "bun maska", "biscuit", "kulhad", "filter coffee"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["food_and_drink.cafe.tea_house"],
            "host": ["kiosk", "market"],
            "incompatible": ["car_dealership"],
        },
        "veto_terms": ["car repair", "dental"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "biryani_restaurant",
        "version": 1,
        "labels": ["biryani house", "biryani restaurant", "dum biryani"],
        "definition": "Restaurant specialising in traditional dum biryani and rice delicacies.",
        "signals": {
            "defining_terms": {"strong": ["biryani", "dum biryani", "hyderabadi biryani", "biriyani", "donne biryani"]},
            "supporting_terms": {"medium": ["kebab", "raita", "salan", "mutton biryani", "chicken biryani"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["food_and_drink.restaurant.indian"],
            "host": ["restaurant"],
            "incompatible": ["supermarket", "salon"],
        },
        "veto_terms": ["dry cleaner", "electronics repair"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Retail & Specialty Stores
    {
        "concept_id": "organic_store",
        "version": 1,
        "labels": ["organic store", "organic grocery", "bio store"],
        "definition": "Retail shop offering organic food, chemical-free groceries, and natural products.",
        "signals": {
            "defining_terms": {"strong": ["organic store", "organic foods", "bio market", "natural grocery", "chemical free"]},
            "supporting_terms": {"medium": ["cold pressed oil", "millets", "desi cow ghee", "sustainable", "vegan"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.grocery.health_food", "shopping.grocery.organic"],
            "host": ["supermarket"],
            "incompatible": ["fast_food", "hardware"],
        },
        "veto_terms": ["car wash", "tyre shop"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "toy_store",
        "version": 1,
        "labels": ["toy store", "toys shop", "kids toys", "game shop"],
        "definition": "Retail store selling children's toys, board games, dolls, and action figures.",
        "signals": {
            "defining_terms": {"strong": ["toy store", "toys shop", "kids toys", "games & toys", "board games"]},
            "supporting_terms": {"medium": ["lego", "dolls", "action figures", "puzzles", "remote control car", "baby games"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.toys_and_games"],
            "host": ["shopping_mall", "department_store"],
            "incompatible": ["liquor", "butcher"],
        },
        "veto_terms": ["car repair", "adult store"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "sports_goods_store",
        "version": 1,
        "labels": ["sports store", "sports shop", "fitness equipment store"],
        "definition": "Store retailing sporting goods, athletic wear, cricket gear, and fitness items.",
        "signals": {
            "defining_terms": {"strong": ["sports store", "sports shop", "cricket gear", "badminton racket", "fitness equipment"]},
            "supporting_terms": {"medium": ["decathlon", "dumbbells", "sportswear", "football", "tennis", "gym wear"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.sporting_goods"],
            "host": ["shopping_mall"],
            "incompatible": ["pharmacy", "bakery"],
        },
        "veto_terms": ["medical clinic", "pharmacy"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "eyewear_store",
        "version": 1,
        "labels": ["eyewear store", "optical shop", "spectacles store", "sunglasses shop"],
        "definition": "Retail store selling frames, sunglasses, lenses, and contact lenses.",
        "signals": {
            "defining_terms": {"strong": ["eyewear", "optical shop", "opticals", "spectacles", "lenskart", "sunglasses"]},
            "supporting_terms": {"medium": ["contact lenses", "frames", "eye testing", "anti glare", "power glasses"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.optician", "shopping.eyewear"],
            "host": ["eye_clinic", "mall"],
            "incompatible": ["butcher", "hardware"],
        },
        "veto_terms": ["hardware", "mechanic"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Professional & Business Services
    {
        "concept_id": "chartered_accountant",
        "version": 1,
        "labels": ["chartered accountant", "ca firm", "tax consultant", "auditor"],
        "definition": "Professional accounting, taxation, GST filing, and financial auditing practice.",
        "signals": {
            "defining_terms": {"strong": ["chartered accountant", "ca firm", "tax consultant", "auditor", "gst practitioner"]},
            "supporting_terms": {"medium": ["income tax return", "audit", "balance sheet", "tds filing", "company registration"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["professional_services.accounting_and_bookkeeping", "professional_services.tax_consultant"],
            "host": ["office_building"],
            "incompatible": ["restaurant", "garage"],
        },
        "veto_terms": ["grocery", "car wash"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "law_firm",
        "version": 1,
        "labels": ["law firm", "advocate office", "legal counsel", "lawyer"],
        "definition": "Legal practice providing court litigation, drafting, and advisory counsel.",
        "signals": {
            "defining_terms": {"strong": ["advocate", "law firm", "legal counsel", "lawyer office", "solicitor", "attorney"]},
            "supporting_terms": {"medium": ["court", "litigation", "legal notice", "affidavit", "property documentation", "notary"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["professional_services.legal"],
            "host": ["office"],
            "incompatible": ["bakery", "hardware"],
        },
        "veto_terms": ["restaurant", "repair shop"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "printing_press",
        "version": 1,
        "labels": ["printing press", "digital printing", "offset printer", "flex printing"],
        "definition": "Commercial printing service for business cards, banners, brochures, and offset print.",
        "signals": {
            "defining_terms": {"strong": ["printing press", "digital printing", "flex printing", "offset printer", "banner printing"]},
            "supporting_terms": {"medium": ["visiting cards", "brochure", "screen print", "pamphlets", "binding", "laser print"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["services.printing", "services.copying_and_printing"],
            "host": ["stationery_store"],
            "incompatible": ["spa", "hospital"],
        },
        "veto_terms": ["spa massage", "dental surgery"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "coworking_space",
        "version": 1,
        "labels": ["coworking space", "shared office", "managed workspace", "flex office"],
        "definition": "Shared and managed office spaces with desks, cabins, and meeting rooms.",
        "signals": {
            "defining_terms": {"strong": ["coworking", "shared office", "managed workspace", "hot desk", "dedicated desk", "wework"]},
            "supporting_terms": {"medium": ["meeting room", "high speed wifi", "virtual office", "startup hub", "business centre"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["business.coworking", "business.office"],
            "host": ["commercial_complex"],
            "incompatible": ["garage", "grocery"],
        },
        "veto_terms": ["car repair", "pet clinic"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Automotive & Mobility
    {
        "concept_id": "car_wash",
        "version": 1,
        "labels": ["car wash", "auto detailing", "ceramic coating", "water wash"],
        "definition": "Vehicle exterior and interior cleaning, pressure washing, and detailing service.",
        "signals": {
            "defining_terms": {"strong": ["car wash", "auto detailing", "ceramic coating", "water wash", "foam wash", "car spa"]},
            "supporting_terms": {"medium": ["interior cleaning", "rubbing polish", "ppf", "wax polish", "bike wash"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["automotive.car_wash", "automotive.repair_and_service"],
            "host": ["fuel_station", "service_station"],
            "incompatible": ["dental_clinic", "bakery"],
        },
        "veto_terms": ["pharmacy", "medical store"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "tyre_dealer",
        "version": 1,
        "labels": ["tyre dealer", "tyre shop", "wheel alignment", "wheel balancing"],
        "definition": "Store selling automotive tyres, tubeless puncture repair, and wheel alignment.",
        "signals": {
            "defining_terms": {"strong": ["tyre dealer", "tyre shop", "wheel alignment", "mrf tyres", "apollo tyres", "bridgestone"]},
            "supporting_terms": {"medium": ["wheel balancing", "nitrogen air", "puncture repair", "tubeless tyre", "rims"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["automotive.tires", "automotive.parts"],
            "host": ["garage", "car_repair"],
            "incompatible": ["restaurant", "clothing_store"],
        },
        "veto_terms": ["ice cream parlour", "clothing"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "car_rental",
        "version": 1,
        "labels": ["car rental", "self drive cars", "taxi hire", "cab service"],
        "definition": "Vehicle hiring agency offering self-drive cars, chauffeurs, and outstation cabs.",
        "signals": {
            "defining_terms": {"strong": ["car rental", "self drive cars", "car hire", "zoomcar", "cab rental", "outstation cabs"]},
            "supporting_terms": {"medium": ["hourly rental", "airport taxi", "innova hire", "sedan rental", "luxury car hire"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["transportation.rental", "transportation.taxi"],
            "host": ["travel_agency"],
            "incompatible": ["bakery", "gym"],
        },
        "veto_terms": ["fitness centre", "spa"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Real Estate & Home Improvement
    {
        "concept_id": "real_estate_agent",
        "version": 1,
        "labels": ["real estate agent", "property consultant", "realtor", "property dealer"],
        "definition": "Brokers and agencies facilitating property sales, rentals, plots, and commercial leasing.",
        "signals": {
            "defining_terms": {"strong": ["real estate", "property consultant", "realtor", "property dealer", "real estate broker"]},
            "supporting_terms": {"medium": ["2bhk", "3bhk", "villa", "plots", "rental flat", "commercial leasing", "rera"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["real_estate.agent", "real_estate.agency"],
            "host": ["commercial_complex"],
            "incompatible": ["restaurant", "salon"],
        },
        "veto_terms": ["car wash", "dental"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "electrician_hardware",
        "version": 1,
        "labels": ["electrical store", "electrical goods", "lighting store", "electrician"],
        "definition": "Store retailing electrical wires, switches, LEDs, fans, and repair accessories.",
        "signals": {
            "defining_terms": {"strong": ["electricals", "electrical store", "lighting shop", "havells", "anchor switches", "led lights"]},
            "supporting_terms": {"medium": ["wiring", "mcb", "exhaust fan", "chandelier", "conduit", "bulb", "socket"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.hardware.electrical", "shopping.lighting"],
            "host": ["hardware_store"],
            "incompatible": ["ice_cream", "clothing"],
        },
        "veto_terms": ["food stall", "clothing boutique"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "plumbing_store",
        "version": 1,
        "labels": ["sanitaryware store", "plumbing store", "bathroom fittings", "pipes & fittings"],
        "definition": "Retail shop selling pipes, faucets, sanitaryware, and plumbing materials.",
        "signals": {
            "defining_terms": {"strong": ["sanitaryware", "plumbing store", "bathroom fittings", "pvc pipes", "cpvc fittings", "jaquar"]},
            "supporting_terms": {"medium": ["faucet", "wash basin", "astral pipes", "taps", "overhead tank", "plumber"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["shopping.hardware.plumbing", "shopping.home_improvement"],
            "host": ["hardware_store"],
            "incompatible": ["cafe", "gym"],
        },
        "veto_terms": ["coffee shop", "salon"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "pest_control",
        "version": 1,
        "labels": ["pest control service", "termite treatment", "disinfestation"],
        "definition": "Professional residential and commercial pest management and termite eradication.",
        "signals": {
            "defining_terms": {"strong": ["pest control", "termite treatment", "bed bug treatment", "cockroach control", "fumigation"]},
            "supporting_terms": {"medium": ["herbal pest control", "fogging", "rodent control", "sanitization", "anti termite"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["services.pest_control", "services.home_maintenance"],
            "host": ["office"],
            "incompatible": ["restaurant", "bakery"],
        },
        "veto_terms": ["sweet shop", "bakery"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    # Education, Kids & Hobbies
    {
        "concept_id": "music_school",
        "version": 1,
        "labels": ["music school", "music academy", "guitar classes", "vocal training"],
        "definition": "Institute teaching musical instruments, classical singing, and sound production.",
        "signals": {
            "defining_terms": {"strong": ["music school", "music academy", "guitar classes", "piano classes", "carnatic music", "hindustani vocal"]},
            "supporting_terms": {"medium": ["violin", "drums", "keyboard", "western vocals", "trinity exam", "flute"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["education.music_school", "education.arts_school"],
            "host": ["cultural_centre"],
            "incompatible": ["car_wash", "butcher"],
        },
        "veto_terms": ["tyre dealer", "car repair"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "dance_academy",
        "version": 1,
        "labels": ["dance academy", "dance class", "bharatanatyam institute", "zumba studio"],
        "definition": "Dance institute offering classical, contemporary, hip-hop, and fitness dance classes.",
        "signals": {
            "defining_terms": {"strong": ["dance academy", "dance classes", "dance studio", "bharatanatyam", "kathak", "contemporary dance"]},
            "supporting_terms": {"medium": ["zumba", "hip hop", "salsa", "choreography", "dance fitness", "kuchipudi"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["education.dance_school", "education.arts_school"],
            "host": ["studio", "fitness_centre"],
            "incompatible": ["hardware_store", "garage"],
        },
        "veto_terms": ["hardware", "mechanic"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "preschool_daycare",
        "version": 1,
        "labels": ["preschool", "play school", "daycare", "kindergarten", "nursery"],
        "definition": "Early childhood education centre, play school, and day care facility for toddlers.",
        "signals": {
            "defining_terms": {"strong": ["preschool", "play school", "daycare", "kindergarten", "montessori", "nursery school"]},
            "supporting_terms": {"medium": ["eurokids", "kidzee", "toddler", "after school care", "early learning", "activity centre"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["education.preschool", "services.child_care"],
            "host": ["school"],
            "incompatible": ["bar", "nightclub", "liquor"],
        },
        "veto_terms": ["bar and restaurant", "pub", "wine shop"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
    {
        "concept_id": "yoga_studio",
        "version": 1,
        "labels": ["yoga studio", "yoga centre", "yoga classes", "hatha yoga"],
        "definition": "Dedicated studio offering yoga asanas, meditation, and pranayama sessions.",
        "signals": {
            "defining_terms": {"strong": ["yoga studio", "yoga centre", "yoga classes", "hatha yoga", "ashtanga yoga", "iyengar yoga"]},
            "supporting_terms": {"medium": ["pranayama", "meditation", "surya namaskar", "mindfulness", "yoga teacher training"]},
            "non_evidence": "inherit",
        },
        "categories": {
            "defining": ["health_and_beauty.yoga", "fitness.yoga_studio"],
            "host": ["wellness_centre", "gym"],
            "incompatible": ["fast_food", "car_dealer"],
        },
        "veto_terms": ["liquor store", "bar"],
        "brands": {"incompatible": []},
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35},
    },
]


def seed_concepts():
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    for item in ADDITIONAL_CONCEPTS:
        cid = item["concept_id"]
        target = CONCEPTS_DIR / f"{cid}.yaml"
        if not target.exists():
            target.write_text(yaml.dump(item, sort_keys=False), encoding="utf-8")
            created += 1
            print(f"Created: {cid}.yaml")
        else:
            print(f"Already exists: {cid}.yaml")

    print(f"Seeding complete. Added {created} new concept cards.")


if __name__ == "__main__":
    seed_concepts()
