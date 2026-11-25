# Product Requirements Document (PRD) - LawShield

## 1. Goal & Product Vision
The goal of **LawShield** is to provide an intuitive, high-fidelity legal tech platform that caters to both **general users** (who need simple, plain-English guidance) and **lawyers/legal professionals** (who require precise, source-grounded research, document auditing, and drafting toolsets).

---

## 2. Core Feature Pillars (Non-Overlapping)
To eliminate feature overlap and user confusion, the system is structured into four distinct functional pillars:

| Pillar | Functionality | Primary Audience | Scope & Boundary |
| :--- | :--- | :--- | :--- |
| **1. AI Consultation** | Multi-turn conversational Q&A focused on answering legal queries, clarifying legal concepts, or researching case law. | General Users & Lawyers | Purely conversational. Does not require a pre-uploaded document. |
| **2. Document Auditing** | Upload a contract, policy, or brief to run risk checklists and regulatory compliance checks. | Lawyers & Corporate | Upload-driven. Analyzes existing documents for errors, missing clauses, or compliance violations. |
| **3. Automated Drafting** | A step-by-step generator that creates structured legal notices, contracts, or replies from templates. | General Users & Lawyers | Form-driven/Guided. Produces a brand-new, fully formatted legal draft from scratch. |
| **4. Legal Calculator** | Precise calculations of statutory limits, filing deadlines, capital gains, interest, or damages. | Lawyers | Tool-driven. Focuses strictly on numerical limits, interest, and calendar deadlines. |

---

## 3. Clean UX/UI Strategy

### A. Persona-Based Workspace Switcher
Allow users to self-select their role upon entry to customize the interface:
* **Client / General Mode**: Displays simplified terminology, hides complex confidence metrics, and focuses on plain-English explanations.
* **Lawyer / Pro Mode**: Unlocks raw citations, enables deeper multi-agent reasoning, shows confidence/grounding scores, and displays legal risk audit summaries.

### B. Segmented Navigation
Separate workflows in the navigation menu so users always know their current context:
```
[ lawShield ]
├── 💬 AI Consultation  ──► (Clean, conversational chat)
├── 🔍 Document Auditor ──► (Upload zone + side-by-side risk checklist)
├── ✍️ Draft Builder    ──► (Form wizards for Lease, NDA, Notice)
└── 🧮 Legal Calculator  ──► (Interactive calculator inputs)
```

### C. Interface Guidelines

#### 1. Document Auditor Layout (Interactive Split-Screen)
* **Left Pane**: Document Viewer showing the uploaded contract/notice with highlighted sections.
* **Right Pane**: Audit Checklist showing **Risks (Red)**, **Warnings (Yellow)**, and **Passed Elements (Green)**.
* **Interactivity**: Clicking any item in the right pane highlights the corresponding text section in the left pane.

#### 2. AI Consultation Layout (Clean Chat with Lazy Citations)
* Maintain a minimalistic chat screen.
* Keep replies clean and jargon-light by default.
* Embed citations inside an accordion wrapper (e.g., `[+] View Citations`) so pro users can expand them to view references while general users see a clean layout.

#### 3. Automated Drafting Layout (Wizard Forms)
* Replace raw-prompt drafting with structured forms.
* Provide fields for crucial details (e.g., Landlord Name, Tenant Name, Rent Amount, Location).
* Generate final formatted drafts (`.docx`/`.pdf`) using verified legal templates.
