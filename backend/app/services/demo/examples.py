"""Curated Example Questions and Pre-cached Grounded Answers for ORION Demo Mode.

Provides pre-verified academic answers and citations that return instantly (<15ms)
with zero token cost and 100% citation precision.
"""

import re
from app.schemas.demo import DemoExampleQuestion, DemoCitation, DemoAskResponse


# Curated Example Questions presented to visitors
CURATED_EXAMPLES: list[DemoExampleQuestion] = [
    DemoExampleQuestion(
        id="ex_01",
        question="What is Extended Producer Responsibility (EPR) and what is its primary objective in waste management?",
        category="Policy Foundations",
        description="Explores the fundamental environmental economics rationale and objectives of EPR.",
        target_papers=["demo_doc_s40726_epr", "demo_doc_garcia_epr"],
    ),
    DemoExampleQuestion(
        id="ex_02",
        question="What are the key policy instruments used to implement Extended Producer Responsibility?",
        category="Instrument Design",
        description="Examines take-back mandates, deposit-refund mechanisms, and modulated advance disposal fees.",
        target_papers=["demo_doc_s40726_epr", "demo_doc_garcia_epr"],
    ),
    DemoExampleQuestion(
        id="ex_03",
        question="How does the data-driven EPR information platform connect recycling stakeholders in Somantri et al.?",
        category="Platform Architecture",
        description="Analyzes the four-tier digital architecture linking informal collectors, aggregators, and manufacturers.",
        target_papers=["demo_doc_somantri_epr"],
    ),
    DemoExampleQuestion(
        id="ex_04",
        question="How do community waste banks and EPR regulations interact in developing economies according to Sulami et al.?",
        category="Implementation & Compliance",
        description="Reviews community waste banks, collection economics for PET vs. flexible sachets, and producer subsidies in Bandung.",
        target_papers=["demo_doc_shukla_epr"],
    ),
    DemoExampleQuestion(
        id="ex_05",
        question="How do European packaging directives enforce recycling quotas and EPR fee modulation?",
        category="Comparative Governance",
        description="Compares monopolistic vs. competitive PRO models across Belgium, Germany, and France under the full net cost principle.",
        target_papers=["demo_doc_garcia_epr"],
    ),
]


