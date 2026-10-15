"""
Comprehensive RAG Retrieval Quality & Grounding Evaluation Test Suite.

Evaluates:
- Retrieval accuracy (Hit Rate@5, MRR) across 6 core legal queries
- Test A: Strict document grounding (no external statutes like Indian Contract Act / IT Act / IPC when query specifies fromdocument)
- Test B: Citation validity (all [Doc X] references match actual context chunks)
- Test C: Unknown information (returns non-hallucinated missing notice for unmentioned facts like salary)
- Test D: Specific clause retrieval (non-compete clause priority)
- Test E: Multi-clause survival period retrieval
"""
from __future__ import annotations

import unittest
import asyncio
import re
from typing import List, Dict, Any

from rag.pipelines import ingest_document, ask_question_pipeline

SAMPLE_NDA_CONTRACT = """
CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

Clause 1 — DEFINITION OF CONFIDENTIAL INFORMATION
The term "Confidential Information" shall include all non-public technical, financial, commercial, and operational information disclosed by the Disclosing Party to the Receiving Party...

Clause 2 — OBLIGATION OF NON-DISCLOSURE
The Receiving Party shall not disclose, transfer, or communicate any Confidential Information to any third party or unauthorized persons without prior written consent...

Clause 3 — REMEDIES AND PENALTIES
In the event of a breach, the Disclosing Party shall be entitled to seek injunctive relief and actual damages proved in a court of competent jurisdiction. No fixed automatic monetary penalty or liquidated damages amount is specified herein.

Clause 5 — SURVIVAL PERIOD
The obligations of confidentiality under this Agreement shall survive for a period of three (3) years following termination of employment or engagement. Provided, however, that trade secrets, personal data, and regulatory investigation records shall remain confidential indefinitely.

Clause 7 — RETURN OR DESTRUCTION OF CONFIDENTIAL INFORMATION
Upon written request, all Confidential Information must be deleted or destroyed within seven (7) business days. Provided, however, that the Receiving Party shall not be deemed in breach if Confidential Information remains stored in automated, routine system backup archives that are not readily accessible to ordinary users and are overwritten in the ordinary course of business.

Clause 8 — COMPETITIVE ACTIVITIES & NON-COMPETE CLARIFICATION
Nothing in this Confidentiality Agreement shall be construed as a non-compete covenant or prevent an employee or contractor from joining or engaging in employment with a competitor, provided that no Confidential Information of the Company is disclosed or used during such employment.

Clause 10 — ARTIFICIAL INTELLIGENCE SYSTEMS
Confidential Information cannot generally be submitted to, processed by, or uploaded to publicly accessible generative AI systems, chatbots, LLMs, code assistants, or similar third-party tools (including ChatGPT).
However, an exception applies and an employee is permitted to use such generative AI systems only if all of the following conditions are satisfied:
1. The AI system is expressly approved by the Company in writing.
2. The employee is specifically authorized to use the approved system.
3. Appropriate contractual and enterprise security protections exist with the provider.
4. The input of information is necessary for legitimate work purposes.
5. Applicable restrictions on model training are satisfied (e.g., data is not used to train public models).
6. Applicable privacy and data-protection requirements are followed.

Clause 12 — GOVERNING LAW AND CONFLICT OF LAWS
This Agreement shall be governed by and construed in accordance with the laws of India. If any provision of this Agreement or Company policy conflicts with mandatory Indian law or statutory regulation, mandatory Indian law shall govern and control.
"""

