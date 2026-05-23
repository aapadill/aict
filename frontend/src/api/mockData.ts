import type {
  AnalysisResult,
  Case,
  ChatMessage,
  Citation,
  DocumentRecord,
} from "../types/api";

const now = () => new Date().toISOString();

export const mockCases: Case[] = [
  {
    id: "case-demo-1",
    title: "GenAI loan application triage assistant",
    description:
      "LLM-based assistant that ingests loan applications, summarizes them, and produces a preliminary eligibility recommendation for loan officers at a retail bank.",
    created_at: now(),
    updated_at: now(),
  },
  {
    id: "case-demo-2",
    title: "AI-assisted radiology pre-read",
    description:
      "Computer-vision model that flags suspicious findings on chest X-rays for a radiologist's review in a hospital network.",
    created_at: now(),
    updated_at: now(),
  },
];

export const mockDocuments: Record<string, DocumentRecord[]> = {
  "case-demo-1": [
    {
      id: "doc-1",
      case_id: "case-demo-1",
      filename: "vendor_whitepaper.pdf",
      content_type: "application/pdf",
      status: "parsed",
      created_at: now(),
    },
    {
      id: "doc-2",
      case_id: "case-demo-1",
      filename: "internal_process_notes.md",
      content_type: "text/markdown",
      status: "parsed",
      created_at: now(),
    },
    {
      id: "doc-3",
      case_id: "case-demo-1",
      filename: "model_card.pdf",
      content_type: "application/pdf",
      status: "parsed",
      created_at: now(),
    },
  ],
};

const citationLeg = (id: string, title: string, location: string, snippet: string): Citation => ({
  id,
  source_type: "legislation",
  source_title: title,
  location,
  snippet,
});

const citationDoc = (
  id: string,
  title: string,
  location: string,
  snippet: string,
  documentId = "doc-1",
): Citation => ({
  id,
  source_type: "uploaded_document",
  source_title: title,
  location,
  snippet,
  document_id: documentId,
});