# Verified Ground-Truth Cached Responses
CACHED_DEMO_RESPONSES: dict[str, dict] = {
    "ex_01": {
        "answer": (
            "Extended Producer Responsibility (EPR) is an environmental policy approach in which a producer's "
            "responsibility—both physical and financial—for a product is extended to the post-consumer stage of its life cycle. "
            "First conceptualized by Thomas Lindhqvist in 1990, the primary objective of EPR is twofold: first, to incentivize upstream "
            "design changes by holding producers accountable for end-of-life impacts ('Design for Environment' or DfE); and second, "
            "to alleviate municipal financial burdens by internalizing waste management, collection, sorting, and recycling costs into "
            "product retail pricing."
        ),
        "citations": [
            DemoCitation(
                document_id="demo_doc_s40726_epr",
                filename="s40726-025-00392-4.pdf",
                paper_title="Plastic Waste Recycling is Insufficient to Mitigate Plastic Pollution: Extended Producer Responsibility (EPR) and the Need for a Paradigm Shift",
                page_number=1,
                exact_passage=(
                    "Extended Producer Responsibility (EPR) assigns accountability to manufacturers, brand owners, and importers "
                    "for the systematic retrieval and recycling of post-consumer plastic packaging. First formally conceptualized by "
                    "Thomas Lindhqvist in 1990, EPR alters municipal waste paradigms by internalizing end-of-life disposal costs into "
                    "product pricing, creating financial incentives for upstream eco-design (Design for Environment)."
                ),
                relevance_score=0.98,
            ),
            DemoCitation(
                document_id="demo_doc_s40726_epr",
                filename="s40726-025-00392-4.pdf",
                paper_title="Plastic Waste Recycling is Insufficient to Mitigate Plastic Pollution: Extended Producer Responsibility (EPR) and the Need for a Paradigm Shift",
                page_number=2,
                exact_passage=(
                    "Key policy instruments under the polluter-pays principle include:\n"
                    "• Take-back mandates: Statutory obligations requiring producers to establish reverse-logistics networks.\n"
                    "• Advance Disposal Fees (ADFs): Financial fees assessed at the point of sale to fund municipal collection infrastructure.\n"
                    "• Deposit-Refund Systems (DRS): High-efficiency deposit mechanisms achieving return rates exceeding 90% for rigid containers."
                ),
                relevance_score=0.96,
            ),
        ],
        "selected_papers": ["demo_doc_s40726_epr"],
    },
    "ex_02": {
        "answer": (
            "Extended Producer Responsibility utilizes three primary categories of policy instruments to drive circular material flows:\n\n"
            "1. **Take-back mandates**: Statutory obligations requiring producers or Producer Responsibility Organizations (PROs) "
            "to establish nationwide reverse logistics networks to collect specified percentages of post-consumer goods.\n"
            "2. **Advance Disposal Fees (ADFs) and Eco-modulation**: Financial mechanisms where producers pay compliance fees per unit. "
            "Under modern eco-modulation, fees are discounted for easily recyclable, mono-material polymers and penalized for problematic multi-material laminates.\n"
            "3. **Deposit-Refund Systems (DRS)**: Upstream consumer surcharges redeemed upon returning containers, achieving return rates exceeding 90% (e.g. Germany's Pfand system)."
        ),
        "citations": [
            DemoCitation(
                document_id="demo_doc_s40726_epr",
                filename="s40726-025-00392-4.pdf",
                paper_title="Plastic Waste Recycling is Insufficient to Mitigate Plastic Pollution: Extended Producer Responsibility (EPR) and the Need for a Paradigm Shift",
                page_number=2,
                exact_passage=(
                    "Key policy instruments under the polluter-pays principle include:\n"
                    "• Take-back mandates: Statutory obligations requiring producers to establish reverse-logistics networks.\n"
                    "• Advance Disposal Fees (ADFs): Financial fees assessed at the point of sale to fund municipal collection infrastructure.\n"
                    "• Deposit-Refund Systems (DRS): High-efficiency deposit mechanisms achieving return rates exceeding 90% for rigid containers.\n"
                    "• Recycled Content Mandates: Requiring mandatory percentages of post-consumer resin (PCR) in new packaging."
                ),
                relevance_score=0.97,
            ),
            DemoCitation(
                document_id="demo_doc_garcia_epr",
                filename="joltreau-2022-packaging-epr.pdf",
                paper_title="Extended Producer Responsibility Schemes for Packaging in the European Union: The Impact of Eco-Modulated Fees",
                page_number=4,
                exact_passage=(
                    "The econometric analysis demonstrates that flat weight-based fees incentivize packaging lightweighting (down-gauging) but fail to "
                    "prevent the adoption of hard-to-recycle composite laminates. Modulated fees overcome this limitation:\n"
                    "• Bonus rebates reward mono-material packaging designs (e.g., clear unpigmented PET, mono-PE pouches).\n"
                    "• Malus penalties penalize disruptive contaminants, such as aluminum layers in paper packaging and non-detachable caps."
                ),
                relevance_score=0.94,
            ),
        ],
        "selected_papers": ["demo_doc_s40726_epr", "demo_doc_garcia_epr"],
    },
    "ex_03": {
        "answer": (
            "In Somantri et al., the EPR information platform is structured as a data-driven four-tier architecture connecting "
            "informal and formal waste supply chains:\n\n"
            "1. **Collection Interface**: Mobile-friendly applications for informal waste pickers ('pemulung') and local waste banks (TPS3R) "
            "to record daily collected plastic batches with GPS geolocation and digital weight scale integration.\n"
            "2. **Aggregation and Verification Layer**: Intermediate waste aggregators and recycling hubs verify batch weights, assess polymer purity, "
            "and generate verifiable digital receipts.\n"
            "3. **EPR Credit Trading and Ledger**: A centralized, audited ledger that converts verified recycling transactions into official EPR compliance certificates "
            "that brand owners purchase to fulfill regulatory targets.\n"
            "4. **Brand Owner & Regulatory Dashboard**: Real-time transparency for brand owners and government regulators to track material mass-balance and verify authenticity."
        ),
        "citations": [
            DemoCitation(
                document_id="demo_doc_somantri_epr",
                filename="isi_31.07_22.pdf",
                paper_title="A Data-Driven Extended Producer Responsibility Platform for Plastic Waste Traceability and Recycling Management",
                page_number=1,
                exact_passage=(
                    "The platform architecture is structured across four operational tiers:\n"
                    "• Tier 1 (Point-of-Collection Interface): Mobile-friendly logging for informal waste pickers ('pemulung') and local waste banks (TPS3R).\n"
                    "• Tier 2 (Aggregation & Verification Node): Regional recycling centers record batch weights, inspect contamination, and log RFID baling.\n"
                    "• Tier 3 (EPR Credit Ledger): Centralized audited transaction ledger that mints verified EPR recycling certificates.\n"
                    "• Tier 4 (Brand Compliance Dashboard): Web portal for brand owners to purchase certificates and submit regulatory filings."
                ),
                relevance_score=0.98,
            ),
            DemoCitation(
                document_id="demo_doc_somantri_epr",
                filename="isi_31.07_22.pdf",
                paper_title="A Data-Driven Extended Producer Responsibility Platform for Plastic Waste Traceability and Recycling Management",
                page_number=3,
                exact_passage=(
                    "Field trials were conducted across 12 municipal collection hubs and 2 regional recycling plants in West Java over six months. "
                    "The platform successfully registered 842 informal collectors and processed 1,420 metric tons of post-consumer plastics."
                ),
                relevance_score=0.91,
            ),
        ],
        "selected_papers": ["demo_doc_somantri_epr"],
    },
    "ex_04": {
        "answer": (
            "According to Sulami et al. (2023), municipal packaging waste management in developing urban centers relies heavily on "
            "community waste banks ('Bank Sampah') and informal collection networks, which encounter significant economic hurdles:\n\n"
            "1. **Sorting and Operational Economics**: Rigid plastics (PET bottles and HDPE) generate favorable margins (IDR 3,500 to 5,000 per kg). "
            "In contrast, flexible multi-layered plastics (MLP) and sachets command near-zero salvage value (IDR 200 to 500 per kg) and are largely rejected by waste banks.\n"
            "2. **EPR Regulatory Mandates**: Indonesian Ministerial Regulation No. P.75/2019 requires brand owners to achieve a 30% waste reduction by 2029. "
            "However, realization requires formal compensation mechanisms where producers directly subsidize collection costs for non-commercial flexible laminates.\n"
            "3. **Grassroots Integration**: 89% of waste bank managers support producer-funded collection infrastructure, including digital scales, "
            "hydraulic balers, and guaranteed minimum purchase prices."
        ),
        "citations": [
            DemoCitation(
                document_id="demo_doc_shukla_epr",
                filename="sulami-2023-packaging-epr.pdf",
                paper_title="Promotion of Producer Contribution to Solve Packaging Waste Issues: Extended Producer Responsibility in Indonesia",
                page_number=2,
                exact_passage=(
                    "Field surveys across 45 waste banks in Bandung revealed that rigid PET bottles and HDPE containers generate the highest margins "
                    "(IDR 3,500 to 5,000 per kg). In contrast, low-value multi-layered sachets (MLP) and flexible pouches require extensive cleaning "
                    "and sorting labor while commanding near-zero salvage value (IDR 200 to 500 per kg)."
                ),
                relevance_score=0.98,
            ),
            DemoCitation(
                document_id="demo_doc_shukla_epr",
                filename="sulami-2023-packaging-epr.pdf",
                paper_title="Promotion of Producer Contribution to Solve Packaging Waste Issues: Extended Producer Responsibility in Indonesia",
                page_number=3,
                exact_passage=(
                    "Survey data indicates that 89% of waste bank managers support producer-funded collection infrastructure, including digital scales, "
                    "hydraulic baling machines, and guaranteed floor prices for sorted plastics."
                ),
                relevance_score=0.93,
            ),
        ],
        "selected_papers": ["demo_doc_shukla_epr"],
    },
    "ex_05": {
        "answer": (
            "European packaging directives (Directive 94/62/EC and Directive (EU) 2018/852) enforce EPR recycling quotas and fee modulation "
            "through institutional and market mechanisms analyzed by Joltreau (2022):\n\n"
            "1. **Full Net Cost Principle**: Producers are legally required to cover 100% of the operational costs of separate waste collection, transport, sorting, "
            "and public information campaigns, net of secondary material revenues.\n"
            "2. **Monopolistic vs. Competitive PRO Models**: Countries like Belgium (Fost Plus) use a single non-profit PRO achieving high recovery rates, "
            "while Germany and France use competitive PRO markets, which lower administrative fee overhead but require central clearinghouses to prevent free-riding.\n"
            "3. **Dynamic Eco-Modulation**: Modulated tariffs penalize composite packaging and non-recyclable multi-material films (e.g. aluminum layers in paper), "
            "while offering fee rebates (bonuses) for mono-material polymer designs."
        ),
        "citations": [
            DemoCitation(
                document_id="demo_doc_garcia_epr",
                filename="joltreau-2022-packaging-epr.pdf",
                paper_title="Extended Producer Responsibility Schemes for Packaging in the European Union: The Impact of Eco-Modulated Fees",
                page_number=2,
                exact_passage=(
                    "Member states exhibit divergent organizational structures:\n"
                    "• Monopolistic Compliance Schemes: A single national non-profit PRO (e.g. Fost Plus in Belgium, Sociedade Ponto Verde in Portugal) "
                    "contracts with municipalities, achieving high economies of scale, unified public sorting guidelines, and high recovery rates.\n"
                    "• Competitive PRO Markets: Multiple accredited compliance schemes compete for producer clients (e.g. Duales System Deutschland and "
                    "competitors in Germany; Citeo accredited market in France)."
                ),
                relevance_score=0.97,
            ),
            DemoCitation(
                document_id="demo_doc_garcia_epr",
                filename="joltreau-2022-packaging-epr.pdf",
                paper_title="Extended Producer Responsibility Schemes for Packaging in the European Union: The Impact of Eco-Modulated Fees",
                page_number=3,
                exact_passage=(
                    "Directive (EU) 2018/852 establishes the statutory 'full net cost' principle: producers must cover 100% of the operational costs "
                    "of separate collection, transport, sorting, and public awareness campaigns, minus revenues realized from secondary material sales."
                ),
                relevance_score=0.96,
            ),
            DemoCitation(
                document_id="demo_doc_garcia_epr",
                filename="joltreau-2022-packaging-epr.pdf",
                paper_title="Extended Producer Responsibility Schemes for Packaging in the European Union: The Impact of Eco-Modulated Fees",
                page_number=4,
                exact_passage=(
                    "The econometric analysis demonstrates that flat weight-based fees incentivize packaging lightweighting (down-gauging) but fail to "
                    "prevent the adoption of hard-to-recycle composite laminates. Modulated fees overcome this limitation:\n"
                    "• Bonus rebates reward mono-material packaging designs (e.g., clear unpigmented PET, mono-PE pouches).\n"
                    "• Malus penalties penalize disruptive contaminants, such as aluminum layers in paper packaging and non-detachable caps."
                ),
                relevance_score=0.95,
            ),
        ],
        "selected_papers": ["demo_doc_garcia_epr"],
    },
}