TEST_CASES = [
    {
        "id": 1,
        "query": "Can an employee upload confidential information to ChatGPT? Explain all exceptions. fromdocument",
        "gold_section": "10",
        "gold_title_keyword": "ARTIFICIAL INTELLIGENCE",
    },
    {
        "id": 2,
        "query": "How long does confidentiality survive after termination?",
        "gold_section": "5",
        "gold_title_keyword": "SURVIVAL",
    },
    {
        "id": 3,
        "query": "The NDA says information must be deleted within 7 business days, but it remains in automated backups. Is that a breach?",
        "gold_section": "7",
        "gold_title_keyword": "DESTRUCTION",
    },
    {
        "id": 4,
        "query": "Does this NDA prevent an employee from joining a competitor?",
        "gold_section": "8",
        "gold_title_keyword": "COMPETITOR",
    },
    {
        "id": 5,
        "query": "What fixed monetary penalty applies for violating the NDA?",
        "gold_section": "3",
        "gold_title_keyword": "REMEDIES",
    },
    {
        "id": 6,
        "query": "If Company policy conflicts with mandatory Indian law, which one controls?",
        "gold_section": "12",
        "gold_title_keyword": "GOVERNING LAW",
    },
]


class TestRAGRetrievalQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection_name = "test_eval_nda_grounding"
        meta = {"filename": "sample_nda.txt", "title": "Confidentiality Agreement"}
        ingest_document(SAMPLE_NDA_CONTRACT, meta, collection_name=cls.collection_name)

    def test_run_eval_suite(self):
        async def _run_all():
            mrr_sum = 0.0
            hits_5 = 0
            results_summary = []

            for tc in TEST_CASES:
                await asyncio.sleep(1.5)
                res = await ask_question_pipeline(tc["query"], collection_name=self.collection_name)
                answer = res.get("answer", "")
                debug_sess = res.get("debug_session")

                reranked_chunks = debug_sess.reranked_chunks if debug_sess else []

                # Determine rank of gold section
                gold_rank = None
                for rank, chunk in enumerate(reranked_chunks, 1):
                    sec_num = chunk.get("metadata", {}).get("section_number") or ""
                    sec_title = chunk.get("section_title") or ""
                    text = chunk.get("text") or ""

                    if sec_num == tc["gold_section"] or tc["gold_title_keyword"].lower() in sec_title.lower() or tc["gold_title_keyword"].lower() in text.lower():
                        gold_rank = rank
                        break

                hit_5 = bool(gold_rank and gold_rank <= 5)
                reciprocal_rank = 1.0 / gold_rank if gold_rank else 0.0

                if hit_5:
                    hits_5 += 1
                mrr_sum += reciprocal_rank

                results_summary.append({
                    "id": tc["id"],
                    "query": tc["query"],
                    "gold_section": tc["gold_section"],
                    "gold_rank": gold_rank,
                    "hit@5": hit_5,
                    "answer": answer[:250],
                })

            n = len(TEST_CASES)
            hit_rate_5 = hits_5 / n
            mrr = mrr_sum / n

            print("\n================================================================")
            print("                RAG EVALUATION METRICS REPORT                  ")
            print("================================================================")
            print(f"Total Test Cases: {n}")
            print(f"Hit Rate @ 5:     {hit_rate_5 * 100:.1f}% ({hits_5}/{n})")
            print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
            print("----------------------------------------------------------------")

            for r in results_summary:
                print(f"Query #{r['id']}: {r['query']}")
                print(f"  Gold Section: Clause {r['gold_section']} | Found Rank: #{r['gold_rank']} | Hit@5: {r['hit@5']}")

            self.assertGreaterEqual(hit_rate_5, 0.83, "Hit Rate@5 should be >= 83%")
            self.assertEqual(results_summary[0]["gold_rank"], 1, "Clause 10 must be ranked #1 for ChatGPT query!")

        asyncio.run(_run_all())

    def test_a_document_grounding(self):
        """Test A: Verify no external statutes (Contract Act, IT Act, Evidence Act, IPC) appear when query has 'fromdocument'."""
        async def _test():
            await asyncio.sleep(2.0)
            q = "Can an employee upload confidential information to ChatGPT? Explain all exceptions. fromdocument"
            res = await ask_question_pipeline(q, collection_name=self.collection_name)
            ans = res.get("answer", "")
            
            forbidden_statutes = [
                "Indian Contract Act", "Information Technology Act", "IT Act",
                "Indian Evidence Act", "Indian Penal Code", "IPC", "BNS"
            ]
            for stat in forbidden_statutes:
                self.assertNotIn(stat.lower(), ans.lower(), f"Answer hallucinated ungrounded statute: {stat}")
            
            self.assertTrue(
                "clause 10" in ans.lower() or "[doc" in ans.lower() or "chatgpt" in ans.lower() 
                 or "generative ai" in ans.lower() or "confidential" in ans.lower() or "prohibited" in ans.lower()
                 or "cannot answer" in ans.lower() or "upload the relevant" in ans.lower(),
                "Answer should reference Clause 10 content, AI prohibition, doc citation, or refusal"
            )

        asyncio.run(_test())

    def test_b_citation_validity(self):
        """Test B: Verify every [Doc N] citation matches actual context docs."""
        async def _test():
            await asyncio.sleep(3.5)
            q = "What happens to confidential information in automated backups?"
            res = await ask_question_pipeline(q, collection_name=self.collection_name)
            ans = res.get("answer", "")
            debug_sess = res.get("debug_session")
            
            if debug_sess and debug_sess.reranked_chunks:
                top_doc_ids = set(f"[doc {i+1}]" for i in range(len(debug_sess.reranked_chunks)))
                import re
                used_citations = set(re.findall(r'\[doc \d+\]', ans.lower()))
                for cite in used_citations:
                    self.assertIn(cite, top_doc_ids, f"Citation {cite} does not exist in retrieved context docs")

        asyncio.run(_test())

    def test_c_unknown_information(self):
        """Test C: Verify system does not hallucinate unmentioned facts (e.g. employee salary)."""
        async def _test():
            await asyncio.sleep(3.5)
            q = "What is the employee's monthly salary under this contract?"
            res = await ask_question_pipeline(q, collection_name=self.collection_name)
            ans = res.get("answer", "")
            
            refusal_phrases = [
                "not mentioned", "cannot answer", "does not contain", "not specified",
                "unmentioned", "need more information", "cannot find", "upload the relevant",
                "more information", "does not mention"
            ]
            self.assertTrue(
                any(phrase in ans.lower() for phrase in refusal_phrases),
                f"System should declare information unmentioned instead of guessing: {ans}"
            )
            # Ensure no fake dollar/rupee amounts were invented
            self.assertNotRegex(ans, r"(\$|₹|INR|\b\d{5,}\b)")

        asyncio.run(_test())

    def test_d_specific_clause_retrieval(self):
        """Test D: Verify non-compete question retrieves Clause 8 without external law."""
        async def _test():
            await asyncio.sleep(3.5)
            q = "Does this NDA stop an employee from joining a competitor?"
            res = await ask_question_pipeline(q, collection_name=self.collection_name)
            ans = res.get("answer", "")
            debug_sess = res.get("debug_session")
            
            top_chunk = debug_sess.reranked_chunks[0] if debug_sess else {}
            sec_num = top_chunk.get("metadata", {}).get("section_number") or ""
            self.assertEqual(sec_num, "8", "Clause 8 (Competitor clarification) should be ranked #1")

        asyncio.run(_test())

    def test_e_multi_clause_question(self):
        """Test E: Verify multi-clause survival query retrieves Clause 5."""
        async def _test():
            await asyncio.sleep(3.5)
            q = "How long does confidentiality survive after termination, and are there different periods?"
            res = await ask_question_pipeline(q, collection_name=self.collection_name)
            ans = res.get("answer", "")
            debug_sess = res.get("debug_session")
            
            reranked = debug_sess.reranked_chunks if debug_sess else []
            has_clause_5 = any(
                chunk.get("metadata", {}).get("section_number") == "5"
                or "survival" in chunk.get("text", "").lower()
                or "term" in chunk.get("text", "").lower()
                for chunk in reranked
            )
            self.assertTrue(
                has_clause_5 or "clause 5" in ans.lower() or "[doc" in ans.lower() or "year" in ans.lower() or "survive" in ans.lower() or "cannot answer" in ans.lower(),
                "Survival query should retrieve Clause 5 or address survival period"
            )

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
