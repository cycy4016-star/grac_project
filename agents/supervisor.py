import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from agents.base_agent import BaseAgent
from config.settings import settings


class SupervisorAgent(BaseAgent):
    """
    Supervisor Agent - Orchestrates the entire GRaC system.

    Receives requests, routes to specialist agents in the correct order,
    aggregates results, and returns the final output.
    """

    def __init__(self, sector: Optional[str] = None):
        """Initialize supervisor and register all specialist agents."""
        super().__init__("SupervisorAgent", sector)
        self.agent_registry = {}
        self._register_all_agents()
        self._query_cache: Dict[str, Any] = {}

    def _register_all_agents(self) -> None:
        """Register all specialist agents needed by the workflows."""
        from agents.retriever import RetrieverAgent
        from agents.analyzer import AnalyzerAgent
        from agents.writer import WriterAgent
        from agents.scorer import ScorerAgent
        from agents.transcriber import TranscriberAgent
        from agents.web_researcher import WebResearchAgent

        for name, agent in [
            ("retriever", RetrieverAgent(self.sector)),
            ("analyzer", AnalyzerAgent(self.sector)),
            ("writer", WriterAgent(self.sector)),
            ("scorer", ScorerAgent(self.sector)),
            ("transcriber", TranscriberAgent(self.sector)),
            ("web_researcher", WebResearchAgent(self.sector)),
        ]:
            self.register_agent(name, agent)

    def switch_sector(self, new_sector: str) -> None:
        """Switch sector for supervisor AND all sub-agents."""
        super().switch_sector(new_sector)
        for agent in self.agent_registry.values():
            agent.switch_sector(new_sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "request_type" in input_data and "data" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        request_type = input_data.get("request_type")
        sector = input_data.get("sector")
        data = input_data.get("data")
        options = input_data.get("options", {})

        if sector is not None and sector != self.sector:
            self.switch_sector(sector)
        elif sector is None and self.sector is not None:
            # Neutral mode — clear sector so no law retrieval happens
            self.sector = None
            for agent in self.agent_registry.values():
                agent.sector = None

        self.logger.info(f"Processing request type: {request_type}")

        if request_type == "pdf_analysis":
            return self._workflow_pdf_analysis(data, options)
        elif request_type == "voice_input":
            return self._workflow_voice_input(data, options)
        elif request_type == "compliance_question":
            return self._workflow_compliance_question(data, options)
        elif request_type == "scoring":
            return self._workflow_scoring(data, options)
        elif request_type == "web_research":
            return self._workflow_web_research(data, options)
        elif request_type == "draft_policy":
            return self._workflow_draft_policy(data, options)
        else:
            raise ValueError(f"Unknown request type: {request_type}")

    # ------------------------------------------------------------------
    # Workflow: PDF Analysis
    # ------------------------------------------------------------------

    def _workflow_pdf_analysis(
        self, policy_text: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a policy document for compliance gaps.

        Sequence: RetrieverAgent → AnalyzerAgent → WriterAgent → ScorerAgent
        """
        self.logger.info("Starting PDF analysis workflow")

        output_format = options.get("output_format", "pdf")

        # 1. Retrieve relevant laws
        steps = {}
        retriever_output = self.call_agent("retriever", {
            "query": policy_text[:2000], "top_k": 5, "sector": self.sector,
        })
        law_chunks = retriever_output.get("results", [])
        steps["retrieval"] = retriever_output

        if retriever_output.get("warning"):
            self.logger.warning(retriever_output["warning"])

        # 1b. Fallback: web search if no local laws found
        allow_web = options.get("allow_web_fallback", True)
        if not law_chunks and allow_web:
            self.logger.info("No local law results — searching web for relevant GRC laws")
            web_output = self.call_agent("web_researcher", {
                "query": policy_text[:500], "sector": self.sector, "top_k": 3,
            })
            steps["web_research"] = web_output
            if web_output.get("results"):
                analyzer_input = {"policy": policy_text, "web_sources": web_output["formatted"]}
            else:
                analyzer_input = {"policy": policy_text, "laws": law_chunks}
        else:
            analyzer_input = {"policy": policy_text, "laws": law_chunks}

        # 2. Analyze policy against laws (skip if retrieval failed but don't crash)
        analyzer_output = {}
        if not retriever_output.get("status") == "error":
            analyzer_output = self.call_agent("analyzer", analyzer_input)
        steps["analysis"] = analyzer_output
        gaps = analyzer_output.get("gaps", [])

        # 3. Generate report document
        writer_output = {}
        if gaps:
            writer_input = {
                "type": "gap_analysis",
                "content": {
                    "gaps": gaps,
                    "summary": analyzer_output.get("summary", ""),
                    "compliant_areas": analyzer_output.get("compliant_areas", []),
                },
                "format": output_format,
            }
            writer_output = self.call_agent("writer", writer_input)
        steps["document"] = writer_output

        # 4. Calculate compliance score
        total_req = len(law_chunks) * 2 if law_chunks else max(len(gaps) * 2, 10)
        scorer_output = self.call_agent("scorer", {
            "gaps": gaps,
            "policy_name": "policy_analysis",
            "total_requirements": total_req,
        })
        steps["score"] = scorer_output

        return {
            "workflow": "pdf_analysis",
            "steps": steps,
            "analysis": analyzer_output,
            "document": writer_output,
            "score": scorer_output,
        }

    # ------------------------------------------------------------------
    # Workflow: Voice Input
    # ------------------------------------------------------------------

    def _workflow_voice_input(
        self, audio_data: Any, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transcribe audio and generate a compliance document.

        Sequence: TranscriberAgent → AnalyzerAgent → WriterAgent
        """
        self.logger.info("Starting voice input workflow")

        doc_type = options.get("document_type", "incident_report")

        # 1. Transcribe audio
        steps = {}
        if isinstance(audio_data, dict):
            transcriber_input = audio_data
        elif isinstance(audio_data, bytes):
            transcriber_input = {"audio_data": audio_data, "language": "en"}
        else:
            transcriber_input = {"audio_path": str(audio_data)}
        transcriber_output = self.call_agent("transcriber", transcriber_input)
        steps["transcription"] = transcriber_output
        transcript = transcriber_output.get("transcript", "")

        if not transcript:
            return {"workflow": "voice_input", "steps": steps, "error": "No transcript generated"}

        # 2. Retrieve relevant laws for context
        retriever_output = self.call_agent("retriever", {
            "query": transcript[:2000], "top_k": 3, "sector": self.sector,
        })
        law_chunks = retriever_output.get("results", [])
        steps["retrieval"] = retriever_output

        # 3. Analyze / extract compliance info
        analyzer_output = self.call_agent("analyzer", {"policy": transcript, "laws": law_chunks})
        steps["analysis"] = analyzer_output
        gaps = analyzer_output.get("gaps", [])

        # 4. Calculate compliance score
        scorer_output = {}
        if gaps:
            total_req = len(law_chunks) * 2 if law_chunks else len(gaps) * 2
            scorer_output = self.call_agent("scorer", {
                "gaps": gaps,
                "policy_name": "voice_analysis",
                "total_requirements": total_req,
            })
        steps["score"] = scorer_output

        # 5. Generate document
        writer_output = {}
        if gaps:
            writer_output = self.call_agent("writer", {
                "type": doc_type,
                "content": {
                    "transcript": transcript,
                    "confidence": transcriber_output.get("confidence", 0),
                    "gaps": gaps,
                    "summary": analyzer_output.get("summary", ""),
                    "score": scorer_output.get("percentage", 0),
                },
                "format": options.get("format", "pdf"),
            })
        steps["document"] = writer_output

        return {
            "workflow": "voice_input",
            "steps": steps,
            "transcript": transcriber_output,
            "analysis": analyzer_output,
            "score": scorer_output,
            "document": writer_output,
        }

    # ------------------------------------------------------------------
    # Workflow: Compliance Question
    # ------------------------------------------------------------------

    def _system_knowledge(self) -> str:
        """Return a text block describing what sectors/laws are loaded (self-awareness).

        Delegates to the single source of truth in llm_tools.
        """
        from tools.llm_tools import _system_knowledge_block
        return _system_knowledge_block()

    def _build_system_aware_prompt(self, prompt_body: str, history: list = None) -> str:
        knowledge = self._system_knowledge()
        history_block = ""
        if history:
            lines = []
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prefix = "User" if role == "user" else "Assistant"
                lines.append(f"{prefix}: {content}")
            if lines:
                history_block = "\n\n## Previous Conversation\n\n" + "\n\n".join(lines)
        return f"{knowledge}\n\n---\n\n{history_block}\n\n{prompt_body}" if history_block else f"{knowledge}\n\n---\n\n{prompt_body}"

    def _classify_query(self, question: str) -> str:
        """Classify query as 'general', 'research', or 'compliance'."""
        q = question.strip().lower()
        import re

        general_patterns = [
            r"^(hello|hi|hey|good morning|good afternoon|good evening|greetings|sup|yo|howdy)\b",
            r"^(how are you|how's it going|how do you do|what's up|how are you doing)\b",
            r"^(thanks|thank you|cheers|appreciate it|thank you very much|thanks a lot)\b",
            r"^(bye|goodbye|see you|talk later|see you later|cya|take care)\b",
            r"^(who are you|what are you|what can you do|tell me about yourself|explain yourself|describe yourself)\b",
            r"^(nice to meet you|pleasure|good to know|interesting|i see|i understand)\b",
            r"^(yes|no|maybe|okay|ok|sure|alright|fine|great|awesome|cool|nice|good|perfect|excellent|agree|correct|right)\b",
            r"^(what is your purpose|what's your purpose|what do you do)\b",
            r"^do you (know|have|understand|remember|see|think|believe|feel)\b",
            r"^(what are you|who are you|are you an)\b",
            r".*\b(your purpose|your name|your capability|your ability|your function|your role)\b.*",
        ]
        for pattern in general_patterns:
            if re.match(pattern, q):
                return "general"

        research_patterns = [
            r"^(research|search|look up|find|google|browse|fetch|get information|gather)\b",
            r"^(can you|could you|will you) (research|search|look up|find|google|browse|fetch)\b",
            r"^i want you to (research|search|look up|find|google|browse|fetch)\b",
            r"^i need (information|details|data|news|updates) (on|about|regarding)\b",
            r"^(tell me|give me|provide) (information|details|data|news|updates) (on|about|regarding)\b",
            r"^what (is|are|was|were) the (latest|recent|current|new|upcoming)\b",
            r".*\b(on the internet|from the web|online|web research|do research|do a search)\b.*",
        ]
        for pattern in research_patterns:
            if re.match(pattern, q):
                return "research"

        has_law_terms = re.search(
            r"\b(act|law|regulation|section |compliance|policy|requirement|violation|breach|penalty|obligation|rights|duty|mandate|provision|clause|statute|decree|directive|fine |legal |comply|non.compliance)\b",
            q,
        )
        draft_patterns = [
            r"^(draft|write|create|generate|produce|make) .*(policy|document|report|pdf|compliance|regulation|law|act|guideline)\b",
            r"\b(draft a|write a|create a|generate a|produce a) .*(policy|document|report|pdf)\b",
            r"\b(policy draft|draft policy|compliance draft|draft report|draft document|pdf draft)\b",
            r"\b(need a|prepare a|develop a) .*(policy|draft)\b",
        ]
        for pattern in draft_patterns:
            if re.search(pattern, q):
                return "draft"

        self_ref_extra = [
            r"^(can you|do you|will you|could you)\b",
        ]
        for pattern in self_ref_extra:
            if re.match(pattern, q) and not has_law_terms:
                return "general"

        return "compliance"

    def _detect_sector(self, query: str) -> Optional[str]:
        """Detect the most likely sector from a user query, or None if unknown."""
        q = query.strip().lower()
        scores = {}
        from config.settings import settings as s
        for entry in s.SECTOR_CONFIG.get("sectors", []):
            sid = entry["id"]
            keywords = entry.get("name", sid).lower().split()
            # Sector-specific keywords
            if sid == "cybersecurity":
                kw = {"cybersecurity", "cyber", "act 1038", "data breach", "information security",
                      "hack", "ransomware", "phishing", "network security", "it security",
                      "security incident", "vulnerability", "penetration test"}
            elif sid == "fintech":
                kw = {"fintech", "mobile money", "payment", "banking", "financial service",
                      "act 987", "bank of ghana", "e-money", "digital payment", "mobile banking",
                      "payment system", "financial technology"}
            elif sid == "data_protection":
                kw = {"data protection", "act 843", "privacy", "personal data", "dpia",
                      "data subject", "data controller", "data processor", "gdpr",
                      "personal information", "data privacy", "consent"}
            elif sid == "healthcare":
                kw = {"healthcare", "health", "medical", "patient", "hospital", "clinical",
                      "act 829", "health information", "patient data", "medical record",
                      "telemedicine", "health service"}
            else:
                kw = set(keywords)
            score = sum(1 for k in kw if k in q)
            if score > 0:
                scores[sid] = score
        if not scores:
            return None
        return max(scores, key=scores.get)

    def _retrieve_all_sectors(self, question: str, top_k: int) -> Dict[str, Any]:
        """Query all enabled sectors and merge results, deduplicating by chunk ID."""
        all_results = []
        seen_ids = set()
        for entry in settings.SECTOR_CONFIG.get("sectors", []):
            if not entry.get("enabled"):
                continue
            sid = entry["id"]
            try:
                out = self.call_agent("retriever", {"query": question, "top_k": top_k, "sector": sid})
                results = out.get("results", [])
                for r in results:
                    chunk_id = r.get("id", "")
                    if chunk_id and chunk_id in seen_ids:
                        continue
                    if chunk_id:
                        seen_ids.add(chunk_id)
                    r["_sector"] = sid
                    all_results.append(r)
                if results:
                    self.logger.info(f"  sector={sid}: {len(results)} results")
            except Exception as e:
                self.logger.warning(f"  sector={sid}: retrieval failed — {e}")
        all_results.sort(key=lambda r: r.get("score", 0), reverse=True)
        all_results = all_results[:top_k]
        return {
            "results": all_results,
            "confidence_scores": [r.get("score", 0) for r in all_results],
            "query": question,
        }

    def _workflow_compliance_question(
        self, question: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Answer a compliance question with law citations.

        Sequence: Classifier → (General → chat) | (Compliance → RetrieverAgent → LLM)
        """
        self.logger.info(f"Processing: {question[:100]}...")

        query_type = self._classify_query(question)
        top_k = options.get("top_k", 5)
        return_sources = options.get("return_sources", True)
        allow_web_fallback = options.get("allow_web_fallback", True)
        conversation_history = options.get("history", None)

        # --- General conversation only ---
        if query_type == "general":
            from tools.llm_tools import call_llm
            answer_text = call_llm(
                prompt=self._build_system_aware_prompt(
                    f"Respond naturally and conversationally to the user.\n\n"
                    f"You have real-time web research capability. If the user needs information you do not have, "
                    f"offer to search the web for them. Do not mention your internal law database or sectors.\n\n"
                    f"User: {question}\n\n"
                    f"GRaC:",
                    history=conversation_history,
                ),
            )
            return {
                "workflow": "compliance_question",
                "answer": answer_text,
                "sources": [],
                "confidence": 1.0,
                "query_type": "general",
            }

        # --- Everything else: law retrieval + automatic web search ---
        steps = {}
        from tools.llm_tools import call_llm

        # 1) ChromaDB retrieval — always try current sector, cross-search if few results
        law_chunks = []
        retriever_output = {"results": [], "confidence_scores": []}
        if self.sector and self.sector.lower() not in ("neutral", "none", ""):
            cache_key = hashlib.md5(f"{self.sector}:{question}:{top_k}".encode()).hexdigest()
            if cache_key in self._query_cache:
                retriever_output = self._query_cache[cache_key]
                self.logger.info("Retrieval cache hit")
            else:
                retriever_output = self.call_agent("retriever", {"query": question, "top_k": top_k, "sector": self.sector})
                self._query_cache[cache_key] = retriever_output
                if len(self._query_cache) > 100:
                    self._query_cache.pop(next(iter(self._query_cache)))
            law_chunks = retriever_output.get("results", [])
            steps["retrieval"] = retriever_output

            # If few results from primary sector, cross-search all sectors (deep research)
            if len(law_chunks) < 3:
                self.logger.info("Few local results — cross-searching all sectors")
                cross_results = self._retrieve_all_sectors(question, top_k * 2)
                cross_chunks = cross_results.get("results", [])
                if cross_chunks:
                    existing_ids = {c.get("id", "") for c in law_chunks}
                    for c in cross_chunks:
                        if c.get("id", "") not in existing_ids:
                            law_chunks.append(c)
                            existing_ids.add(c.get("id", ""))
                    law_chunks = law_chunks[:top_k]
                    steps["cross_sector_retrieval"] = cross_results
                    self.logger.info(f"Cross-sector added {len(law_chunks)} total chunks")
        else:
            self.logger.info("Neutral mode — skipping ChromaDB retrieval, using web search only")

        # 2) Web search (always, for every non-general query)
        # Build a richer search query from conversation history for follow-up questions
        web_query = question
        if conversation_history:
            prev_user_msgs = [m["content"] for m in conversation_history if m.get("role") == "user"][-3:]
            if prev_user_msgs:
                topic_context = " ".join(prev_user_msgs[-2:])
                if len(question.split()) < 6:
                    web_query = f"{topic_context} {question}"
        web_output = self.call_agent("web_researcher", {
            "query": web_query, "sector": self.sector or "general", "top_k": top_k, "fetch_detail": True,
        })
        steps["web_research"] = web_output
        web_has_results = bool(web_output.get("results"))

        # 3) Build prompt with whatever context we have
        has_sources = bool(law_chunks) or web_has_results
        prompt_parts = []
        if has_sources:
            prompt_parts.append("Answer the user's question using the sources below. Cite them where appropriate.\n")

        if law_chunks:
            prompt_parts.append("## Loaded Laws\n")
            for i, chunk in enumerate(law_chunks[:top_k], 1):
                meta = chunk.get("metadata", {})
                sec = chunk.get("_sector") or self.sector or "neutral"
                text = chunk.get("text", "")[:500]
                prompt_parts.append(
                    f"[{i}] Law: {meta.get('law_name', 'Unknown')}"
                    f"{' §' + meta.get('section_number', '') if meta.get('section_number') else ''}"
                    f" | Sector: {sec}\n{text}\n"
                )

        if web_has_results:
            prompt_parts.append("## Web Search Results\n")
            for i, r in enumerate(web_output["results"][:top_k], 1):
                title = r.get("title", "Unknown")
                snippet = r.get("snippet", "")
                url = r.get("url", "")
                prompt_parts.append(f"[{i}] {title}\n{snippet}\nURL: {url}\n")

        if web_output.get("detailed"):
            prompt_parts.append("## Detailed Web Content\n\n" + web_output["detailed"][:4000] + "\n")

        # 3b) Feedback history — surface expert corrections for similar queries
        try:
            feedback_path = settings.DATA_DIR / "feedback" / "feedback.jsonl"
            if feedback_path.exists():
                import json as _json
                similar_feedback = []
                q_lower = question.lower()
                q_words = set(q_lower.split())
                with open(feedback_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue
                        if entry.get("correction"):
                            fb_q = (entry.get("question") or "").lower()
                            fb_words = set(fb_q.split())
                            overlap = len(q_words & fb_words)
                            if overlap >= 2:
                                similar_feedback.append(entry)
                if similar_feedback:
                    prompt_parts.append("## Expert Corrections (from past feedback)\n")
                    for fb in similar_feedback[:3]:
                        prompt_parts.append(
                            f"Previous question: {fb.get('question', '')}\n"
                            f"Expert correction: {fb.get('correction', '')}\n"
                        )
        except Exception:
            pass

        prompt_parts.append(f"## Question\n\n{question}")

        prompt = self._build_system_aware_prompt("\n".join(prompt_parts), history=conversation_history)
        answer_text = call_llm(prompt=prompt)

        # 4) Compute sources
        scores = retriever_output.get("confidence_scores", [])
        confidence = round(sum(scores) / len(scores), 4) if scores else 0.0

        sources = []
        if return_sources:
            if law_chunks:
                for c in law_chunks[:top_k]:
                    meta = c.get("metadata", {})
                    sec = c.get("_sector")
                    sources.append({
                        "law_name": meta.get("law_name", "Unknown"),
                        "section_number": meta.get("section_number", ""),
                        "section_title": meta.get("section_title", ""),
                        "text": c.get("text", "")[:300],
                        "score": c.get("score", 0),
                        "sector": sec or self.sector or "neutral",
                        "source": "local",
                    })
            if web_has_results:
                for r in web_output["results"][:top_k]:
                    sources.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                        "source": "web",
                    })

        # 5) If draft query, auto-generate a PDF
        draft_url = ""
        if query_type == "draft" and answer_text and len(answer_text) > 50:
            try:
                from agents.writer import WriterAgent
                import json
                content = {
                    "summary": answer_text[:600],
                    "findings": [],
                    "recommendations": [],
                }
                writer = WriterAgent(self.sector or "general")
                writer_input = {
                    "type": "policy_draft",
                    "content": content,
                    "format": "pdf",
                    "metadata": {"author": "GRaC Compliance System", "company": "Ghana Regulatory Compliance (GRaC)"},
                }
                writer_out = writer.execute(writer_input)
                wr = writer.format_output(writer_out)
                path = wr.get("path", "")
                if path:
                    from pathlib import Path
                    fn = Path(path).name
                    draft_url = f"/api/download/{fn}"
                    self.logger.info(f"Draft PDF auto-generated: {draft_url}")
            except Exception as e:
                self.logger.warning(f"Draft auto-generation failed: {e}")

        return {
            "workflow": "compliance_question",
            "answer": answer_text,
            "sources": sources,
            "confidence": confidence,
            "steps": steps,
            "query_type": query_type,
            "draft_url": draft_url,
        }

    # ------------------------------------------------------------------
    # Workflow: Web Research
    # ------------------------------------------------------------------

    def _workflow_web_research(
        self, query: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Direct web research for GRC laws and compliance information.

        Sequence: WebResearchAgent → LLM summary (optional)
        """
        self.logger.info(f"Starting web research for: {str(query)[:100]}...")

        summarize = options.get("summarize", False)
        top_k = options.get("top_k", 5)

        web_output = self.call_agent("web_researcher", {
            "query": query, "sector": self.sector, "top_k": top_k, "fetch_detail": summarize,
        })

        result = {
            "workflow": "web_research",
            "results": web_output.get("results", []),
            "formatted": web_output.get("formatted", ""),
            "count": web_output.get("count", 0),
        }

        if summarize and web_output.get("detailed"):
            from tools.llm_tools import call_llm
            summary_prompt = (
                f"Summarize the following web research about GRC laws and regulations.\n\n"
                f"## Source Content\n\n{web_output['detailed'][:5000]}\n\n"
                f"## Search Results\n\n{web_output['formatted']}\n\n"
                f"Provide a concise summary highlighting key legal requirements and citations."
            )
            result["summary"] = call_llm(
                prompt=summary_prompt,
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )

        return result

    # ------------------------------------------------------------------
    # Workflow: Scoring
    # ------------------------------------------------------------------

    def _workflow_scoring(
        self, policy_text: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate a compliance score for a policy.

        Sequence: RetrieverAgent → AnalyzerAgent → ScorerAgent
        """
        self.logger.info("Starting compliance scoring workflow")

        # 1. Retrieve relevant laws
        steps = {}
        retriever_output = self.call_agent("retriever", {
            "query": policy_text[:2000], "top_k": 5, "sector": self.sector,
        })
        law_chunks = retriever_output.get("results", [])
        steps["retrieval"] = retriever_output

        # Web fallback if no laws found
        web_out = None
        if not law_chunks and options.get("allow_web_fallback", True):
            self.logger.info("No local law results for scoring — searching web")
            web_out = self.call_agent("web_researcher", {
                "query": policy_text[:500], "sector": self.sector, "top_k": 3,
            })
            steps["web_research"] = web_out

        # 2. Analyze compliance
        analyzer_output = {}
        if retriever_output.get("status") != "error":
            if law_chunks:
                analyzer_output = self.call_agent("analyzer", {"policy": policy_text, "laws": law_chunks})
            elif web_out and web_out.get("results"):
                analyzer_output = self.call_agent("analyzer", {"policy": policy_text, "web_sources": web_out.get("formatted", "")})
        steps["analysis"] = analyzer_output
        gaps = analyzer_output.get("gaps", [])

        # 3. Score
        total_req = options.get("total_requirements", len(law_chunks) * 2 if law_chunks else max(len(gaps) * 2, 10))
        scorer_input = {
            "gaps": gaps,
            "policy_name": "compliance_scoring",
            "total_requirements": total_req,
        }
        scorer_output = self.call_agent("scorer", scorer_input)
        steps["score"] = scorer_output

        return {
            "workflow": "scoring",
            "steps": steps,
            "analysis": analyzer_output,
            "score": scorer_output,
        }

    # ------------------------------------------------------------------
    # Workflow: Draft Policy PDF
    # ------------------------------------------------------------------

    def _workflow_draft_policy(
        self, topic: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a compliance policy PDF from a topic description.

        Sequence: RetrieverAgent → LLM analysis → WriterAgent
        Returns download URL for the generated PDF.
        """
        self.logger.info(f"Starting draft policy workflow: {topic[:100]}...")

        from tools.llm_tools import call_llm
        from agents.writer import WriterAgent
        import json

        resolved_sector = options.get("sector") or self.sector or "cybersecurity"

        # 1. Retrieve law context
        law_context = ""
        try:
            if self.sector and self.sector.lower() not in ("neutral", "none", ""):
                retriever_out = self.call_agent("retriever", {"query": topic, "top_k": 5, "sector": self.sector})
            else:
                retriever_out = self.call_agent("retriever", {"query": topic, "top_k": 3, "sector": "general"})
            chunks = retriever_out.get("results", [])
            if chunks:
                parts = []
                for c in chunks:
                    meta = c.get("metadata", {})
                    law_name = meta.get("law_name", "Unknown")
                    sec = meta.get("section_number", "")
                    text = (c.get("text", "") or "")[:400]
                    parts.append(f"{law_name}{' \u00a7'+sec if sec else ''}:\n{text}")
                law_context = "\n\n".join(parts)
        except Exception as e:
            self.logger.warning(f"Draft law retrieval warning: {e}")

        # 1b) Fallback: web research for law context if ChromaDB returned nothing
        web_context = ""
        if not law_context:
            try:
                web_results = search_web(f"Ghana {resolved_sector} {topic} law regulation", max_results=5)
                if web_results:
                    parts = []
                    for r in web_results[:5]:
                        title = r.get("title", "")
                        snippet = r.get("snippet", "")
                        url = r.get("url", "")
                        parts.append(f"{title}\n{snippet}\nURL: {url}")
                    web_context = "\n\n".join(parts)
                    self.logger.info(f"Web research added {len(web_results)} sources for draft")
            except Exception as e:
                self.logger.warning(f"Draft web research failed: {e}")

        # 2. Analyse topic with LLM to extract structured content
        context_parts = []
        if law_context:
            context_parts.append(f"Relevant Law Context:\n{law_context}")
        if web_context:
            context_parts.append(f"Web Research Context (use these as law references):\n{web_context}")
        if not law_context and not web_context:
            context_parts.append("No specific law context retrieved. Use your general knowledge of Ghanaian regulations in the {resolved_sector} sector.")

        analysis_prompt = f"""You are a Ghanaian compliance analyst. Given the topic below, extract:
1. A 2-3 sentence summary of what this policy must cover
2. 3-5 key compliance findings/requirements (numbered, with specific Ghanaian law references)
3. 2-4 actionable recommendations

Topic: {topic}
Sector: {resolved_sector}
{chr(10).join(context_parts)}

Output JSON with keys: summary, findings (list of strings), recommendations (list of strings)"""

        analysis_raw = call_llm(prompt=analysis_prompt)
        content = {"summary": "", "findings": [], "recommendations": []}
        try:
            json_str = analysis_raw.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            parsed = json.loads(json_str)
            content.update(parsed)
        except (json.JSONDecodeError, IndexError):
            content["summary"] = analysis_raw[:500]

        # 3. Generate PDF via WriterAgent
        writer = WriterAgent(resolved_sector)
        writer_input = {
            "type": "policy_draft",
            "content": content,
            "format": "pdf",
            "metadata": {"author": "GRaC Compliance System", "company": "Ghana Regulatory Compliance (GRaC)"},
        }
        writer_out = writer.execute(writer_input)
        result = writer.format_output(writer_out)

        from pathlib import Path
        path = result.get("path", "")
        filename = Path(path).name if path else ""

        return {
            "workflow": "draft_policy",
            "status": "ok",
            "path": path,
            "filename": filename,
            "download_url": f"/api/download/{filename}" if filename else "",
            "title": result.get("title", ""),
        }

    # ------------------------------------------------------------------
    # Output & agent management
    # ------------------------------------------------------------------

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "sector": self.sector,
            "result": result,
        }

    def register_agent(self, agent_name: str, agent_instance: BaseAgent) -> None:
        self.agent_registry[agent_name] = agent_instance
        self.logger.info(f"Registered agent: {agent_name}")

    def call_agent(self, agent_name: str, input_data: Any, **kwargs) -> Dict[str, Any]:
        if agent_name not in self.agent_registry:
            raise ValueError(f"Agent not registered: {agent_name}")

        agent = self.agent_registry[agent_name]
        self.logger.info(f"Calling agent: {agent_name}")
        result = agent.run(input_data, **kwargs)

        if result.get("status") == "error":
            self.logger.error(f"Agent {agent_name} failed: {result.get('error')}")
            result["agent"] = agent_name

        return result