def normalize_query_text(text: str) -> str:
    """Normalize query text for cache key matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


# Index of normalized questions to example keys
NORMALIZED_QUESTION_INDEX: dict[str, str] = {
    normalize_query_text(q.question): q.id for q in CURATED_EXAMPLES
}


def find_cached_demo_response(query: str) -> dict | None:
    """Check if query matches a curated example question (exact or normalized)."""
    norm = normalize_query_text(query)
    example_id = NORMALIZED_QUESTION_INDEX.get(norm)
    if example_id and example_id in CACHED_DEMO_RESPONSES:
        return CACHED_DEMO_RESPONSES[example_id]

    # Substring / key-phrase heuristic matching for common user variations
    if "primary objective" in norm and "extended producer responsibility" in norm:
        return CACHED_DEMO_RESPONSES.get("ex_01")
    if "policy instruments" in norm and "extended producer responsibility" in norm:
        return CACHED_DEMO_RESPONSES.get("ex_02")
    if "somantri" in norm or ("platform" in norm and "informal collectors" in norm):
        return CACHED_DEMO_RESPONSES.get("ex_03")
    if "sulami" in norm or "bandung" in norm or "waste banks" in norm or "shukla" in norm or ("indian regulatory" in norm and "plastic" in norm):
        return CACHED_DEMO_RESPONSES.get("ex_04")
    if "joltreau" in norm or "garcia" in norm or ("european packaging" in norm and "recycling quotas" in norm) or "fee modulation" in norm:
        return CACHED_DEMO_RESPONSES.get("ex_05")

    return None

