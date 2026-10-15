import asyncio
import logging
from rag.pipelines import ingest_document, ask_question_pipeline
from rag.retrieval import get_qdrant_client

logging.basicConfig(level=logging.INFO)

SAMPLE_NDA_CONTRACT = """
CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

Clause 1 — DEFINITION OF CONFIDENTIAL INFORMATION
The term "Confidential Information" shall include all non-public technical, financial, commercial, and operational information disclosed by the Disclosing Party to the Receiving Party...

Clause 2 — OBLIGATION OF NON-DISCLOSURE
The Receiving Party shall not disclose, transfer, or communicate any Confidential Information to any third party or unauthorized persons without prior written consent...

Clause 10 — ARTIFICIAL INTELLIGENCE SYSTEMS
Confidential Information cannot generally be submitted to, processed by, or uploaded to publicly accessible generative AI systems, chatbots, LLMs, code assistants, or similar third-party tools (including ChatGPT).
However, an exception applies and an employee is permitted to use such generative AI systems only if all of the following conditions are satisfied:
1. The AI system is expressly approved by the Company in writing.
2. The employee is specifically authorized to use the approved system.
3. Appropriate contractual and enterprise security protections exist with the provider.
4. The input of information is necessary for legitimate work purposes.
5. Applicable restrictions on model training are satisfied (e.g., data is not used to train public models).
6. Applicable privacy and data-protection requirements are followed.
"""

async def run_trace():
    print("=== Step 1: Ingesting Document ===")
    collection = "debug_trace_coll"
    meta = {"title": "sample_nda.txt", "filename": "sample_nda.txt"}
    ingest_res = ingest_document(SAMPLE_NDA_CONTRACT, meta, collection_name=collection)
    print("Ingest result:", ingest_res)

    print("\n=== Step 2: Directly Querying Vector Store for Clause 10 ===")
    q_client = get_qdrant_client()
    pts = q_client.scroll(collection_name=collection, limit=100)[0]
    print(f"Total stored points: {len(pts)}")
    clause_10_found = False
    for p in pts:
        txt = p.payload.get("text", "")
        if "ARTIFICIAL INTELLIGENCE" in txt or "ChatGPT" in txt:
            clause_10_found = True
            print("\n[STORED CHUNK MATCH]:")
            print("  Point ID:", p.id)
            print("  Section Title:", p.payload.get("metadata", {}).get("section_title"))
            print("  Section Number:", p.payload.get("metadata", {}).get("section_number"))
            print("  Text Snippet:", txt[:200].replace("\n", " "))

    print("\n=== Step 3: Running Pipeline End-to-End ===")
    query = "Can an employee upload confidential information to ChatGPT? Explain all exceptions."
    res = await ask_question_pipeline(query, collection_name=collection)
    
    debug_sess = res.get("debug_session")
    if debug_sess:
        print("\n" + debug_sess.format_text_report())
    
    print("\n=== FINAL PIPELINE RESULT ===")
    print("Answer:", res.get("answer"))

if __name__ == "__main__":
    asyncio.run(run_trace())
