"""Generates the versioned evaluation benchmark dataset for ORION."""

import json
from pathlib import Path
from app.evaluation.schema import BenchmarkDataset, BenchmarkSample, GroundTruthEvidence, QuestionCategory

DATASET_VERSION = "1.0.0"

SAMPLES: list[BenchmarkSample] = [
    # ==========================================
    # CATEGORY 1: DIRECT FACTUAL QUESTIONS
    # ==========================================
    BenchmarkSample(
        id="fact_01",
        category=QuestionCategory.DIRECT_FACTUAL,
        question="What was the total volume of plastic production in India reported for 2018-19 in Emami et al.?",
        selected_filenames=["Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["19.3 Mt", "19.3", "production"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="The analysis reveals a total plastic production of 19.3 Mt, 22% of which is Polyethylene as the most wildly used plastic.",
                key_entities_or_numbers=["19.3 Mt", "22%", "Polyethylene"],
            )
        ],
        notes_and_limitations="Direct factual extraction from Abstract on page 1.",
    ),
    BenchmarkSample(
        id="fact_02",
        category=QuestionCategory.DIRECT_FACTUAL,
        question="What is the title and primary modeling framework proposed in Yamamoto et al. (Zhang et al.)?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["dynamic probabilistic material flow analysis", "DPMFA"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="This work presents a dynamic probabilistic material flow analysis (DPMFA) model for assessing plastic flows across all life-cycle stages, with high granularity at the end-of-life stage.",
                key_entities_or_numbers=["dynamic probabilistic material flow analysis", "DPMFA"],
            )
        ],
    ),
    BenchmarkSample(
        id="fact_03",
        category=QuestionCategory.DIRECT_FACTUAL,
        question="In Somantri et al., which country was the data-driven Extended Producer Responsibility (EPR) platform developed for?",
        selected_filenames=["Somantri.pdf"],
        should_abstain=False,
        expected_key_facts=["Indonesia"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="The platform was developed based on sales and purchase data collected from recycling stakeholders in Indonesia and was designed to connect producers, collectors, recyclers, verifiers, and administrators through a unified information system.",
                key_entities_or_numbers=["Indonesia", "producers", "collectors", "recyclers"],
            )
        ],
    ),
    BenchmarkSample(
        id="fact_04",
        category=QuestionCategory.DIRECT_FACTUAL,
        question="According to Rita Garcia et al., what was the contribution of recycled materials in reducing virgin material use (recycled input rate) in Portugal?",
        selected_filenames=["Rita Garcia.pdf"],
        should_abstain=False,
        expected_key_facts=["11%", "11 percent", "recycled input rate"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Rita Garcia.pdf",
                document_id="doc_93be921e-1977-4d0e-9f78-7f10377a8fc5",
                page_number=1,
                exact_passage="The recycled input rate indicates an 11 % contribution of recycled materials in reducing the use of virgin materials.",
                key_entities_or_numbers=["11 %", "recycled input rate"],
            )
        ],
    ),
    BenchmarkSample(
        id="fact_05",
        category=QuestionCategory.DIRECT_FACTUAL,
        question="Who are the first authors and corresponding author of the 2025 review on plastic pollution in Current Pollution Reports?",
        selected_filenames=["Saurabh Shukla.pdf"],
        should_abstain=False,
        expected_key_facts=["Saurabh Shukla", "Ramsha Khan", "Paolo Roccaro"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=1,
                exact_passage="Saurabh Shukla and Ramsha Khan share first authorship. Paolo Roccaro paolo.roccaro@unict.it",
                key_entities_or_numbers=["Saurabh Shukla", "Ramsha Khan", "Paolo Roccaro"],
            )
        ],
    ),

    # ==========================================
    # CATEGORY 2: QUESTIONS REQUIRING MULTIPLE PASSAGES
    # ==========================================
    BenchmarkSample(
        id="multi_01",
        category=QuestionCategory.MULTI_PASSAGE,
        question="In Emami et al., compare India's plastic consumption growth with its population growth between 1990 and 2019, and explain their data harmonisation method to address data gaps.",
        selected_filenames=["Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["20-fold", "60%", "data pedigree matrix", "harmonisation"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=2,
                exact_passage="Between 1990 and 2019, India's consumption of plastics grew 20-fold [3], while its population increased by 60% over the same period [4].",
                key_entities_or_numbers=["20-fold", "60%"],
            ),
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=3,
                exact_passage="We take a systematic data harmonisation approach and use a data pedigree matrix to score the reliability and validity of existing datasets.",
                key_entities_or_numbers=["systematic data harmonisation", "data pedigree matrix"],
            ),
        ],
    ),
    BenchmarkSample(
        id="multi_02",
        category=QuestionCategory.MULTI_PASSAGE,
        question="In Somantri et al., explain the development lifecycle of the platform and the outcomes of both functional testing and usability evaluation.",
        selected_filenames=["Somantri.pdf"],
        should_abstain=False,
        expected_key_facts=["SDLC", "functional evaluation", "reliability", "usability", "stakeholders"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=3,
                exact_passage="software development life cycle (SDLC), enabling rapid iteration and responsiveness to changing needs. Development activities include interface and back-end programming, database integration, and feature adjustments.",
                key_entities_or_numbers=["software development life cycle", "SDLC"],
            ),
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="Functional evaluation confirmed the reliability of the system components, while usability assessment indicated strong acceptance among stakeholders.",
                key_entities_or_numbers=["Functional evaluation", "reliability", "usability assessment"],
            ),
        ],
    ),
    BenchmarkSample(
        id="multi_03",
        category=QuestionCategory.MULTI_PASSAGE,
        question="In Yamamoto et al., what proportion of mechanical recycling inflows in Japan comes from post-consumer waste, which sector dominates this inflow, and how are secondary materials commonly downcycled?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["70%", "77%", "packaging", "downcycled", "agricultural plastics to flooring"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="In 2023, post-consumer waste accounts for 70% of mechanical recycling inflows, with 77% originating from the packaging sector.",
                key_entities_or_numbers=["70%", "77%", "packaging"],
            ),
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="existing evidence shows that recycled plastics are often downcycled to lower-quality applications or transferred to different sectors, such as the conversion of agricultural plastics to flooring.",
                key_entities_or_numbers=["downcycled", "agricultural plastics to flooring"],
            ),
        ],
    ),
    BenchmarkSample(
        id="multi_04",
        category=QuestionCategory.MULTI_PASSAGE,
        question="In Shukla et al., what are the major environmental drawbacks of incineration, and why does mixed plastic recycling pose difficulties for depolymerization?",
        selected_filenames=["Saurabh Shukla.pdf"],
        should_abstain=False,
        expected_key_facts=["incineration", "toxic gases", "carbon emissions", "depolymerization", "mixed plastic", "incompatibility"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=4,
                exact_passage="Incineration of plastic waste is a form of waste to energy conversion with degrading impacts on the environment through release of toxic gases on combustion [16].",
                key_entities_or_numbers=["toxic gases on combustion", "incineration"],
            ),
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=5,
                exact_passage="The varying chemical reactivity of plastics and their possible interaction with additives can complicate the depolymerization process in chemical recycling. Thus, recycling of mixed waste plastics is a major challenge for conventional recycling.",
                key_entities_or_numbers=["varying chemical reactivity", "depolymerization", "mixed waste plastics"],
            ),
        ],
    ),
    BenchmarkSample(
        id="multi_05",
        category=QuestionCategory.MULTI_PASSAGE,
        question="In Mariana Gonçalves et al., what are the stages of the proposed MFA framework and what reference unit is used for measuring plastic packaging flows?",
        selected_filenames=["Mariana Gonçalves.pdf"],
        should_abstain=False,
        expected_key_facts=["static MFA model", "circularity indicators", "tonne", "t"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Mariana Gonçalves.pdf",
                document_id="doc_6b57efca-6092-4dfa-bbaa-6313853ef93d",
                page_number=3,
                exact_passage="The implementation of the first stage results in a static MFA model, which serves as the basis for calculating the circularity indicators in Stage 2.",
                key_entities_or_numbers=["static MFA model", "circularity indicators"],
            ),
            GroundTruthEvidence(
                filename="Mariana Gonçalves.pdf",
                document_id="doc_6b57efca-6092-4dfa-bbaa-6313853ef93d",
                page_number=4,
                exact_passage="The reference unit used for the model is tonne of plastics (t), commonly used in MFAs for plastic.",
                key_entities_or_numbers=["tonne of plastics", "t"],
            ),
        ],
    ),

    # ==========================================
    # CATEGORY 3: CROSS-PAPER SYNTHESIS & COMPARISON
    # ==========================================
    BenchmarkSample(
        id="cross_01",
        category=QuestionCategory.CROSS_PAPER_SYNTHESIS,
        question="Compare the temporal and methodological modeling approaches of Emami et al. for India with Yamamoto et al. for Japan.",
        selected_filenames=["Emami.pdf", "Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["India", "2018-19", "static", "Japan", "dynamic probabilistic", "DPMFA", "1990-2023"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="This work presents a 20-year update, detailing plastic production, consumption by all plastic types and sectors, and the overall material flow for 2018-19 to fill the gap in the data on post-consumer plastic flows.",
                key_entities_or_numbers=["2018-19", "India", "20-year update"],
            ),
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="The model is parameterized for eight types of plastic polymers in Japan between 1990 and 2023, including 47 product categories, 17 waste collection pathways, and 10 sorting systems.",
                key_entities_or_numbers=["Japan", "1990 and 2023", "dynamic probabilistic", "eight types of plastic polymers"],
            ),
        ],
    ),
    BenchmarkSample(
        id="cross_02",
        category=QuestionCategory.CROSS_PAPER_SYNTHESIS,
        question="Synthesize how Somantri et al. and Shukla et al. analyze the role of data transparency and Extended Producer Responsibility in developing countries.",
        selected_filenames=["Somantri.pdf", "Saurabh Shukla.pdf"],
        should_abstain=False,
        expected_key_facts=["traceability", "transactional records", "EPR", "developing countries", "informal"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="Plastic waste management remains a critical challenge in developing countries due to fragmented recycling systems, limited traceability, and insufficient integration of material-flow information. This study proposes a data-driven extended producer responsibility (EPR) platform.",
                key_entities_or_numbers=["developing countries", "fragmented recycling systems", "traceability", "EPR"],
            ),
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=1,
                exact_passage="Consequently, the world is witnessing a proliferation of proposed solutions to manage plastic waste... This review seeks to elucidate the underlying causes and limitations of current strategies that fail to adequately address the global plastic waste crisis.",
                key_entities_or_numbers=["proliferation of proposed solutions", "limitations of current strategies"],
            ),
        ],
    ),
    BenchmarkSample(
        id="cross_03",
        category=QuestionCategory.CROSS_PAPER_SYNTHESIS,
        question="Compare the focus on packaging plastics between Rita Garcia et al. in Portugal and Yamamoto et al. in Japan.",
        selected_filenames=["Rita Garcia.pdf", "Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["Portugal", "plastic packaging", "11%", "Japan", "77%", "packaging sector"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Rita Garcia.pdf",
                document_id="doc_93be921e-1977-4d0e-9f78-7f10377a8fc5",
                page_number=1,
                exact_passage="This article proposes an MFA-based approach to assess circularity and presents an application to plastic packaging in Portugal... Results show that plastic packaging has a low circularity due to short lifespans and low recycling rates.",
                key_entities_or_numbers=["plastic packaging in Portugal", "low circularity"],
            ),
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="In 2023, post-consumer waste accounts for 70% of mechanical recycling inflows, with 77% originating from the packaging sector.",
                key_entities_or_numbers=["77%", "packaging sector", "Japan"],
            ),
        ],
    ),
    BenchmarkSample(
        id="cross_04",
        category=QuestionCategory.CROSS_PAPER_SYNTHESIS,
        question="How do Emami et al. and Somantri et al. characterize the challenges of informal plastic waste recovery in Asian emerging economies?",
        selected_filenames=["Emami.pdf", "Somantri.pdf"],
        should_abstain=False,
        expected_key_facts=["informal", "data scarcity", "fragmented recycling", "traceability", "India", "Indonesia"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=4,
                exact_passage="We re-iterate the difficulty of obtaining primary data in this field of research. We acknowledge the best efforts and empathise greatly with the abovementioned authors, but there is also a need to acknowledge the provenance, limits and age of data sources.",
                key_entities_or_numbers=["difficulty of obtaining primary data", "India"],
            ),
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="Plastic waste management remains a critical challenge in developing countries due to fragmented recycling systems, limited traceability, and insufficient integration of material-flow information.",
                key_entities_or_numbers=["fragmented recycling systems", "limited traceability", "Indonesia"],
            ),
        ],
    ),
    BenchmarkSample(
        id="cross_05",
        category=QuestionCategory.CROSS_PAPER_SYNTHESIS,
        question="Synthesize the environmental impacts of plastic waste mismanagement reported across Shukla et al. and Emami et al.",
        selected_filenames=["Saurabh Shukla.pdf", "Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["microplastics", "contaminants", "mismanaged plastic waste", "leaching", "incineration"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=4,
                exact_passage="Plastic waste in landfills is an image of unemployed economic potential, with risks of contaminant leaching into the vicinity. Incineration of plastic waste is a form of waste to energy conversion with degrading impacts on the environment.",
                key_entities_or_numbers=["contaminant leaching", "incineration"],
            ),
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="Plastic is valued for its flexibility to be utilized in different applications, yet it poses a significant threat to our environment because of mismanaged plastic waste.",
                key_entities_or_numbers=["significant threat to our environment", "mismanaged plastic waste"],
            ),
        ],
    ),

    # ==========================================
    # CATEGORY 4: RESEARCH GAPS AND LIMITATIONS
    # ==========================================
    BenchmarkSample(
        id="gap_01",
        category=QuestionCategory.RESEARCH_GAPS,
        question="What explicit data limitation regarding secondary material tracking does Yamamoto et al. acknowledge?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["secondary material use", "downcycled", "data limitations"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="While data limitations prevent explicit modeling of secondary material use, existing evidence shows that recycled plastics are often downcycled to lower-quality applications or transferred to different sectors.",
                key_entities_or_numbers=["data limitations", "explicit modeling of secondary material use"],
            )
        ],
    ),
    BenchmarkSample(
        id="gap_02",
        category=QuestionCategory.RESEARCH_GAPS,
        question="What primary data collection difficulties and historical research gaps in India does Emami et al. highlight?",
        selected_filenames=["Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["no comprehensive study since 2000", "difficulty of obtaining primary data", "gap in data on post-consumer"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="Despite this significant growth, there has not been a comprehensive study of Indian plastic flows since 2000. This work presents a 20-year update, detailing plastic production, consumption by all plastic types and sectors, and the overall material flow for 2018-19 to fill the gap in the data on post-consumer plastic flows.",
                key_entities_or_numbers=["since 2000", "gap in the data on post-consumer plastic flows"],
            ),
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=4,
                exact_passage="We re-iterate the difficulty of obtaining primary data in this field of research.",
                key_entities_or_numbers=["difficulty of obtaining primary data"],
            ),
        ],
    ),
    BenchmarkSample(
        id="gap_03",
        category=QuestionCategory.RESEARCH_GAPS,
        question="What limitations in conventional chemical recycling and depolymerization does Shukla et al. state?",
        selected_filenames=["Saurabh Shukla.pdf"],
        should_abstain=False,
        expected_key_facts=["chemical reactivity", "additives", "mixed waste plastics", "depolymerization"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=5,
                exact_passage="The varying chemical reactivity of plastics and their possible interaction with additives can complicate the depolymerization process in chemical recycling. The presence of multiple reactive species can lead to side reactions hampering the progress separation of target molecule. Thus, recycling of mixed waste plastics is a major challenge for conventional recycling.",
                key_entities_or_numbers=["side reactions", "mixed waste plastics", "additives"],
            )
        ],
    ),
    BenchmarkSample(
        id="gap_04",
        category=QuestionCategory.RESEARCH_GAPS,
        question="What limitations in Material Flow Analysis for evaluating plastic circularity are discussed by Rita Garcia et al.?",
        selected_filenames=["Rita Garcia.pdf"],
        should_abstain=False,
        expected_key_facts=["short lifespans", "low recycling rates", "limitations in providing a comprehensive assessment"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Rita Garcia.pdf",
                document_id="doc_93be921e-1977-4d0e-9f78-7f10377a8fc5",
                page_number=1,
                exact_passage="Material flow analysis (MFA) has been used to investigate plastic flows, albeit with limitations in providing a comprehensive assessment... Results show that plastic packaging has a low circularity due to short lifespans and low recycling rates.",
                key_entities_or_numbers=["limitations in providing a comprehensive assessment", "low circularity"],
            )
        ],
    ),
    BenchmarkSample(
        id="gap_05",
        category=QuestionCategory.RESEARCH_GAPS,
        question="In Somantri et al., what data gaps and system challenges in developing country recycling systems did the study seek to close?",
        selected_filenames=["Somantri.pdf"],
        should_abstain=False,
        expected_key_facts=["fragmented recycling systems", "limited traceability", "insufficient integration of material-flow information"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="Plastic waste management remains a critical challenge in developing countries due to fragmented recycling systems, limited traceability, and insufficient integration of material-flow information.",
                key_entities_or_numbers=["fragmented recycling systems", "limited traceability"],
            )
        ],
    ),

    # ==========================================
    # CATEGORY 5: NUMERICAL FACTS
    # ==========================================
    BenchmarkSample(
        id="num_01",
        category=QuestionCategory.NUMERICAL_FACTS,
        question="What was the total mass of plastic in products distributed in various applications in India in 2018-19 according to Emami et al.?",
        selected_filenames=["Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["23.9 Mt", "23.9"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="The total mass of plastic in products distributed in various applications is 23.9 Mt.",
                key_entities_or_numbers=["23.9 Mt"],
            )
        ],
    ),
    BenchmarkSample(
        id="num_02",
        category=QuestionCategory.NUMERICAL_FACTS,
        question="In Somantri et al., what were the total weights recorded in purchase transactions and supply transactions in kg during 2024?",
        selected_filenames=["Somantri.pdf"],
        should_abstain=False,
        expected_key_facts=["27,028,801 kg", "4,896,392 kg", "27028801", "4896392"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                page_number=1,
                exact_passage="nine categories recorded in purchase transactions totaling 27,028,801 kg and seven categories recorded in supply transactions totaling 4,896,392 kg.",
                key_entities_or_numbers=["27,028,801 kg", "4,896,392 kg"],
            )
        ],
    ),
    BenchmarkSample(
        id="num_03",
        category=QuestionCategory.NUMERICAL_FACTS,
        question="In Yamamoto et al., how many product categories, waste collection pathways, and sorting systems were parameterized in the Japan DPMFA model?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],
        should_abstain=False,
        expected_key_facts=["47 product categories", "17 waste collection pathways", "10 sorting systems"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Haruhisa Yamamoto.pdf",
                document_id="doc_9283731d-f59e-4b71-a87e-806a71c3b68d",
                page_number=1,
                exact_passage="including 47 product categories, 17 waste collection pathways, and 10 sorting systems.",
                key_entities_or_numbers=["47 product categories", "17 waste collection pathways", "10 sorting systems"],
            )
        ],
    ),
    BenchmarkSample(
        id="num_04",
        category=QuestionCategory.NUMERICAL_FACTS,
        question="What was India's compound annual growth rate of plastic consumption over the decade analyzed by Emami et al.?",
        selected_filenames=["Emami.pdf"],
        should_abstain=False,
        expected_key_facts=["7%", "7 percent"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Emami.pdf",
                document_id="doc_99072719-82e4-4c9a-97c8-5db7417bc7d3",
                page_number=1,
                exact_passage="India's compound annual growth of plastic consumption has been around 7% for a decade.",
                key_entities_or_numbers=["7%"],
            )
        ],
    ),
    BenchmarkSample(
        id="num_05",
        category=QuestionCategory.NUMERICAL_FACTS,
        question="In Shukla et al., what plastic particle concentration did Carpenter and Smith (1972) confirm in the Sargasso Sea?",
        selected_filenames=["Saurabh Shukla.pdf"],
        should_abstain=False,
        expected_key_facts=["290 g/km2", "0.25 and 0.5 cm"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                page_number=3,
                exact_passage="Carpenter and Smith [5], in their study on plastic particles in Sargasso Sea using neuston surface nets, confirmed plastic concentrations up to 290 g/km2 with a diameter between 0.25 and 0.5 cm.",
                key_entities_or_numbers=["290 g/km2", "0.25 and 0.5 cm"],
            )
        ],
    ),

    # ==========================================
    # CATEGORY 6: UNANSWERABLE QUESTIONS REQUIRING ABSTENTION
    # ==========================================
    BenchmarkSample(
        id="abstain_01",
        category=QuestionCategory.UNANSWERABLE_ABSTENTION,
        question="What is the computational complexity of self-attention per layer in the Transformer architecture?",
        selected_filenames=["Emami.pdf", "Somantri.pdf", "Haruhisa Yamamoto.pdf", "Rita Garcia.pdf", "Saurabh Shukla.pdf"],
        should_abstain=True,
        expected_abstention_reason="The provided documents do not contain evidence about Transformer self-attention complexity.",
        ground_truth_evidence=[],
    ),
    BenchmarkSample(
        id="abstain_02",
        category=QuestionCategory.UNANSWERABLE_ABSTENTION,
        question="What audit records or investigative findings prove fraudulent plastic recycling credit generation and cartel collusion among recyclers in Indonesia?",
        selected_filenames=["Somantri.pdf", "isi_31.07_22.pdf"],
        should_abstain=True,
        expected_abstention_reason="The papers contain no audits, findings, or allegations of fraudulent credits or collusion.",
        ground_truth_evidence=[],
    ),
    BenchmarkSample(
        id="abstain_03",
        category=QuestionCategory.UNANSWERABLE_ABSTENTION,
        question="What are the phase transitions and superconducting critical temperatures of cuprate ceramics under high pressure in these papers?",
        selected_filenames=["Emami.pdf", "Mariana Gonçalves.pdf"],
        should_abstain=True,
        expected_abstention_reason="Superconductivity and high pressure physics are completely absent from the indexed environmental research documents.",
        ground_truth_evidence=[],
    ),
    BenchmarkSample(
        id="abstain_04",
        category=QuestionCategory.UNANSWERABLE_ABSTENTION,
        question="What are the specific parameters, deadlines, and milestones defining the project's frozen research scope?",
        selected_filenames=["Emami.pdf", "Somantri.pdf", "Haruhisa Yamamoto.pdf", "Saurabh Shukla.pdf"],
        should_abstain=True,
        expected_abstention_reason="External project frozen scope is not defined or mentioned in any academic publication.",
        ground_truth_evidence=[],
    ),
    BenchmarkSample(
        id="abstain_05",
        category=QuestionCategory.UNANSWERABLE_ABSTENTION,
        question="How many metric tons of microplastics were emitted into the mesosphere by commercial satellite constellations in 2023?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],
        should_abstain=True,
        expected_abstention_reason="Satellite mesospheric microplastic emissions are not investigated in the selected literature.",
        ground_truth_evidence=[],
    ),

    # ==========================================
    # CATEGORY 7: QUESTIONS WHERE SELECTED-DOCUMENT RESTRICTIONS MATTER
    # ==========================================
    BenchmarkSample(
        id="restrict_01",
        category=QuestionCategory.SOURCE_RESTRICTION,
        question="What is the recycled input rate for plastic packaging in Portugal?",
        selected_filenames=["Emami.pdf"],  # Restricted to Emami (which is only about India!)
        should_abstain=True,
        expected_abstention_reason="Emami.pdf focuses exclusively on India and contains no data on Portugal's packaging circularity.",
        ground_truth_evidence=[],
        notes_and_limitations="Source restriction test: although the answer exists in Rita Garcia.pdf, the user selected ONLY Emami.pdf.",
    ),
    BenchmarkSample(
        id="restrict_02",
        category=QuestionCategory.SOURCE_RESTRICTION,
        question="What are the parameters of the Dynamic Probabilistic Material Flow Analysis (DPMFA) model for Japan?",
        selected_filenames=["Somantri.pdf"],  # Restricted to Somantri (which is about Indonesia!)
        should_abstain=True,
        expected_abstention_reason="Somantri.pdf focuses on an Indonesian EPR software platform and does not contain the Japan DPMFA model.",
        ground_truth_evidence=[],
        notes_and_limitations="Source restriction test: Yamamoto.pdf contains the answer, but user selected ONLY Somantri.pdf.",
    ),
    BenchmarkSample(
        id="restrict_03",
        category=QuestionCategory.SOURCE_RESTRICTION,
        question="What was India's total plastic production in 2018-19 according to the selected literature?",
        selected_filenames=["Haruhisa Yamamoto.pdf"],  # Restricted to Yamamoto (which is only about Japan!)
        should_abstain=True,
        expected_abstention_reason="Yamamoto et al. parameterizes plastic flows in Japan and contains no national production figures for India.",
        ground_truth_evidence=[],
    ),
    BenchmarkSample(
        id="restrict_04",
        category=QuestionCategory.SOURCE_RESTRICTION,
        question="What were the purchase transaction weights recorded in the 2024 Indonesian EPR platform?",
        selected_filenames=["Rita Garcia.pdf"],  # Restricted to Rita Garcia (Portugal!)
        should_abstain=True,
        expected_abstention_reason="Rita Garcia.pdf investigates packaging in Portugal and has no data on Indonesian EPR transactions.",
        ground_truth_evidence=[],
    ),

    # ==========================================
    # CATEGORY 8: DUPLICATE AND OVERLAPPING EVIDENCE
    # ==========================================
    BenchmarkSample(
        id="dup_01",
        category=QuestionCategory.DUPLICATE_OVERLAPPING,
        question="Synthesize the transaction recording and verification framework across Somantri.pdf and isi_31.07_22.pdf, explaining their relationship.",
        selected_filenames=["Somantri.pdf", "isi_31.07_22.pdf"],
        should_abstain=False,
        expected_key_facts=["duplicate", "SHA-256", "Indonesia", "EPR", "27,028,801 kg"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Somantri.pdf",
                document_id="doc_636b4805-8c5f-4dd3-a3e4-78411b912c5b",
                content_hash="8dea11b505e5c4aa3473ef867b6d553981053f092c7f7c25a33f6e918a387cac",
                page_number=1,
                exact_passage="This study proposes a data-driven extended producer responsibility (EPR) platform that integrates transactional records, verification mechanisms, and monitoring functions to improve transparency and accountability in plastic waste recycling.",
                key_entities_or_numbers=["extended producer responsibility", "transactional records"],
            ),
            GroundTruthEvidence(
                filename="isi_31.07_22.pdf",
                document_id="doc_fa8f9d86-a161-4f70-b7c1-4962ee5f5825",
                content_hash="8dea11b505e5c4aa3473ef867b6d553981053f092c7f7c25a33f6e918a387cac",
                page_number=1,
                exact_passage="This study proposes a data-driven extended producer responsibility (EPR) platform that integrates transactional records, verification mechanisms, and monitoring functions to improve transparency and accountability in plastic waste recycling.",
                key_entities_or_numbers=["extended producer responsibility", "transactional records"],
            ),
        ],
        notes_and_limitations="Evaluates duplicate detection: both files share hash 8dea11b5... and must not be counted as independent corroboration.",
    ),
    BenchmarkSample(
        id="dup_02",
        category=QuestionCategory.DUPLICATE_OVERLAPPING,
        question="Examine the review of plastic waste challenges across Saurabh Shukla.pdf and s40726-025-00392-4.pdf, identifying if they provide independent corroboration.",
        selected_filenames=["Saurabh Shukla.pdf", "s40726-025-00392-4.pdf"],
        should_abstain=False,
        expected_key_facts=["duplicate", "SHA-256", "Current Pollution Reports", "depolymerization", "06b98b81"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Saurabh Shukla.pdf",
                document_id="doc_311c7a69-2c19-482b-a37d-caacea637a17",
                content_hash="06b98b8167417af023fda7fa20541a7053a7c2978db1e256387465764b5dbb6d",
                page_number=1,
                exact_passage="This review seeks to elucidate the underlying causes and limitations of current strategies that fail to adequately address the global plastic waste crisis.",
                key_entities_or_numbers=["global plastic waste crisis"],
            ),
            GroundTruthEvidence(
                filename="s40726-025-00392-4.pdf",
                document_id="doc_95c685a5-cd3b-4b2e-abb6-2aa61bf7b3f7",
                content_hash="06b98b8167417af023fda7fa20541a7053a7c2978db1e256387465764b5dbb6d",
                page_number=1,
                exact_passage="This review seeks to elucidate the underlying causes and limitations of current strategies that fail to adequately address the global plastic waste crisis.",
                key_entities_or_numbers=["global plastic waste crisis"],
            ),
        ],
        notes_and_limitations="Evaluates duplicate detection: both files share hash 06b98b81... and must be synthesized as a single evidentiary source.",
    ),
    BenchmarkSample(
        id="dup_03",
        category=QuestionCategory.DUPLICATE_OVERLAPPING,
        question="Compare the findings in Rita Garcia.pdf and Mariana Gonçalves.pdf regarding plastic packaging circularity indicators in Portugal.",
        selected_filenames=["Rita Garcia.pdf", "Mariana Gonçalves.pdf"],
        should_abstain=False,
        expected_key_facts=["Portugal", "MFA", "packaging", "circularity indicators"],
        ground_truth_evidence=[
            GroundTruthEvidence(
                filename="Rita Garcia.pdf",
                document_id="doc_93be921e-1977-4d0e-9f78-7f10377a8fc5",
                page_number=1,
                exact_passage="This article proposes an MFA-based approach to assess circularity and presents an application to plastic packaging in Portugal",
                key_entities_or_numbers=["MFA-based approach", "plastic packaging in Portugal"],
            ),
            GroundTruthEvidence(
                filename="Mariana Gonçalves.pdf",
                document_id="doc_6b57efca-6092-4dfa-bbaa-6313853ef93d",
                page_number=3,
                exact_passage="The implementation of the first stage results in a static MFA model, which serves as the basis for calculating the circularity indicators in Stage 2.",
                key_entities_or_numbers=["static MFA model", "circularity indicators"],
            ),
        ],
        notes_and_limitations="Overlapping authorship and topic (Mariana Gonçalves and Rita Garcia co-authored both publications).",
    ),
]


def build_and_save_dataset(output_path: str = "backend/app/evaluation/datasets/v1_academic_lit_benchmark.json") -> BenchmarkDataset:
    dataset = BenchmarkDataset(
        version=DATASET_VERSION,
        description="Ground-truth RAG evaluation benchmark for academic research synthesis in ORION.",
        target_corpus=[
            "Emami.pdf",
            "Somantri.pdf",
            "isi_31.07_22.pdf",
            "Haruhisa Yamamoto.pdf",
            "Rita Garcia.pdf",
            "Mariana Gonçalves.pdf",
            "Saurabh Shukla.pdf",
            "s40726-025-00392-4.pdf",
        ],
        samples=SAMPLES,
    )
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return dataset


if __name__ == "__main__":
    ds = build_and_save_dataset()
    print(f"Successfully generated benchmark dataset v{ds.version} with {len(ds.samples)} samples.")