export const mockAnalysis = (caseId: string): AnalysisResult => ({
  case_id: caseId,
  summary:
    "A retail bank plans to deploy a generative-AI assistant, built on a third-party foundation model, that reads incoming consumer loan applications together with supporting documents, produces a structured summary, and outputs a preliminary creditworthiness recommendation (approve / review / decline) shown to a human loan officer who makes the final decision. The assistant is integrated into the bank's existing loan-origination workflow and is not exposed directly to applicants.",
  extracted_facts: [
    {
      id: "f1",
      label: "Intended purpose",
      value:
        "Summarize consumer loan applications and recommend a preliminary creditworthiness decision to a loan officer.",
      status: "found",
      citations: [
        citationDoc(
          "c-d1",
          "vendor_whitepaper.pdf",
          "p.3",
          "The assistant produces a recommendation of APPROVE / REVIEW / DECLINE alongside a natural-language rationale.",
        ),
      ],
    },
    {
      id: "f2",
      label: "Underlying technology",
      value:
        "Built on a third-party general-purpose foundation model, fine-tuned on the bank's historical lending decisions.",
      status: "found",
      citations: [
        citationDoc(
          "c-d2",
          "model_card.pdf",
          "§2",
          "Base model: vendor GPAI model v4. Fine-tuned on ~120k historical applications and outcomes from 2018-2023.",
          "doc-3",
        ),
      ],
    },
    {
      id: "f3",
      label: "Role in decision",
      value:
        "Loan officer reviews the recommendation; the officer signs the final decision in the loan-origination system.",
      status: "found",
      citations: [
        citationDoc(
          "c-d3",
          "internal_process_notes.md",
          "§Workflow",
          "Officers must confirm or override the recommendation before the case advances.",
          "doc-2",
        ),
      ],
    },
    {
      id: "f4",
      label: "Deployer and provider roles",
      value:
        "The bank operates the system in its own workflow (deployer). The vendor supplies the fine-tuned model and APIs (provider).",
      status: "uncertain",
      citations: [
        citationDoc(
          "c-d4",
          "vendor_whitepaper.pdf",
          "p.7",
          "Vendor retains responsibility for model updates; bank controls integration and configuration.",
        ),
      ],
    },
    {
      id: "f5",
      label: "Applicant-facing disclosure",
      value:
        "Not described — unclear whether applicants are informed that an AI system contributes to the decision.",
      status: "missing",
      citations: [],
    },
    {
      id: "f6",
      label: "Training-data governance",
      value:
        "Documents mention historical applications but do not describe bias testing, demographic balance, or data-quality controls.",
      status: "missing",
      citations: [],
    },
  ],
  ai_system_assessment: {
    title: "AI system qualification (Art. 3(1))",
    conclusion:
      "Clearly qualifies as an AI system under the EU AI Act.",
    confidence: "high",
    reasoning:
      "The assistant is a machine-based system that, from loan-application inputs, infers a recommendation that influences a decision affecting a natural person. This matches the Art. 3(1) definition of an AI system, and the underlying foundation model further confirms the qualification.",
    citations: [
      citationLeg(
        "c-l1",
        "Regulation (EU) 2024/1689",
        "Art. 3(1)",
        "'AI system' means a machine-based system designed to operate with varying levels of autonomy ... that infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions ...",
      ),
    ],
    assumptions: [
      "The vendor's foundation model is genuinely ML-based, as described in the model card.",
    ],
    uncertainties: [
      "The exact degree of autonomy at inference time is described only at a high level.",
    ],
  },
  risk_classification: {
    title: "Preliminary risk classification",
    conclusion:
      "High-risk under Annex III §5(b): AI systems intended to evaluate the creditworthiness of natural persons or establish their credit score.",
    confidence: "high",
    reasoning:
      "The assistant is explicitly used to evaluate the creditworthiness of consumer loan applicants. Annex III §5(b) lists such systems as high-risk, with limited carve-outs (e.g. detection of financial fraud) that do not apply here. The fact that a human officer signs off does not remove the high-risk classification; it informs the human-oversight obligation under Art. 14.",
    citations: [
      citationLeg(
        "c-l2",
        "Regulation (EU) 2024/1689",
        "Annex III §5(b)",
        "AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score, with the exception of AI systems used for the purpose of detecting financial fraud.",
      ),
    ],
    assumptions: [
      "The applicants are natural persons (consumer lending), not legal entities.",
    ],
    uncertainties: [
      "If the system were re-scoped to fraud detection only, Annex III §5(b) would not apply.",
    ],
  },
  obligations: [
    {
      title: "Risk management system (Art. 9)",
      conclusion:
        "The provider must establish, document, and maintain a continuous risk-management process across the system's lifecycle; the deployer must feed operational signals back into it.",
      confidence: "high",
      reasoning:
        "Art. 9 imposes a lifecycle risk-management obligation on providers of high-risk AI systems. The deployer's monitoring data is part of that loop.",
      citations: [
        citationLeg(
          "c-l3",
          "Regulation (EU) 2024/1689",
          "Art. 9",
          "A risk management system shall be established, implemented, documented and maintained in relation to high-risk AI systems ...",
        ),
      ],
      assumptions: [],
      uncertainties: [],
    },
    {
      title: "Data and data governance (Art. 10)",
      conclusion:
        "Training, validation, and test data must meet quality criteria, including relevance, representativeness, and examination for bias affecting protected groups.",
      confidence: "high",
      reasoning:
        "Historical lending data is known to encode demographic and geographic bias. Art. 10 requires explicit data-governance practices for high-risk systems, especially where the output affects natural persons.",
      citations: [
        citationLeg(
          "c-l4",
          "Regulation (EU) 2024/1689",
          "Art. 10",
          "Training, validation and testing data sets shall be subject to data governance and management practices appropriate for the intended purpose ...",
        ),
      ],
      assumptions: [],
      uncertainties: [
        "No bias-testing documentation was uploaded; this may exist but is not visible to the assessment.",
      ],
    },
    {
      title: "Human oversight (Art. 14)",
      conclusion:
        "The system must be designed so that loan officers can understand the recommendation, are not over-reliant on it, and can effectively override or disregard it.",
      confidence: "medium",
      reasoning:
        "The described 'officer confirms or overrides' workflow is consistent with Art. 14, but oversight effectiveness depends on UI design, training, and whether overrides are meaningfully exercised — automation bias is a known failure mode in credit decisioning.",
      citations: [
        citationLeg(
          "c-l5",
          "Regulation (EU) 2024/1689",
          "Art. 14",
          "High-risk AI systems shall be designed and developed ... such that they can be effectively overseen by natural persons during the period in which they are in use ...",
        ),
      ],
      assumptions: [
        "Loan officers receive task-specific training and have authority to override.",
      ],
      uncertainties: [
        "Override rates and the UI presentation of the recommendation are not described.",
      ],
    },
    {
      title: "Transparency to affected persons (Art. 26(11) deployer duty)",
      conclusion:
        "As a deployer using a high-risk AI system to make decisions concerning natural persons, the bank must inform applicants that they are subject to the use of such a system.",
      confidence: "high",
      reasoning:
        "Art. 26(11) requires deployers of high-risk AI systems referred to in Annex III to inform the natural persons concerned. This is independent of the GDPR information duties.",
      citations: [
        citationLeg(
          "c-l6",
          "Regulation (EU) 2024/1689",
          "Art. 26(11)",
          "Deployers of high-risk AI systems referred to in Annex III that make decisions or assist in making decisions related to natural persons shall inform the natural persons that they are subject to the use of the high-risk AI system.",
        ),
      ],
      assumptions: [],
      uncertainties: [
        "Current applicant-facing communications were not provided; disclosure may already exist.",
      ],
    },
    {
      title: "Fundamental Rights Impact Assessment (Art. 27)",
      conclusion:
        "As a deployer that is a body governed by public law or a private operator providing public services — and specifically for Annex III §5(b) creditworthiness systems — the bank must perform a FRIA before first use.",
      confidence: "high",
      reasoning:
        "Art. 27 expressly extends the FRIA obligation to deployers using Annex III §5(b) systems, regardless of whether they are public-sector entities.",
      citations: [
        citationLeg(
          "c-l7",
          "Regulation (EU) 2024/1689",
          "Art. 27",
          "Prior to deploying a high-risk AI system referred to in Article 6(2) ... deployers that are bodies governed by public law, or are private entities providing public services, and deployers of high-risk AI systems referred to in points 5(b) and 5(c) of Annex III, shall perform an assessment of the impact on fundamental rights ...",
        ),
      ],
      assumptions: [],
      uncertainties: [],
    },
    {
      title: "GPAI obligations on the upstream foundation model (Art. 53)",
      conclusion:
        "The vendor, as provider of the underlying general-purpose AI model, must supply technical documentation and information enabling downstream integrators to comply.",
      confidence: "medium",
      reasoning:
        "Art. 53 places documentation and information-sharing obligations on GPAI providers. The bank, as downstream deployer/integrator, should obtain and retain this information for its own conformity work.",
      citations: [
        citationLeg(
          "c-l8",
          "Regulation (EU) 2024/1689",
          "Art. 53",
          "Providers of general-purpose AI models shall ... draw up and keep up-to-date the technical documentation of the model ... make information and documentation available to providers of AI systems who intend to integrate the general-purpose AI model into their AI systems ...",
        ),
      ],
      assumptions: [
        "The base model qualifies as a general-purpose AI model.",
      ],
      uncertainties: [
        "Whether the model meets the systemic-risk threshold under Art. 51 is not stated.",
      ],
    },
  ],
  governance_observations: [
    {
      title: "Logging and post-market monitoring",
      conclusion:
        "Automatic logging of recommendations, officer overrides, and outcomes should be designed in from day one to satisfy Art. 12 and Art. 72.",
      confidence: "medium",
      reasoning:
        "High-risk systems must produce logs enabling traceability, and providers must run a post-market monitoring system. The deployer's logs feed both.",
      citations: [
        citationLeg(
          "c-l9",
          "Regulation (EU) 2024/1689",
          "Art. 12",
          "High-risk AI systems shall technically allow for the automatic recording of events (logs) ...",
        ),
      ],
      assumptions: [],
      uncertainties: [
        "No logging architecture was described in the uploads.",
      ],
    },
    {
      title: "Role allocation between bank and vendor",
      conclusion:
        "The provider/deployer split must be formalized contractually; under Art. 25 the bank could be reclassified as provider if it substantially modifies the system or puts it on the market under its own name.",
      confidence: "medium",
      reasoning:
        "Art. 25 reallocates provider obligations to downstream actors that substantially modify a high-risk system. Fine-tuning scope and branding decisions therefore have legal consequences.",
      citations: [
        citationLeg(
          "c-l10",
          "Regulation (EU) 2024/1689",
          "Art. 25",
          "Any distributor, importer, deployer or other third party shall be considered to be a provider of a high-risk AI system ... and shall be subject to the obligations of the provider ... in any of the following circumstances ...",
        ),
      ],
      assumptions: [],
      uncertainties: [
        "Whether the fine-tuning amounts to a 'substantial modification' is not assessed.",
      ],
    },
  ],
  missing_information: [
    "Whether applicants are informed that an AI system contributes to the decision (Art. 26(11)).",
    "Bias and fairness evaluation of the fine-tuning dataset across protected groups (Art. 10).",
    "Concrete human-oversight design: what information the officer sees, override rate, training program (Art. 14).",
    "Logging architecture and retention policy (Art. 12).",
    "Whether the bank rebrands or substantially modifies the vendor model (Art. 25).",
    "Whether a Fundamental Rights Impact Assessment has been performed (Art. 27).",
  ],
  follow_up_questions: [
    "Is the assistant's recommendation shown as a binary label, a probability, or free-text rationale?",
    "Has the vendor provided the Art. 53 technical documentation for the underlying GPAI model?",
    "What is the current applicant-facing privacy and AI disclosure language?",
    "Are officer overrides tracked and reviewed for automation bias?",
    "Is the system intended only for consumer loans, or also for SME / corporate lending?",
  ],
  citations: [
    citationLeg("c-l1", "Regulation (EU) 2024/1689", "Art. 3(1)", "'AI system' means a machine-based system ..."),
    citationLeg("c-l2", "Regulation (EU) 2024/1689", "Annex III §5(b)", "AI systems intended to be used to evaluate the creditworthiness of natural persons ..."),
    citationLeg("c-l5", "Regulation (EU) 2024/1689", "Art. 14", "High-risk AI systems shall be designed and developed ... such that they can be effectively overseen by natural persons ..."),
    citationLeg("c-l6", "Regulation (EU) 2024/1689", "Art. 26(11)", "Deployers ... shall inform the natural persons that they are subject to the use of the high-risk AI system."),
    citationLeg("c-l7", "Regulation (EU) 2024/1689", "Art. 27", "... deployers of high-risk AI systems referred to in points 5(b) and 5(c) of Annex III, shall perform an assessment of the impact on fundamental rights ..."),
    citationDoc("c-d1", "vendor_whitepaper.pdf", "p.3", "The assistant produces a recommendation of APPROVE / REVIEW / DECLINE ..."),
    citationDoc("c-d2", "model_card.pdf", "§2", "Base model: vendor GPAI model v4 ...", "doc-3"),
  ],
  agent_trace: [
    {
      agent: "IntakeAgent",
      action: "synthesize_case",
      output_summary:
        "Merged 3 documents into a single case description; identified vendor/bank split and consumer-lending scope.",
    },
    {
      agent: "FactExtractionAgent",
      action: "extract_facts",
      output_summary:
        "Extracted 6 facts; flagged applicant disclosure and training-data governance as missing.",
    },
    {
      agent: "RetrievalAgent",
      action: "retrieve_ai_act",
      output_summary:
        "Pulled passages from Art. 3, 9, 10, 12, 14, 25, 26, 27, 53 and Annex III §5(b).",
    },
    {
      agent: "ClassifierAgent",
      action: "classify_risk",
      output_summary:
        "Mapped use case to Annex III §5(b) (creditworthiness) — high-risk.",
    },
    {
      agent: "ObligationsAgent",
      action: "derive_obligations",
      output_summary:
        "Selected obligations: risk management, data governance, human oversight, transparency to affected persons, FRIA, GPAI documentation.",
    },
    {
      agent: "ReviewerAgent",
      action: "flag_gaps_and_uncertainties",
      output_summary:
        "Surfaced 6 missing-information items and 5 follow-up questions for the user.",
    },
  ],
  limitation_notice:
    "This is an automated decision-support draft based only on the uploaded documents and the built-in EU AI Act corpus. It is not legal advice and does not cover GDPR, national implementations of the AI Act, or sector-specific financial-services rules (e.g. CRD/CCD) except where flagged.",
});

export const mockMessages: Record<string, ChatMessage[]> = {};
