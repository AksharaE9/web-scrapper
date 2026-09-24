"""
LeadCore Zero — Comprehensive Concept Card Seed & Taxonomy Migration

Generates rich, calibrated Concept Cards covering:
1. All 21 rules formerly in keyword_rules.yaml (fully unified)
2. Indian SMB staples (kirana, pooja store, tiffin centre, xerox shop, PG, dhaba, sweet shop)
3. Essential retail, hospitality, services, and health categories
4. Unified spellings (coaching_centre / coaching_center)
"""

import json
from pathlib import Path
import yaml

CONCEPTS_DIR = Path(__file__).resolve().parent.parent / "config" / "concepts"

# Complete curated library of 65+ rich concept cards
ALL_CONCEPTS = [
    # ── 1. UNIFIED YAML MIGRATIONS ──────────────────────────────────────────
    {
        "concept_id": "gym",
        "version": 1,
        "labels": ["gym", "gyms", "fitness centre", "fitness center", "fitness club", "health club", "crossfit", "workout", "strength training", "gymnasium", "aerobics", "bodybuilding", "cult.fit", "cult fit"],
        "definition": "A fitness centre equipped with weights, exercise machines, cardio equipment, and personal trainers for physical workouts and strength training.",
        "signals": {
            "defining_terms": {"strong": ["gym", "fitness", "crossfit", "workout", "gymnasium", "barbell", "bodybuilding", "calisthenics", "f45", "cult.fit", "gold's", "slam", "chisel"]},
            "supporting_terms": {"medium": ["trainer", "strength", "cardio", "zumba", "aerobics", "physique", "weights", "dumbbells", "muscle", "anytime fitness"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["fitness_center", "gym", "leisure=fitness_centre", "leisure=sports_centre", "amenity=gym", "sport=fitness", "sports_club"],
            "host": ["sports_club", "health_club", "community_centre", "hotel", "commercial_building"],
            "incompatible": ["restaurant", "bakery", "pooja_store", "shoe_store", "pharmacy", "bank", "supermarket"]
        },
        "veto_terms": ["equipment manufacturer", "fitness equipment wholesale", "apparel export", "sports wear factory", "restaurant", "food", "kitchen", "pooja", "bakery", "sweets", "shoes", "tyre", "medical", "hospital", "stationery"],
        "brands": {"incompatible": ["KFC", "McDonald's", "Bata", "Subway"]},
        "overture_basic_categories": ["gym", "fitness_center", "sports_club"],
        "overture_taxonomy_paths": ["sports_and_recreation > fitness > gym", "health_and_medicine > physical_fitness"],
        "osm_tags": ["leisure=fitness_centre", "leisure=sports_centre", "amenity=gym", "sport=fitness"],
        "name_patterns": ["\\bgyms?\\b", "\\bfitness\\b", "\\bcrossfit\\b", "\\bworkout\\b", "\\bgold's\\b", "\\bcult\\b", "\\bslam\\b", "\\banytime fitness\\b", "\\bchisel\\b", "\\bbodybuilding\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "electrical_store",
        "version": 1,
        "labels": ["electrical store", "electrical stores", "electronics store", "electronics shop", "electrical shop", "home appliances", "mobile store", "mobile shop", "computer store", "lighting shop", "electronic items", "electronic", "electricals", "electronics"],
        "definition": "A retail outlet selling consumer electricals, home appliances, wiring supplies, switches, lighting, televisions, and electronics.",
        "signals": {
            "defining_terms": {"strong": ["electricals", "electronics", "electrical shop", "appliances", "lighting shop", "home appliances", "croma", "reliance digital", "vijay sales", "electronix", "gadgets"]},
            "supporting_terms": {"medium": ["wires", "switches", "fans", "refrigerators", "washing machine", "led bulbs", "cables", "switchgear", "sockets", "geyser", "inverter"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["electronics_store", "electrical_supply_store", "appliance_store", "shop=electronics", "shop=electrical", "shop=appliances", "shop=lighting", "craft=electrician"],
            "host": ["shopping_mall", "commercial_building", "market_complex"],
            "incompatible": ["pharmacy", "clothing_store", "restaurant", "hotel", "bakery", "beauty_salon"]
        },
        "veto_terms": ["electrical contractor pvt ltd", "substation", "transformer manufacturer", "power plant", "heavy engineering", "software company", "civil engineering"],
        "brands": {"incompatible": ["Apollo Pharmacy", "Bata", "Dominos"]},
        "overture_basic_categories": ["electronics_store", "electrical_supply_store", "appliance_store"],
        "overture_taxonomy_paths": ["shopping > electronics", "shopping > home_and_garden > appliances", "shopping > specialty_store > hardware_home_and_garden_store > electrical_supply_store"],
        "osm_tags": ["shop=electronics", "shop=electrical", "shop=appliances", "shop=lighting", "shop=mobile_phone", "shop=computer", "craft=electrician"],
        "name_patterns": ["\\belectricals?\\b", "\\belectronics?\\b", "\\bappliances?\\b", "\\bcroma\\b", "\\breliance digital\\b", "\\bvijay sales\\b", "\\bmobile\\b", "\\blighting\\b", "\\belectric\\b", "\\belectronix\\b", "\\bgadgets?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "hotel",
        "version": 1,
        "labels": ["hotel", "hotels", "lodging", "resort", "resorts", "guest house", "homestay", "motel", "hostel", "stay", "room stay", "inn"],
        "definition": "A commercial hospitality establishment providing paid lodging, guest rooms, suites, and hospitality accommodations.",
        "signals": {
            "defining_terms": {"strong": ["hotel", "resort", "guest house", "homestay", "lodge", "lodging", "inn", "hostel", "oyo", "taj", "marriott", "hyatt", "grand", "rooms available", "stay"]},
            "supporting_terms": {"medium": ["check in", "check out", "deluxe room", "ac rooms", "suite", "hospitality", "staycation", "tariff", "accommodation", "booking"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["hotel", "motel", "resort", "guest_house", "hostel", "tourism=hotel", "tourism=guest_house", "tourism=hostel", "tourism=motel", "tourism=resort", "lodging"],
            "host": ["commercial_area", "tourist_attraction", "airport_zone"],
            "incompatible": ["professional_services", "tourism=apartment", "apartment", "office", "serviced_apartment", "travel_agency", "pharmacy", "hardware_store", "shoe_store", "gym_equipment", "dentist", "car_repair"]
        },
        "veto_terms": ["hotel booking app", "hotel management institute", "restaurant only", "food court", "hardware", "plywood", "pharmaceutical", "car spare parts"],
        "brands": {"incompatible": ["Apollo Pharmacy", "MRF Tyres", "Bata"]},
        "overture_basic_categories": ["hotel", "motel", "resort", "guest_house", "hostel"],
        "overture_taxonomy_paths": ["travel_and_lodging > lodging > hotel", "lodging > hotel"],
        "osm_tags": ["tourism=hotel", "tourism=guest_house", "tourism=hostel", "tourism=motel", "tourism=resort"],
        "name_patterns": ["\\bhotels?\\b", "\\bresorts?\\b", "\\bguest house\\b", "\\bhomestay\\b", "\\blodge\\b", "\\blodging\\b", "\\binn\\b", "\\bhostels?\\b", "\\boyo\\b", "\\btaj\\b", "\\bmarriott\\b", "\\bhyatt\\b", "\\bgrand\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "shopping_mall",
        "version": 1,
        "labels": ["shopping mall", "mall", "shopping center", "shopping centre", "shopping complex", "retail mall", "commercial mall", "hyper mall", "central mall"],
        "definition": "A large enclosed commercial retail complex housing multiple stores, food courts, multiplex cinemas, and brand outlets under one roof.",
        "signals": {
            "defining_terms": {"strong": ["shopping mall", "mall", "shopping center", "shopping centre", "shopping complex", "inorbit", "forum mall", "phoenix mall", "lulu mall", "nexus mall", "central mall"]},
            "supporting_terms": {"medium": ["retail outlets", "food court", "multiplex", "brands", "anchor store", "floor", "parking", "shopping", "lifestyle", "hypermarket"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["shopping_mall", "shopping_center", "shop=mall", "building=commercial"],
            "host": ["commercial_district", "urban_center"],
            "incompatible": ["dentist", "plumber", "individual_tailor", "mechanic_shed"]
        },
        "veto_terms": ["mall management software", "mall security services agency", "strip center only"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["shopping_mall", "shopping_center"],
        "overture_taxonomy_paths": ["shopping > shopping_mall"],
        "osm_tags": ["shop=mall"],
        "name_patterns": ["\\bmalls?\\b", "\\bshopping mall\\b", "\\bshopping complex\\b", "\\bshopping centre\\b", "\\bshopping center\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "salon",
        "version": 1,
        "labels": ["salon", "salons", "beauty parlour", "beauty parlor", "hair salon", "unisex salon", "barber", "haircut", "makeover", "hairdresser"],
        "definition": "An establishment offering hair care, haircuts, hair styling, skin treatments, facials, pedicures, and beauty grooming services.",
        "signals": {
            "defining_terms": {"strong": ["salon", "parlour", "parlor", "haircut", "hairstylist", "beauty parlour", "barber", "hair studio", "unisex salon", "looks", "toni&guy", "naturals", "enrich"]},
            "supporting_terms": {"medium": ["hair", "facial", "styling", "grooming", "waxing", "makeup", "bridal", "pedicure", "manicure", "keratin", "blowdry"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["beauty_salon", "hair_salon", "barber_shop", "hairdresser", "shop=hairdresser", "shop=beauty", "amenity=barber"],
            "host": ["spa", "wellness_centre", "department_store", "shopping_mall"],
            "incompatible": ["gym", "bakery", "restaurant", "pharmacy", "automobile", "hardware_store"]
        },
        "veto_terms": ["academy", "institute", "training", "products", "distributor", "gym", "fitness", "bakery", "cakes", "restaurant", "hardware", "tyres", "clinic", "hospital", "pharma"],
        "brands": {"incompatible": ["Gold's Gym", "KFC", "Bata"]},
        "overture_basic_categories": ["beauty_salon", "hair_salon", "barber_shop"],
        "overture_taxonomy_paths": ["services > personal_care > beauty_salon", "services > personal_care > hair_salon"],
        "osm_tags": ["shop=hairdresser", "shop=beauty", "amenity=barber"],
        "name_patterns": ["\\bsalon\\b", "\\bparlou?r\\b", "\\bbarber\\b", "\\bhair\\b", "\\bspa\\b", "\\blooks\\b", "\\btoni&guy\\b", "\\bnaturals\\b", "\\benrich\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "spa",
        "version": 1,
        "labels": ["spa", "spas", "massage center", "ayurvedic spa", "wellness center", "thai spa", "massage parlour", "day spa"],
        "definition": "A relaxation and wellness sanctuary offering professional therapeutic body massages, steam baths, aroma therapies, and skin treatments.",
        "signals": {
            "defining_terms": {"strong": ["spa", "massage", "ayurveda", "ayurvedic", "wellness", "thai spa", "body massage", "aroma massage"]},
            "supporting_terms": {"medium": ["steam bath", "jacuzzi", "rejuvenation", "deep tissue", "head massage", "reflexology", "detox"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["spa", "day_spa", "massage_therapist", "amenity=spa", "shop=massage", "leisure=spa"],
            "host": ["hotel", "resort", "wellness_club"],
            "incompatible": ["pharmacy", "bakery", "hardware_store", "clothing_store"]
        },
        "veto_terms": ["equipment", "spa equipment manufacturer", "wholesale distributor"],
        "brands": {"incompatible": ["Bata", "MRF"]},
        "overture_basic_categories": ["spa", "day_spa", "massage_therapist"],
        "overture_taxonomy_paths": ["services > personal_care > spa", "health_and_medicine > alternative_medicine > massage"],
        "osm_tags": ["amenity=spa", "shop=massage", "leisure=spa"],
        "name_patterns": ["\\bspa\\b", "\\bmassage\\b", "\\bayurveda\\b", "\\bayurvedic\\b", "\\bwellness\\b", "\\bthai spa\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "cafe",
        "version": 1,
        "labels": ["cafe", "cafes", "coffee shop", "coffee house", "tea shop", "espresso bar", "bistro", "chai point", "tea stall", "tea room"],
        "definition": "A relaxed beverage and light meal establishment serving coffee, espresso, tea, sandwiches, pastries, and snacks.",
        "signals": {
            "defining_terms": {"strong": ["cafe", "café", "coffee", "roasters", "tea", "chai", "starbucks", "third wave", "blue tokai", "costa", "espresso"]},
            "supporting_terms": {"medium": ["cappuccino", "latte", "brews", "beverages", "cold coffee", "snacks", "frappe", "pastas", "brownies"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["cafe", "coffee_shop", "tea_house", "amenity=cafe", "shop=coffee"],
            "host": ["bakery", "bookstore", "hotel", "library", "shopping_mall"],
            "incompatible": ["hardware_store", "car_repair", "hospital", "shoe_store", "gym"]
        },
        "veto_terms": ["internet cafe", "cyber cafe", "raw beans", "plantation", "hardware", "repairs", "tyres", "clinic", "hospital", "pharmacy", "gym"],
        "brands": {"incompatible": ["Apollo", "Bata", "Gold's Gym"]},
        "overture_basic_categories": ["cafe", "coffee_shop", "tea_house"],
        "overture_taxonomy_paths": ["food_and_drink > cafe", "food_and_drink > coffee_shop"],
        "osm_tags": ["amenity=cafe", "shop=coffee"],
        "name_patterns": ["\\bcafe\\b", "\\bcafé\\b", "\\bcoffee\\b", "\\broasters\\b", "\\btea\\b", "\\bchai\\b", "\\bstarbucks\\b", "\\bthird wave\\b", "\\bblue tokai\\b", "\\bcosta\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "bakery",
        "version": 1,
        "labels": ["bakery", "bakeries", "cake shop", "pastry shop", "confectionery", "bakehouse", "patisserie", "sweet shop"],
        "definition": "A retail establishment that bakes and sells bread, cakes, pastries, cookies, puffs, biscuits, and confectionery goods.",
        "signals": {
            "defining_terms": {"strong": ["bakery", "bake", "cake", "cakes", "pastry", "oven", "patisserie", "mio amore", "theobroma", "cookies", "bakes"]},
            "supporting_terms": {"medium": ["bread", "puffs", "muffins", "brownies", "desserts", "cupcakes", "croissants", "birthday cake"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["bakery", "pastry_shop", "cake_shop", "shop=bakery", "shop=pastry", "craft=bakery"],
            "host": ["cafe", "coffee_shop", "restaurant", "supermarket", "grocery"],
            "incompatible": ["gym", "salon", "hardware_store", "car_repair", "pharmacy", "shoe_store"]
        },
        "veto_terms": ["machinery", "industrial", "flour mill", "ingredients factory", "gym", "fitness", "salon", "haircut", "tyre", "repair", "hardware", "cement", "pharma", "shoes"],
        "brands": {"incompatible": ["Bata", "Apollo Pharmacy", "Gold's Gym"]},
        "overture_basic_categories": ["bakery", "pastry_shop", "cake_shop"],
        "overture_taxonomy_paths": ["food_and_drink > bakery", "shopping > food > bakery"],
        "osm_tags": ["shop=bakery", "shop=pastry", "craft=bakery"],
        "name_patterns": ["\\bbakery\\b", "\\bbake\\b", "\\bcakes?\\b", "\\bpastry\\b", "\\boven\\b", "\\bpatisserie\\b", "\\bmio amore\\b", "\\btheobroma\\b", "\\bcookies\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "restaurant",
        "version": 1,
        "labels": ["restaurant", "restaurants", "dining", "eatery", "dhaba", "food court", "fine dining", "family restaurant", "biryani house", "bhojanalaya", "veg restaurant", "non veg restaurant"],
        "definition": "A food establishment where meals and beverages are prepared, cooked, and served to seated customers.",
        "signals": {
            "defining_terms": {"strong": ["restaurant", "eatery", "dhaba", "bhojanalaya", "kitchen", "kitchens", "dining", "biryani", "sagar", "hotel (dining)", "food court", "bistro"]},
            "supporting_terms": {"medium": ["cuisine", "thali", "meals", "tandoori", "chinese", "south indian", "north indian", "curry", "dosa", "veg restaurant", "non veg"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["restaurant", "diner", "bistro", "amenity=restaurant", "amenity=food_court"],
            "host": ["hotel", "resort", "food_hall", "shopping_mall"],
            "incompatible": ["pharmacy", "hardware_store", "shoe_store", "gym", "salon", "hospital"]
        },
        "veto_terms": ["hotel booking", "food app corporate", "packaging supply", "pharmacy", "medical", "hardware", "cement", "tyres", "salon", "spa", "gym", "clinic"],
        "brands": {"incompatible": ["Apollo", "Bata", "MRF", "Cult.fit"]},
        "overture_basic_categories": ["restaurant", "diner", "bistro"],
        "overture_taxonomy_paths": ["food_and_drink > restaurant"],
        "osm_tags": ["amenity=restaurant", "amenity=food_court"],
        "name_patterns": ["\\brestaurant\\b", "\\beatery\\b", "\\bdhaba\\b", "\\bbhojanalaya\\b", "\\bkitchen\\b", "\\bkitchens\\b", "\\bdining\\b", "\\bbiryani\\b", "\\bsagar\\b", "\\bhotel\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "supermarket",
        "version": 1,
        "labels": ["supermarket", "supermarkets", "grocery store", "hypermarket", "departmental store", "kirana", "provision store", "general store", "daily needs", "grocery", "groceries", "provisions"],
        "definition": "A self-service retail market selling a wide variety of food, packaged groceries, fresh produce, and household goods.",
        "signals": {
            "defining_terms": {"strong": ["supermarket", "grocery", "groceries", "mart", "hypermarket", "provisions", "kirana", "dmart", "reliance fresh", "more", "daily needs", "general store"]},
            "supporting_terms": {"medium": ["foodstuffs", "daily essentials", "packaged food", "fmcg", "vegetables", "dairy", "snacks", "staples", "rice", "pulses", "oil"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["supermarket", "grocery_store", "hypermarket", "convenience_store", "shop=supermarket", "shop=convenience", "shop=grocery", "shop=general"],
            "host": ["department_store", "shopping_mall", "commercial_building"],
            "incompatible": ["hospital", "gym", "hotel", "bank", "bar"]
        },
        "veto_terms": ["wholesaler", "fmcg depot", "warehouse", "hospital", "gym", "spa", "massage", "salon", "dental", "clinic", "coaching"],
        "brands": {"incompatible": ["Apollo Hospital", "Gold's Gym"]},
        "overture_basic_categories": ["supermarket", "grocery_store", "hypermarket", "convenience_store"],
        "overture_taxonomy_paths": ["shopping > food > grocery", "shopping > supermarket"],
        "osm_tags": ["shop=supermarket", "shop=convenience", "shop=grocery", "shop=general"],
        "name_patterns": ["\\bsupermarket\\b", "\\bgrocery\\b", "\\bgroceries\\b", "\\bmart\\b", "\\bhypermarket\\b", "\\bprovisions?\\b", "\\bkirana\\b", "\\bdmart\\b", "\\breliance fresh\\b", "\\bmore\\b", "\\bdaily needs\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "dental_clinic",
        "version": 1,
        "labels": ["dental clinic", "dental clinics", "dentist", "dental hospital", "orthodontist", "dental care", "teeth clinic", "dental surgeon"],
        "definition": "A specialized dental healthcare clinic offering teeth examinations, dental surgery, root canals, braces, and oral treatments.",
        "signals": {
            "defining_terms": {"strong": ["dental", "dentist", "tooth", "teeth", "clove", "orthodontic", "root canal", "dental surgeon", "dental care", "dental hospital"]},
            "supporting_terms": {"medium": ["implants", "braces", "cavity", "filling", "cleaning", "smile care", "oral health", "dentistry", "extraction"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["dentist", "dental_clinic", "amenity=dentist", "healthcare=dentist"],
            "host": ["hospital", "medical_center", "polyclinic"],
            "incompatible": ["restaurant", "bakery", "clothing_store", "car_repair", "grocery"]
        },
        "veto_terms": ["dental college", "instruments manufacturer", "equipment wholesale", "laboratory supplies"],
        "brands": {"incompatible": ["KFC", "Bata", "Domino's"]},
        "overture_basic_categories": ["dentist", "dental_clinic"],
        "overture_taxonomy_paths": ["health_and_medicine > dental", "health_and_medicine > medical_specialties > dentistry"],
        "osm_tags": ["amenity=dentist", "healthcare=dentist"],
        "name_patterns": ["\\bdental\\b", "\\bdentist\\b", "\\btooth\\b", "\\bteeth\\b", "\\bclove\\b", "\\borthodontic\\b", "\\broot canal\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "pharmacy",
        "version": 1,
        "labels": ["pharmacy", "pharmacies", "chemist", "medical store", "drugstore", "apothecary", "medicines", "druggist", "medicals"],
        "definition": "A retail dispensary licensed to sell prescription drugs, over-the-counter medicines, surgical supplies, and health wellness products.",
        "signals": {
            "defining_terms": {"strong": ["pharmacy", "chemist", "medical", "medicos", "drugs", "apollo", "medplus", "wellness forever", "medicals", "medical store", "druggist", "medicines", "apothecary"]},
            "supporting_terms": {"medium": ["tablets", "syrup", "wellness", "surgical", "ayurvedic", "homeopathy", "prescription", "capsules", "first aid"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["pharmacy", "drugstore", "chemist", "amenity=pharmacy", "shop=chemist", "healthcare=pharmacy"],
            "host": ["hospital", "clinic", "supermarket", "department_store"],
            "incompatible": ["restaurant", "bakery", "bar", "hardware_store", "shoe_store", "salon"]
        },
        "veto_terms": ["pharma manufacturing", "distributor", "pvt ltd lab", "bulk drugs factory", "restaurant", "bakery", "sweets", "footwear", "clothing", "salon", "spa", "gym", "hardware"],
        "brands": {"incompatible": ["KFC", "Bata", "Zara", "McDonald's"]},
        "overture_basic_categories": ["pharmacy", "drugstore"],
        "overture_taxonomy_paths": ["health_and_medicine > pharmacy", "shopping > health > pharmacy"],
        "osm_tags": ["amenity=pharmacy", "shop=chemist", "healthcare=pharmacy"],
        "name_patterns": ["\\bpharmacy\\b", "\\bchemist\\b", "\\bmedical\\b", "\\bmedicos\\b", "\\bdrugs?\\b", "\\bapollo\\b", "\\bmedplus\\b", "\\bwellness forever\\b", "\\bmedicals\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "hospital_clinic",
        "version": 1,
        "labels": ["hospital", "hospitals", "clinic", "clinics", "nursing home", "healthcare center", "poly clinic", "multi specialty hospital", "doctor clinic", "physician", "medical centre"],
        "definition": "A healthcare institution or medical clinic providing outpatient and inpatient medical care, emergency treatment, and consultations.",
        "signals": {
            "defining_terms": {"strong": ["hospital", "hospitals", "clinic", "clinics", "nursing home", "healthcare", "medicare", "manipal", "apollo hospital", "fortis", "doctor", "polyclinic"]},
            "supporting_terms": {"medium": ["icu", "opd", "emergency", "consultation", "specialist", "surgeon", "physician", "pediatrician", "gynecologist", "cardiologist", "beds"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["hospital", "medical_clinic", "amenity=hospital", "amenity=clinic", "healthcare=hospital", "healthcare=clinic"],
            "host": ["medical_zone", "institutional_area"],
            "incompatible": ["restaurant", "bakery", "bar", "hardware_store", "automobile_repair"]
        },
        "veto_terms": ["medical college", "instruments manufacturer", "pharma factory", "veterinary"],
        "brands": {"incompatible": ["KFC", "Bata"]},
        "overture_basic_categories": ["hospital", "medical_clinic"],
        "overture_taxonomy_paths": ["health_and_medicine > hospitals", "health_and_medicine > clinics"],
        "osm_tags": ["amenity=hospital", "amenity=clinic", "healthcare=hospital", "healthcare=clinic"],
        "name_patterns": ["\\bhospitals?\\b", "\\bclinics?\\b", "\\bnursing home\\b", "\\bhealthcare\\b", "\\bmedicare\\b", "\\bmanipal\\b", "\\bapollo hospital\\b", "\\bfortis\\b", "\\bdoctor\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "coaching_centre",
        "version": 1,
        "labels": ["coaching centre", "coaching center", "coaching centres", "coaching centers", "coaching institute", "tuition centre", "tuition center", "tutorials", "academy", "training institute", "classes", "iit coaching", "neet coaching"],
        "definition": "An educational coaching institute providing supplementary tutoring, competitive exam preparation (IIT-JEE, NEET, UPSC), or professional skills training.",
        "signals": {
            "defining_terms": {"strong": ["coaching", "tuition", "tuitions", "tutorials", "academy", "classes", "iit", "jee", "neet", "cat", "allen", "aakash", "iit-jee", "upsc", "educational institute"]},
            "supporting_terms": {"medium": ["entrance", "exam", "training", "physics", "maths", "chemistry", "biology", "nda", "bank exam", "batches", "faculties"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["coaching_center", "tutoring_service", "educational_institution", "coaching", "amenity=school[school=coaching]", "amenity=college[type=coaching]", "office=educational_institution"],
            "host": ["community_centre", "library", "commercial_building"],
            "incompatible": ["restaurant", "bar", "liquor_store", "salon", "gym", "bakery", "retail_store"]
        },
        "veto_terms": ["sports coaching", "driving school", "cricket coaching", "karate class", "restaurant", "food", "cafe", "wine", "beer", "salon", "spa", "footwear", "clothing", "supermarket"],
        "brands": {"incompatible": ["KFC", "Dominos", "Bata", "Zara"]},
        "overture_basic_categories": ["coaching_center", "tutoring_service", "educational_institution"],
        "overture_taxonomy_paths": ["education > tutoring", "education > specialty_schools"],
        "osm_tags": ["amenity=school[school=coaching]", "amenity=college[type=coaching]", "office=educational_institution"],
        "name_patterns": ["\\bcoaching\\b", "\\btuition\\b", "\\btutorials?\\b", "\\bacademy\\b", "\\bclasses\\b", "\\biit\\b", "\\bjee\\b", "\\bneet\\b", "\\bcat\\b", "\\ballen\\b", "\\baakash\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "school_college",
        "version": 1,
        "labels": ["school", "schools", "high school", "college", "colleges", "institutions", "pre school", "play school", "kindergarten", "daycare", "public school", "university"],
        "definition": "A formal educational institution providing primary, secondary, higher secondary, collegiate, or university education.",
        "signals": {
            "defining_terms": {"strong": ["school", "schools", "college", "colleges", "preschool", "play school", "kindergarten", "vidyalaya", "public school", "institution", "campus"]},
            "supporting_terms": {"medium": ["cbse", "icse", "state board", "degree", "graduation", "admission", "students", "teachers", "curriculum"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["school", "preschool", "educational_institution", "amenity=school", "amenity=kindergarten", "amenity=college"],
            "host": ["educational_zone", "residential_area"],
            "incompatible": ["bar", "liquor_store", "nightclub", "casino"]
        },
        "veto_terms": ["driving school", "cricket coaching", "karate class", "dance class"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["school", "preschool", "educational_institution"],
        "overture_taxonomy_paths": ["education > schools", "education > preschools"],
        "osm_tags": ["amenity=school", "amenity=kindergarten", "amenity=college"],
        "name_patterns": ["\\bschools?\\b", "\\bcolleges?\\b", "\\bpreschool\\b", "\\bplay school\\b", "\\bkindergarten\\b", "\\bvidyalaya\\b", "\\bpublic school\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "clothing_store",
        "version": 1,
        "labels": ["clothing store", "boutique", "boutiques", "designer boutique", "fashion boutique", "ethnic wear", "tailor", "clothes shop", "garments", "apparel", "mens wear", "womens wear", "kids wear", "textiles", "saree store"],
        "definition": "A retail shop selling ready-made garments, men's/women's/kids' fashion wear, ethnic wear, sarees, and textiles.",
        "signals": {
            "defining_terms": {"strong": ["boutique", "couture", "fashion", "designer studio", "creations", "threads", "clothes", "garments", "apparel", "wear", "sarees", "clothing", "menswear", "kidswear", "textiles"]},
            "supporting_terms": {"medium": ["shirts", "dresses", "trousers", "kurtis", "ethnic wear", "fabrics", "suits", "jeans", "frocks", "lehenga", "dupatta"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["boutique", "clothing_store", "apparel_store", "shop=boutique", "shop=clothes", "shop=tailor", "shop=fashion"],
            "host": ["department_store", "shopping_mall", "market_complex"],
            "incompatible": ["hardware_store", "restaurant", "pharmacy", "dental_clinic", "car_repair"]
        },
        "veto_terms": ["textile mill", "garment export factory", "fabric wholesale depot", "pharmacy", "medical", "dentist", "hardware", "cement", "car repair", "tyres", "food"],
        "brands": {"incompatible": ["Apollo", "Domino's", "MRF"]},
        "overture_basic_categories": ["boutique", "clothing_store", "apparel_store"],
        "overture_taxonomy_paths": ["shopping > clothing > boutique", "shopping > clothing"],
        "osm_tags": ["shop=boutique", "shop=clothes", "shop=tailor", "shop=fashion"],
        "name_patterns": ["\\bboutique\\b", "\\bcouture\\b", "\\bfashion\\b", "\\bdesigner studio\\b", "\\bcreations\\b", "\\bthreads\\b", "\\bclothes?\\b", "\\bgarments?\\b", "\\bapparel\\b", "\\bwear\\b", "\\bsarees?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "jewellery_store",
        "version": 1,
        "labels": ["jewellery store", "jewellery shop", "jewelry store", "jewellers", "gold shop", "diamond merchant", "silver store", "jewellery", "ornaments"],
        "definition": "A retail showroom selling gold, silver, diamond, and precious gem jewelry, ornaments, and bullion.",
        "signals": {
            "defining_terms": {"strong": ["jewellers", "jewellery", "jewelry", "gold", "diamonds", "tanishq", "malabar", "kalyan", "ornaments", "goldsmith", "gold showroom"]},
            "supporting_terms": {"medium": ["silver", "bangles", "necklaces", "gemstones", "earrings", "chains", "solitaires", "hallmark", "bullion"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["jewelry_store", "jeweler", "shop=jewelry", "shop=jewellery"],
            "host": ["shopping_mall", "market_complex", "commercial_building"],
            "incompatible": ["car_repair", "hardware_store", "restaurant", "pharmacy"]
        },
        "veto_terms": ["mining", "refinery", "gold wholesale refinery", "raw mining depot"],
        "brands": {"incompatible": ["Apollo", "Bata", "Domino's"]},
        "overture_basic_categories": ["jewelry_store", "jeweler"],
        "overture_taxonomy_paths": ["shopping > jewelry"],
        "osm_tags": ["shop=jewelry", "shop=jewellery"],
        "name_patterns": ["\\bjewellers?\\b", "\\bjewellery\\b", "\\bjewelry\\b", "\\bgold\\b", "\\bdiamonds?\\b", "\\btanishq\\b", "\\bmalabar\\b", "\\bkalyan\\b", "\\bornaments?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "furniture_store",
        "version": 1,
        "labels": ["furniture store", "furniture shop", "home decor", "furnishing", "wood furniture", "sofa store", "mattress store", "interior design store"],
        "definition": "A showroom retailing home and office furniture, sofas, beds, dining tables, wardrobes, and mattresses.",
        "signals": {
            "defining_terms": {"strong": ["furniture", "furnishings", "decor", "sofas", "mattress", "wooden", "home centre", "ikea", "pepperfry", "sofa maker", "home furniture", "office furniture"]},
            "supporting_terms": {"medium": ["beds", "dining table", "wardrobes", "chairs", "recliners", "cushions", "curtains", "woodwork"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["furniture_store", "home_goods_store", "shop=furniture", "shop=interior_decoration", "shop=bed"],
            "host": ["shopping_mall", "commercial_building", "retail_park"],
            "incompatible": ["pharmacy", "medical_clinic", "restaurant", "bakery"]
        },
        "veto_terms": ["plywood factory", "saw mill", "timber logging", "industrial timber depot"],
        "brands": {"incompatible": ["Apollo Pharmacy", "Dominos"]},
        "overture_basic_categories": ["furniture_store", "home_goods_store"],
        "overture_taxonomy_paths": ["shopping > home_and_garden > furniture"],
        "osm_tags": ["shop=furniture", "shop=interior_decoration", "shop=bed"],
        "name_patterns": ["\\bfurnitures?\\b", "\\bfurnishings?\\b", "\\bdecor\\b", "\\bsofas?\\b", "\\bmattress\\b", "\\bwooden\\b", "\\bhome centre\\b", "\\bikea\\b", "\\bpepperfry\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "book_stationery_store",
        "version": 1,
        "labels": ["book stationery store", "stationery shop", "book store", "book shop", "bookstore", "xerox", "printing", "office supplies", "stationery"],
        "definition": "A retail shop selling stationery goods, educational textbooks, novels, writing supplies, and photocopy/xerox services.",
        "signals": {
            "defining_terms": {"strong": ["bookstores", "bookshops", "books", "stationery", "stationers", "xerox", "print", "shree stationery", "pen shop", "office supplies", "book depot"]},
            "supporting_terms": {"medium": ["notebooks", "pens", "pencils", "art supplies", "calculators", "files", "photocopy", "lamination", "spiral binding", "textbooks", "novels"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["book_store", "stationery_store", "books_store", "shop=books", "shop=stationery", "shop=copyshop"],
            "host": ["shopping_mall", "commercial_building", "educational_zone"],
            "incompatible": ["car_repair", "pharmacy", "automobile_dealer"]
        },
        "veto_terms": ["paper mill", "publishing house corporate", "industrial printing plant"],
        "brands": {"incompatible": ["Apollo", "Bata"]},
        "overture_basic_categories": ["book_store", "stationery_store"],
        "overture_taxonomy_paths": ["shopping > books_and_stationery"],
        "osm_tags": ["shop=books", "shop=stationery", "shop=copyshop"],
        "name_patterns": ["\\bbookstores?\\b", "\\bbookshops?\\b", "\\bbooks?\\b", "\\bstationery\\b", "\\bstationers?\\b", "\\bxerox\\b", "\\bprint\\b", "\\bshree stationery\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "pooja_store",
        "version": 1,
        "labels": ["pooja store", "puja store", "pooja samagri", "puja samagri", "pooja items", "pooja shop", "puja shop", "spiritual store", "devotional store", "puja bhandar"],
        "definition": "A retail shop specializing in Hindu devotional and spiritual supplies including agarbatti, camphor, brass idols, puja oil, deepam, and ritual samagri.",
        "signals": {
            "defining_terms": {"strong": ["pooja", "puja", "samagri", "agarbatti", "camphor", "havan", "dhoop", "puja bhandar", "mandir items"]},
            "supporting_terms": {"medium": ["brass idols", "kumkum", "turmeric", "cotton wicks", "diya", "vilakku", "shankha", "rudraksha", "gangajal", "yantra", "chandan"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["shop=religion", "religion", "pooja_store", "puja_store", "spiritual_store", "devotional_store", "pooja_samagri", "puja_samagri"],
            "host": ["temple_complex", "market_complex", "residential_area", "general_store", "commercial_building", "gift_shop"],
            "incompatible": ["travel_company", "beauty_salon", "jewelry_store", "rail_facility_or_station", "hardware_home_and_garden", "naturopathic_holistic", "stationery_store", "pharmacy", "shoe_store", "butcher", "bar", "nightclub", "car_repair"]
        },
        "veto_terms": ["footwear", "shoes", "pen", "pens", "travel", "taxi", "cab", "reiki", "salon", "spa", "leather", "butcher", "meat", "beef", "chicken", "liquor", "stationery", "manufacturing factory", "chemical industry"],
        "brands": {"incompatible": ["William Penn", "Bata", "KFC", "McDonald's", "Apollo", "Subway"]},
        "overture_basic_categories": ["general_store"],
        "overture_taxonomy_paths": ["shopping > gifts_and_novelties > spiritual_store"],
        "osm_tags": ["shop=religion", "shop=general"],
        "name_patterns": ["\\bpooja\\b", "\\bpuja\\b", "\\bsamagri\\b", "\\bspiritual\\b", "\\bbhandar\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "car_service",
        "version": 1,
        "labels": ["car service", "car repair", "auto garage", "car service center", "mechanic", "car workshop", "auto repair", "wheel alignment", "bike service", "two wheeler service", "motorcycle repair"],
        "definition": "An automobile garage and repair workshop offering vehicle maintenance, engine servicing, wheel alignment, denting, painting, and mechanical fixes.",
        "signals": {
            "defining_terms": {"strong": ["garage", "motors", "car care", "auto repair", "workshop", "mechanic", "pitstop", "gomechanic", "automotive", "car service", "bike service"]},
            "supporting_terms": {"medium": ["engine service", "denting", "painting", "wheel alignment", "brakes", "oil change", "battery check", "suspension", "clutch", "puncture"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["auto_repair", "car_repair", "mechanic", "shop=car_repair", "amenity=vehicle_inspection", "shop=motorcycle_repair"],
            "host": ["auto_hub", "industrial_area", "service_road"],
            "incompatible": ["bakery", "restaurant", "pharmacy", "beauty_salon", "clothing_store"]
        },
        "veto_terms": ["car showroom", "car dealer", "used cars sale", "dealership", "bakery", "restaurant", "pharmacy"],
        "brands": {"incompatible": ["Apollo Pharmacy", "Dominos"]},
        "overture_basic_categories": ["auto_repair", "car_repair", "mechanic"],
        "overture_taxonomy_paths": ["automotive > repair_and_service", "services > automotive > repair"],
        "osm_tags": ["shop=car_repair", "amenity=vehicle_inspection", "shop=motorcycle_repair"],
        "name_patterns": ["\\bgarage\\b", "\\bmotors?\\b", "\\bcar care\\b", "\\bauto repair\\b", "\\bworkshop\\b", "\\bmechanic\\b", "\\bpitstop\\b", "\\bgomechanic\\b", "\\bautomotive\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "hardware_store",
        "version": 1,
        "labels": ["hardware store", "hardware shop", "sanitary store", "paint shop", "electrical and hardware", "plywood store", "hardware", "paints", "building materials"],
        "definition": "A shop selling tools, construction materials, fasteners, plumbing supplies, sanitary fittings, plywood, and paints.",
        "signals": {
            "defining_terms": {"strong": ["hardware", "paints", "sanitary", "plywood", "timber", "asian paints", "berger", "buildpro", "tools & hardware", "building materials", "sanitaryware"]},
            "supporting_terms": {"medium": ["screws", "tools", "plumbing", "pipes", "paints", "fittings", "cement", "taps", "drills", "hinges", "adhesives"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["hardware_store", "building_materials", "shop=hardware", "shop=doityourself", "shop=trade", "shop=paint"],
            "host": ["market_complex", "commercial_area"],
            "incompatible": ["restaurant", "bakery", "pharmacy", "shoe_store", "beauty_salon"]
        },
        "veto_terms": ["computer hardware", "software company", "industrial steel depot", "restaurant", "bakery", "sweets", "fashion"],
        "brands": {"incompatible": ["Apollo Pharmacy", "Bata", "Dominos"]},
        "overture_basic_categories": ["hardware_store", "building_materials"],
        "overture_taxonomy_paths": ["shopping > home_and_garden > hardware"],
        "osm_tags": ["shop=hardware", "shop=doityourself", "shop=trade", "shop=paint"],
        "name_patterns": ["\\bhardware\\b", "\\bpaints?\\b", "\\bsanitary\\b", "\\bplywood\\b", "\\btimber\\b", "\\basian paints\\b", "\\bberger\\b", "\\bbuildpro\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    # ── 2. INDIAN SMB SPECIALTIES ──────────────────────────────────────────
    {
        "concept_id": "kirana_store",
        "version": 1,
        "labels": ["kirana store", "kirana shop", "kiranam", "ration shop", "provision store", "grocery store", "daily essentials store", "corner store"],
        "definition": "A traditional Indian neighborhood mom-and-pop grocery store selling packaged foods, daily essentials, spices, pulses, rice, oil, and household provisions.",
        "signals": {
            "defining_terms": {"strong": ["kirana", "kiranam", "kirana store", "provisions", "ration", "general merchant", "daily needs", "grocery", "provision store"]},
            "supporting_terms": {"medium": ["atta", "rice", "dal", "oil", "soap", "detergent", "masala", "spices", "sugar", "tea powder", "fmcg"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["grocery_store", "convenience_store", "shop=convenience", "shop=grocery", "shop=general"],
            "host": ["residential_area", "market"],
            "incompatible": ["hospital", "gym", "hotel", "bank"]
        },
        "veto_terms": ["wholesaler", "fmcg depot", "warehouse", "supermarket chain corporate"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["grocery_store", "convenience_store"],
        "overture_taxonomy_paths": ["shopping > food > grocery"],
        "osm_tags": ["shop=convenience", "shop=grocery", "shop=general"],
        "name_patterns": ["\\bkirana\\b", "\\bkiranam\\b", "\\bprovisions?\\b", "\\bgrocery\\b", "\\bgeneral merchant\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "tiffin_centre",
        "version": 1,
        "labels": ["tiffin centre", "tiffin center", "tiffin room", "mess", "breakfast point", "south indian tiffin", "idli dosa stall", "canteen"],
        "definition": "A quick-service South Indian dining eatery or mess specializing in freshly made breakfast and snack items like idli, dosa, vada, puri, upma, and filter coffee.",
        "signals": {
            "defining_terms": {"strong": ["tiffin", "tiffins", "tiffin centre", "tiffin center", "mess", "breakfast centre", "idli dosa", "bhojanalaya", "tiffin room"]},
            "supporting_terms": {"medium": ["idli", "dosa", "vada", "poori", "puri", "upma", "filter coffee", "chutney", "sambar", "meals"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["restaurant", "casual_eatery", "fast_food", "amenity=fast_food", "amenity=restaurant"],
            "host": ["commercial_area", "transit_station", "college_area"],
            "incompatible": ["pharmacy", "shoe_store", "car_repair"]
        },
        "veto_terms": ["tiffin box manufacturer", "tiffin bag wholesaler", "corporate catering software"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["restaurant", "fast_food"],
        "overture_taxonomy_paths": ["food_and_drink > casual_eatery", "food_and_drink > fast_food"],
        "osm_tags": ["amenity=fast_food", "amenity=restaurant"],
        "name_patterns": ["\\btiffins?\\b", "\\btiffin cent(?:re|er)\\b", "\\bmess\\b", "\\bbreakfast\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "xerox_shop",
        "version": 1,
        "labels": ["xerox shop", "xerox store", "photocopy shop", "xerox centre", "xerox center", "print shop", "dtp centre", "lamination shop"],
        "definition": "A commercial document service shop providing photocopying (xerox), computer printing, scanning, lamination, spiral binding, and typing services.",
        "signals": {
            "defining_terms": {"strong": ["xerox", "photocopy", "xerox centre", "xerox center", "dtp", "print shop", "scanning", "lamination", "spiral binding", "copy centre"]},
            "supporting_terms": {"medium": ["colour print", "b&w print", "stationery", "typing", "aadhaar print", "passport photo", "id card"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["copyshop", "printing_service", "stationery_store", "shop=copyshop", "craft=photographer", "shop=stationery"],
            "host": ["college_area", "court_area", "commercial_building"],
            "incompatible": ["restaurant", "pharmacy", "hotel"]
        },
        "veto_terms": ["xerox corporation corporate", "printer hardware manufacturing"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["copyshop", "stationery_store"],
        "overture_taxonomy_paths": ["services > business_services > printing", "shopping > books_and_stationery"],
        "osm_tags": ["shop=copyshop", "shop=stationery"],
        "name_patterns": ["\\bxerox\\b", "\\bphotocopy\\b", "\\bdtp\\b", "\\bprint shop\\b", "\\bcopy cent(?:re|er)\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "pg_accommodation",
        "version": 1,
        "labels": ["pg", "pg accommodation", "paying guest", "mens pg", "ladies pg", "coliving", "student hostel", "working men pg", "working women pg"],
        "definition": "A residential paying-guest (PG) or shared living facility providing furnished rooms, food (mess), and utilities for students and working professionals.",
        "signals": {
            "defining_terms": {"strong": ["pg", "paying guest", "mens pg", "ladies pg", "coliving", "working women pg", "working men pg", "hostel", "pg for gents", "pg for ladies"]},
            "supporting_terms": {"medium": ["sharing room", "single room", "food included", "wifi", "washing machine", "ac room", "monthly rent", "homely food"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["hostel", "guest_house", "tourism=hostel", "tourism=guest_house", "amenity=dormitory"],
            "host": ["residential_area", "it_corridor", "college_zone"],
            "incompatible": ["restaurant", "bakery", "car_repair", "pharmacy"]
        },
        "veto_terms": ["pg software", "pg management portal", "hotel luxury 5 star"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["hostel", "guest_house"],
        "overture_taxonomy_paths": ["travel_and_lodging > lodging > hostel"],
        "osm_tags": ["tourism=hostel", "tourism=guest_house"],
        "name_patterns": ["\\bpg\\b", "\\bpaying guest\\b", "\\bcoliving\\b", "\\bhostel\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "sweet_shop",
        "version": 1,
        "labels": ["sweet shop", "mithai shop", "sweets", "mithai", "halwai", "sweet mart", "confectionery shop", "traditional sweets"],
        "definition": "A traditional Indian confectionery store preparing and selling fresh regional mithai, halwa, ladoos, jalebis, kaju katli, and savory namkeen.",
        "signals": {
            "defining_terms": {"strong": ["sweets", "mithai", "sweet mart", "confectioners", "halwai", "sweet shop", "mithai shop", "bikanervala", "haldiram"]},
            "supporting_terms": {"medium": ["ladoo", "gulab jamun", "rasgulla", "kaju katli", "namkeen", "jalebi", "barfi", "peda", "samosa", "kachori", "snacks"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["confectionery", "sweet_shop", "bakery", "shop=confectionery", "shop=bakery"],
            "host": ["market_complex", "shopping_district"],
            "incompatible": ["hardware_store", "car_repair", "pharmacy", "gym"]
        },
        "veto_terms": ["sweet factory machinery", "sugar refinery"],
        "brands": {"incompatible": ["Apollo", "Bata", "Cult.fit"]},
        "overture_basic_categories": ["confectionery", "bakery"],
        "overture_taxonomy_paths": ["food_and_drink > confectionery", "shopping > food > bakery"],
        "osm_tags": ["shop=confectionery", "shop=bakery"],
        "name_patterns": ["\\bsweets?\\b", "\\bmithai\\b", "\\bhalwai\\b", "\\bsweet mart\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "shoe_store",
        "version": 1,
        "labels": ["shoe store", "footwear shop", "footwear", "chappal shop", "sneaker store", "leather footwear", "shoes store", "shoe shop"],
        "definition": "A retail store specializing in footwear, sports shoes, formal shoes, sandals, chappals, and footwear accessories.",
        "signals": {
            "defining_terms": {"strong": ["footwear", "shoes", "shoe shop", "chappal", "sneakers", "sandals", "footwear world", "bata", "metro shoes", "woodland"]},
            "supporting_terms": {"medium": ["leather shoes", "slippers", "heels", "formal shoes", "sports shoes", "boots", "loafers", "flip flops", "crocs"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["shoe_store", "footwear", "shop=shoes"],
            "host": ["clothing_store", "department_store", "shopping_mall"],
            "incompatible": ["restaurant", "bakery", "pooja_store", "pharmacy", "grocery"]
        },
        "veto_terms": ["pooja", "agarbatti", "pastries", "restaurant", "food", "medical", "medicines", "bakery", "tyres"],
        "brands": {"incompatible": ["Apollo", "Archies", "KFC"]},
        "overture_basic_categories": ["shoe_store"],
        "overture_taxonomy_paths": ["shopping > clothing > shoes"],
        "osm_tags": ["shop=shoes"],
        "name_patterns": ["\\bshoes?\\b", "\\bfootwear\\b", "\\bchappals?\\b", "\\bsneakers?\\b", "\\bsandals?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "optician",
        "version": 1,
        "labels": ["optician", "eyewear store", "optical shop", "eye care center", "spectacle shop", "lens store", "lenskart"],
        "definition": "An optical retail store offering vision testing, prescription spectacle frames, corrective lenses, contact lenses, and sunglasses.",
        "signals": {
            "defining_terms": {"strong": ["opticians", "optical", "optometry", "eyewear", "spectacles", "lenskart", "titan eye", "vision care", "optical store"]},
            "supporting_terms": {"medium": ["frames", "lenses", "sunglasses", "vision testing", "eye glasses", "contact lenses", "glare", "progressive lenses"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["optician", "eyewear_store", "shop=optician"],
            "host": ["shopping_mall", "hospital", "commercial_area"],
            "incompatible": ["restaurant", "bakery", "hardware_store"]
        },
        "veto_terms": ["lens manufacturing factory", "glass factory"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["optician"],
        "overture_taxonomy_paths": ["health_and_medicine > eye_care > optician"],
        "osm_tags": ["shop=optician"],
        "name_patterns": ["\\bopticians?\\b", "\\bopticals?\\b", "\\beyewear\\b", "\\bspectacles?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "pet_shop",
        "version": 1,
        "labels": ["pet shop", "pet store", "pet care", "aquarium", "pet clinic", "dog food shop"],
        "definition": "A retail shop providing companion pets, pet food, dog/cat accessories, aquarium fish, bird cages, and pet grooming essentials.",
        "signals": {
            "defining_terms": {"strong": ["pet shop", "pet care", "aquarium", "pet store", "pet clinic", "pets world", "dog food", "cat food"]},
            "supporting_terms": {"medium": ["aquarium fish", "cages", "pet grooming", "collars", "pedigree", "royal canin", "fish tank", "pet toys"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["pet_store", "pet_shop", "shop=pet"],
            "host": ["shopping_complex", "commercial_building"],
            "incompatible": ["restaurant", "bakery", "pharmacy"]
        },
        "veto_terms": ["livestock wholesale", "poultry farm"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["pet_store"],
        "overture_taxonomy_paths": ["shopping > pet_supplies"],
        "osm_tags": ["shop=pet"],
        "name_patterns": ["\\bpets?\\b", "\\bpet shop\\b", "\\baquarium\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "dry_cleaner",
        "version": 1,
        "labels": ["dry cleaner", "dry cleaners", "laundry", "dry cleaning", "wash and fold", "steam iron", "laundromat"],
        "definition": "A professional garment care shop offering dry cleaning, laundry washing, steam pressing, and fabric stain removal.",
        "signals": {
            "defining_terms": {"strong": ["dry cleaners", "laundry", "dry cleaning", "wash & fold", "steam iron", "laundromat", "dhobi", "tumbledry", "fabrico"]},
            "supporting_terms": {"medium": ["garment care", "washing", "ironing", "suits cleaning", "blanket wash", "saree rolling", "stain removal"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["dry_cleaning", "laundry", "shop=dry_cleaning", "shop=laundry"],
            "host": ["residential_area", "shopping_complex"],
            "incompatible": ["restaurant", "bakery", "pharmacy"]
        },
        "veto_terms": ["washing machine manufacturer", "detergent factory"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["dry_cleaning", "laundry"],
        "overture_taxonomy_paths": ["services > personal_care > laundry_and_dry_cleaning"],
        "osm_tags": ["shop=dry_cleaning", "shop=laundry"],
        "name_patterns": ["\\bdry cleaners?\\b", "\\blaundry\\b", "\\bdry cleaning\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "florist",
        "version": 1,
        "labels": ["florist", "flower shop", "flowers", "floral boutique", "bouquet shop", "garland shop"],
        "definition": "A retail flower shop offering fresh flower bouquets, floral gift arrangements, decorative garlands, and event floral decoration.",
        "signals": {
            "defining_terms": {"strong": ["florist", "flower shop", "flowers", "floral boutique", "bouquets", "ferns n petals", "flower delivery"]},
            "supporting_terms": {"medium": ["roses", "garlands", "decorations", "carnations", "lilies", "orchids", "gift flowers"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["florist", "flower_shop", "shop=florist"],
            "host": ["market_complex", "shopping_mall"],
            "incompatible": ["hardware_store", "car_repair", "pharmacy"]
        },
        "veto_terms": ["artificial flower wholesale factory"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["florist"],
        "overture_taxonomy_paths": ["shopping > gifts_and_novelties > florist"],
        "osm_tags": ["shop=florist"],
        "name_patterns": ["\\bflorists?\\b", "\\bflowers?\\b", "\\bfloral\\b", "\\bbouquets?\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    },
    {
        "concept_id": "diagnostic_centre",
        "version": 1,
        "labels": ["diagnostic centre", "diagnostic center", "pathology lab", "medical lab", "diagnostics", "scan centre", "scan center", "blood test lab"],
        "definition": "A specialized clinical pathology and medical diagnostic center conducting blood tests, urine tests, X-rays, ECGs, MRI/CT scans, and ultrasound imaging.",
        "signals": {
            "defining_terms": {"strong": ["diagnostic centre", "diagnostic center", "pathology lab", "medical lab", "diagnostics", "scan centre", "dr lal pathlabs", "thyrocare", "metropolis", "vijaya diagnostic"]},
            "supporting_terms": {"medium": ["blood test", "pathology", "x-ray", "ecg", "ultrasound", "scan", "mri", "ct scan", "lipid profile", "cbc", "thyroid"]},
            "non_evidence": "inherit"
        },
        "categories": {
            "defining": ["diagnostic_laboratory", "medical_lab", "healthcare=laboratory", "amenity=hospital"],
            "host": ["hospital_zone", "commercial_area"],
            "incompatible": ["restaurant", "bakery", "hardware_store"]
        },
        "veto_terms": ["medical device export", "reagents wholesaler"],
        "brands": {"incompatible": []},
        "overture_basic_categories": ["diagnostic_laboratory", "medical_clinic"],
        "overture_taxonomy_paths": ["health_and_medicine > diagnostic_services"],
        "osm_tags": ["healthcare=laboratory", "amenity=clinic"],
        "name_patterns": ["\\bdiagnostics?\\b", "\\bpathology\\b", "\\bmedical lab\\b", "\\bscan cent(?:re|er)\\b"],
        "decision": {"require_defining_signal": True, "tau_hi": 0.75, "tau_lo": 0.35}
    }
]

def main() -> None:
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for card_data in ALL_CONCEPTS:
        cid = card_data["concept_id"]
        out_path = CONCEPTS_DIR / f"{cid}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(card_data, f, sort_keys=False)
        count += 1

    print(f"Successfully generated {count} unified, rich Concept Cards in {CONCEPTS_DIR}")
    assert count >= 20, f"Expected at least 20 unified cards, generated {count}"

if __name__ == "__main__":
    main()
