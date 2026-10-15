import asyncio
import logging
from rag.retrieval import get_qdrant_client, init_collections
from rag.pipelines import ingest_document, ask_question_pipeline

logging.basicConfig(level=logging.INFO)

async def main():
    doc_text = """
EMPLOYMENT CONTRACT
This Agreement is entered into on 1st January 2024 by LawShield AI Pvt Ltd (Employer) and Rohan Sharma (Employee).
1. Position: Senior Legal Counsel.
2. Termination Notice Period: Either party may terminate this agreement by providing 60 days prior written notice to the other party.
3. Remuneration: The Employer shall pay the Employee a fixed gross salary of INR 25,00,000 per annum, payable in equal monthly installments.
4. Non-Disclosure & Confidentiality: The Employee agrees not to disclose any confidential client files or proprietary AI source code for a period of 5 years following termination of employment.
"""
    meta = {"title": "employment_contract.txt", "filename": "employment_contract.txt"}

    print("Step 1: Ingesting document into vector database...")
    ingest_res = ingest_document(doc_text, meta)
    print("Ingest result:", ingest_res)

    print("\nStep 2: Asking grounded question about notice period...")
    query = "What is the notice period for termination in the employment contract?"
    ans = await ask_question_pipeline(query)

    print("\n================ FINAL RAG ANSWER ================")
    print(ans.get("answer"))
    print("\n================ CONTEXT CHUNKS USED ================")
    for i, c in enumerate(ans.get("context_used", []), 1):
        print(f"[{i}] {c}\n")

if __name__ == "__main__":
    asyncio.run(main())
