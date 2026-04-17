from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SentimentResult:
    ticket_id: str = ""
    sentiment: int = 3  # 1-5
    confidence: float = 0.0
    indicators: list[str] = field(default_factory=list)


@dataclass
class CategorySuggestion:
    ticket_id: str = ""
    current_issue_type: str = ""
    current_sub_issue: str = ""
    suggested_issue_type: str = ""
    suggested_sub_issue: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass
class AIAnalysisResult:
    sentiment: list[SentimentResult] = field(default_factory=list)
    sentiment_summary: dict = field(default_factory=dict)
    category_suggestions: list[CategorySuggestion] = field(default_factory=list)
    executive_summary: str = ""
    anomaly_narratives: list[str] = field(default_factory=list)
    frustration_hotspots: list[dict] = field(default_factory=list)
    frustration_by_type: list[dict] = field(default_factory=list)
    hygiene_report: dict = field(default_factory=dict)
    talking_points: list[str] = field(default_factory=list)
    calls_made: int = 0
    tokens_used: int = 0
    errors: list[str] = field(default_factory=list)


def _clean(df: pd.DataFrame, col: str) -> pd.Series:
    return df.get(col, pd.Series(dtype=str)).fillna("").astype(str).str.strip()


class AIEngine:
    def __init__(self, settings: dict):
        ai_cfg = settings.get("ai", {})
        self.enabled = ai_cfg.get("enabled", False)
        self.provider = ai_cfg.get("provider", "azure_openai")
        self.endpoint = ai_cfg.get("endpoint", "")
        self.base_url = ai_cfg.get("base_url", "")
        self.api_key = ai_cfg.get("api_key", "")
        self.organization = ai_cfg.get("organization", "")
        self.project = ai_cfg.get("project", "")
        self.deployment = ai_cfg.get("deployment", "gpt-5.4")
        self.reasoning_effort = ai_cfg.get("reasoning_effort", "high")
        self.api_version = ai_cfg.get("api_version", "2026-02-01")
        self.max_calls = ai_cfg.get("max_calls_per_run", 50)
        self.features = ai_cfg.get("features", {
            "sentiment": True,
            "categorization": True,
            "prediction": True,
            "executive_summary": True,
            "anomaly_narration": True,
        })
        self.tone = ai_cfg.get("tone", "formal")
        self.custom_instructions = ai_cfg.get("custom_instructions", "")
        self._client = None
        self._calls_made = 0
        self._tokens_used = 0
        self._errors: list[str] = []
        self._progress_callback = None  # callable(event_dict) for SSE streaming

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def _emit(self, event_type: str, message: str, data: dict | None = None):
        if self._progress_callback:
            self._progress_callback({
                "type": event_type,
                "message": message,
                "calls": self._calls_made,
                "tokens": self._tokens_used,
                "data": data or {},
            })

    def _resolved_provider_config(self) -> dict[str, str]:
        if self.provider == "azure_openai":
            return {
                "endpoint": (self.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")).strip(),
                "api_key": (self.api_key or os.getenv("AZURE_OPENAI_API_KEY", "")).strip(),
                "api_version": (self.api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2026-02-01")).strip(),
            }

        if self.provider == "openai":
            organization = self.organization or os.getenv("OPENAI_ORG_ID", "") or os.getenv("OPENAI_ORGANIZATION", "")
            project = self.project or os.getenv("OPENAI_PROJECT_ID", "") or os.getenv("OPENAI_PROJECT", "")
            return {
                "api_key": (self.api_key or os.getenv("OPENAI_API_KEY", "")).strip(),
                "base_url": (self.base_url or os.getenv("OPENAI_BASE_URL", "")).strip(),
                "organization": organization.strip(),
                "project": project.strip(),
            }

        if self.provider == "chatgpt_oauth":
            return {"provider": "chatgpt_oauth"}

        return {}

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Extract JSON from a response that may have markdown or text wrapping."""
        content = content.strip()
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        # Try extracting from ```json ... ``` markdown blocks
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding the first { ... } block
        brace_start = content.find('{')
        brace_end = content.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(content[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass
        return {}

    def _call_codex_responses(self, system: str, user: str) -> dict:
        """Call the Codex Responses API (streaming, for ChatGPT OAuth). Uses sync httpx."""
        import httpx
        from codex_auth import auth

        tokens = auth.authenticate()
        full_text = ""
        try:
            # Use a regular POST and collect the full SSE response
            resp = httpx.post(
                "https://chatgpt.com/backend-api/codex/responses",
                headers={
                    "Authorization": f"Bearer {tokens.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.deployment,
                    "store": False,
                    "stream": True,
                    "instructions": "CRITICAL: Respond with ONLY valid JSON. No markdown, no text, no code fences.\n\n" + system,
                    "input": [{"role": "user", "content": user}],
                },
                timeout=90,
            )
            if resp.status_code != 200:
                self._errors.append(f"Codex API {resp.status_code}: {resp.text[:80]}")
                return {}

            # Parse SSE from the full response body
            for line in resp.text.split("\n"):
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        d = json.loads(chunk)
                        if d.get("type") == "response.output_text.delta":
                            full_text += d.get("delta", "")
                        if d.get("type") == "response.completed" and d.get("response", {}).get("usage"):
                            usage = d["response"]["usage"]
                            self._tokens_used += usage.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            self._errors.append(f"Codex error: {str(e)[:80]}")
            return {}

        self._calls_made += 1
        if self._calls_made <= 3:
            print(f"[AI DEBUG] Codex call {self._calls_made}: {full_text[:200]}")
        return self._parse_json_response(full_text)

    def _get_client(self):
        if self._client is not None:
            return self._client

        resolved = self._resolved_provider_config()
        if self.provider == "azure_openai":
            if not resolved.get("endpoint") or not resolved.get("api_key"):
                raise ValueError(
                    "Azure OpenAI requires both an endpoint and API key in Settings > AI, "
                    "or the AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY environment variables."
                )
        elif self.provider == "openai":
            if not resolved.get("api_key"):
                raise ValueError(
                    "OpenAI API requires an API key in Settings > AI, or the OPENAI_API_KEY environment variable."
                )
        elif self.provider == "chatgpt_oauth":
            pass  # codex_auth handles authentication
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

        try:
            if self.provider == "azure_openai":
                from openai import AzureOpenAI

                self._client = AzureOpenAI(
                    azure_endpoint=resolved["endpoint"],
                    api_key=resolved["api_key"],
                    api_version=resolved["api_version"],
                )
            elif self.provider == "chatgpt_oauth":
                try:
                    from codex_auth import CodexClient
                    self._client = CodexClient()
                except ImportError:
                    raise ValueError(
                        "ChatGPT OAuth requires the codex-auth package. "
                        "Install it with: pip install codex-auth"
                    )
                except Exception as e:
                    raise ValueError(
                        f"ChatGPT OAuth login failed: {e}. "
                        "Try running the app again — a browser window should open for login."
                    )
            else:
                from openai import OpenAI

                kwargs: dict[str, Any] = {"api_key": resolved["api_key"]}
                if resolved.get("base_url"):
                    kwargs["base_url"] = resolved["base_url"]
                if resolved.get("organization"):
                    kwargs["organization"] = resolved["organization"]
                if resolved.get("project"):
                    kwargs["project"] = resolved["project"]
                self._client = OpenAI(**kwargs)
            return self._client
        except ValueError:
            raise
        except Exception as e:
            labels = {"azure_openai": "Azure OpenAI", "openai": "OpenAI", "chatgpt_oauth": "ChatGPT OAuth"}
            raise ValueError(f"Failed to initialize {labels.get(self.provider, self.provider)} client: {e}")

    def _call(self, system: str, user: str, max_tokens: int = 4096) -> dict:
        """Single API call. Returns parsed JSON dict."""
        if self._calls_made >= self.max_calls:
            self._errors.append(f"Call limit reached ({self.max_calls})")
            return {}

        client = self._get_client()
        retries = 3
        for attempt in range(retries):
            try:
                # ChatGPT OAuth uses the Codex Responses API (streaming required)
                if self.provider == "chatgpt_oauth":
                    return self._call_codex_responses(system, user)

                call_kwargs: dict[str, Any] = {
                    "model": self.deployment,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": max_tokens,
                }
                if self.reasoning_effort and self.reasoning_effort != "none":
                    call_kwargs["extra_body"] = {"reasoning": {"effort": self.reasoning_effort}}
                else:
                    call_kwargs["temperature"] = 0.3

                response = client.chat.completions.create(**call_kwargs)
                self._calls_made += 1
                if response.usage:
                    self._tokens_used += response.usage.total_tokens
                content = response.choices[0].message.content or ""
                # Debug: log first few raw responses
                if self._calls_made <= 3:
                    print(f"[AI DEBUG] Call {self._calls_made} raw response ({len(content)} chars): {content[:300]}")
                parsed = self._parse_json_response(content)
                if not parsed and content:
                    self._errors.append(f"JSON parse failed on call {self._calls_made}: {content[:80]}")
                return parsed
            except json.JSONDecodeError:
                self._errors.append(f"Invalid JSON response on call {self._calls_made + 1}")
                return {}
            except Exception as e:
                err_str = str(e)
                # Don't retry 400 errors — they're parameter issues, not transient
                if "400" in err_str or "Unsupported parameter" in err_str:
                    self._errors.append(f"API error: {err_str[:100]}")
                    return {}
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                self._errors.append(f"API error: {err_str[:100]}")
                return {}
        return {}

    # -------------------------------------------------------------------
    # 9A. Sentiment Analysis
    # -------------------------------------------------------------------
    def analyze_sentiment_batch(self, tickets: list[dict], batch_size: int = 20) -> list[SentimentResult]:
        if not self.features.get("sentiment", True):
            return []

        system = (
            "You are an MSP helpdesk ticket sentiment analyzer. For each ticket, rate the "
            "end-user's sentiment from 1-5 (1=frustrated/angry, 2=dissatisfied, 3=neutral, "
            "4=satisfied, 5=appreciative). Base assessment on title and description tone.\n\n"
            "Respond with JSON: {\"results\": [{\"id\": \"...\", \"sentiment\": 3, "
            "\"confidence\": 0.85, \"indicators\": [\"keyword1\"]}]}"
        )

        all_results = []
        total_batches = (len(tickets) + batch_size - 1) // batch_size
        for i in range(0, len(tickets), batch_size):
            batch_num = i // batch_size + 1
            batch = tickets[i:i + batch_size]
            self._emit("trace", f"Sentiment batch {batch_num}/{total_batches} — {len(batch)} tickets")
            user_msg = json.dumps({"tickets": [
                {"id": t.get("ticket_id", ""), "title": t.get("title", ""), "description": t.get("description", "")[:300]}
                for t in batch
            ]})

            resp = self._call(system, user_msg)
            for r in resp.get("results", []):
                all_results.append(SentimentResult(
                    ticket_id=r.get("id", ""),
                    sentiment=max(1, min(5, r.get("sentiment", 3))),
                    confidence=r.get("confidence", 0.0),
                    indicators=r.get("indicators", []),
                ))

        return all_results

    # -------------------------------------------------------------------
    # 9B. Category Suggestions (Unknown/Mismatch only)
    # -------------------------------------------------------------------
    def suggest_categories_batch(self, tickets: list[dict], batch_size: int = 20) -> list[CategorySuggestion]:
        if not self.features.get("categorization", True):
            return []

        system = (
            "You are an IT helpdesk ticket classifier. These tickets have 'Unknown' or 'Other' "
            "as their Issue Type/Sub-Issue Type, or appear miscategorized.\n\n"
            "For each ticket, SUGGEST a better category from: "
            "[Computer, Email, Software, Network, Security, Hardware/Peripherals, "
            "User Account/Access, Mobile Device, Spam]\n\n"
            "Respond with JSON: {\"suggestions\": [{\"id\": \"...\", "
            "\"suggested_issue_type\": \"...\", \"suggested_sub_issue\": \"...\", "
            "\"confidence\": 0.85, \"reason\": \"...\"}]}"
        )

        all_results = []
        for i in range(0, len(tickets), batch_size):
            batch = tickets[i:i + batch_size]
            user_msg = json.dumps({"tickets": [
                {
                    "id": t.get("ticket_id", ""),
                    "title": t.get("title", ""),
                    "description": t.get("description", "")[:300],
                    "current_issue_type": t.get("issue_type", ""),
                    "current_sub_issue": t.get("sub_issue_type", ""),
                }
                for t in batch
            ]})

            resp = self._call(system, user_msg)
            for r in resp.get("suggestions", []):
                all_results.append(CategorySuggestion(
                    ticket_id=r.get("id", ""),
                    suggested_issue_type=r.get("suggested_issue_type", ""),
                    suggested_sub_issue=r.get("suggested_sub_issue", ""),
                    confidence=r.get("confidence", 0.0),
                    reason=r.get("reason", ""),
                ))

        return all_results

    def categorize_tickets_batch(self, tickets: list[dict], batch_size: int = 20) -> list[CategorySuggestion]:
        return self.suggest_categories_batch(tickets, batch_size=batch_size)

    # -------------------------------------------------------------------
    # 9C. Governance Talking Points
    # -------------------------------------------------------------------
    def generate_talking_points(
        self, metrics: dict, observations: list[str], company_data: list[dict],
    ) -> list[str]:
        """Generate 5-7 actionable governance call talking points."""
        system = (
            "You are preparing an SDM for a governance call with an MSP partner. "
            "Generate 5-7 specific, actionable talking points based on the metrics and observations. "
            "Each point should reference specific companies, issue types, or patterns. "
            "Be concrete — 'Ask Crestline about 10 password resets at SF Marriott' not 'discuss password issues'.\n\n"
            'Respond with JSON: {"talking_points": ["point 1", "point 2", ...]}'
        )

        user_msg = json.dumps({
            "headline_metrics": metrics,
            "service_observations": observations[:8],
            "top_companies": company_data[:10],
        }, default=str)

        resp = self._call(system, user_msg)
        return resp.get("talking_points", [])

    # -------------------------------------------------------------------
    # 9D. Executive Summary
    # -------------------------------------------------------------------
    def generate_executive_summary(
        self, metrics: dict, observations: list[str], actions: list[str],
        custom_instructions: str = "",
    ) -> str:
        if not self.features.get("executive_summary", True):
            return ""

        custom_preamble = ""
        if custom_instructions:
            custom_preamble = f"IMPORTANT USER INSTRUCTIONS: {custom_instructions}\n\n"

        system = (
            f"{custom_preamble}"
            f"You are writing an executive summary for an MSP governance review meeting. "
            f"Tone: {self.tone}. Write 3-4 concise paragraphs focusing on actionable insights "
            f"and trends. Do not restate raw numbers — interpret them for a non-technical audience. "
            f'Respond with JSON: {{"summary": "your summary text here"}}'
        )

        user_msg = json.dumps({
            "headline_metrics": metrics,
            "service_observations": observations[:8],
            "priority_actions": actions[:5],
        }, default=str)

        resp = self._call(system, user_msg, max_tokens=1500)
        return resp.get("summary", resp.get("executive_summary", ""))

    # -------------------------------------------------------------------
    # 9E. Anomaly Narration
    # -------------------------------------------------------------------
    def narrate_anomalies(self, deltas: dict, sample_tickets: list[dict]) -> list[str]:
        if not self.features.get("anomaly_narration", True):
            return []
        if not deltas:
            return []

        system = (
            "You are an MSP data analyst. These metrics changed significantly between periods. "
            "Explain the likely causes in 2-3 bullet points. Be specific about which companies, "
            "issue types, or patterns drove the change.\n\n"
            "Respond with JSON: {\"narratives\": [\"bullet 1\", \"bullet 2\"]}"
        )

        user_msg = json.dumps({
            "deltas": deltas,
            "sample_tickets": sample_tickets[:20],
        }, default=str)

        resp = self._call(system, user_msg)
        return resp.get("narratives", [])

    # -------------------------------------------------------------------
    # Master orchestrator
    # -------------------------------------------------------------------
    def run_full_analysis(
        self,
        df: pd.DataFrame,
        artifacts,
        comparison_deltas: dict | None = None,
    ) -> AIAnalysisResult:
        """Run all enabled AI analyses. Respects max_calls_per_run."""
        self._calls_made = 0
        self._tokens_used = 0
        self._errors = []

        # Prepare ticket dicts
        all_tickets = []
        for _, row in df.head(500).iterrows():  # cap at 500 for API cost
            all_tickets.append({
                "ticket_id": str(row.get("Ticket Number", "")),
                "title": str(row.get("Title", "")),
                "description": str(row.get("Description", ""))[:400],
                "issue_type": str(row.get("Issue Type", "")),
                "sub_issue_type": str(row.get("Sub-Issue Type", "")),
                "priority": str(row.get("Priority", "")),
                "queue": str(row.get("Queue", "")),
                "company": str(row.get("Company", "")),
                "source": str(row.get("Source", "")),
            })

        tickets_by_id = {t["ticket_id"]: t for t in all_tickets}
        self._emit("start", f"Analyzing {len(all_tickets)} tickets with {self.deployment}")

        # 9A: Sentiment
        self._emit("phase", "SENTIMENT ANALYSIS", {"total": len(all_tickets), "batch_size": 20})
        sentiment = self.analyze_sentiment_batch(all_tickets)
        sentiment_summary = {}
        if sentiment:
            scores = [s.sentiment for s in sentiment]
            sentiment_summary = {
                "mean": round(sum(scores) / len(scores), 1),
                "distribution": {i: scores.count(i) for i in range(1, 6)},
                "low_count": sum(1 for s in scores if s <= 2),
                "high_count": sum(1 for s in scores if s >= 4),
            }

        # 9A+: Frustration hotspots (aggregate sentiment by company and issue type)
        frustration_hotspots = []
        frustration_by_type = []
        if sentiment:
            # By company
            company_sentiments: dict[str, list[SentimentResult]] = defaultdict(list)
            for s in sentiment:
                ticket = tickets_by_id.get(s.ticket_id)
                if ticket:
                    company_sentiments[ticket["company"]].append(s)

            for company, items in company_sentiments.items():
                if not company or len(items) < 3:
                    continue
                avg = round(sum(s.sentiment for s in items) / len(items), 2)
                if avg <= 2.5:
                    frustration_hotspots.append({
                        "company": company,
                        "avg_sentiment": avg,
                        "ticket_count": len(items),
                        "frustration_score": round((5 - avg) * len(items), 1),
                        "sample_titles": [
                            tickets_by_id.get(s.ticket_id, {}).get("title", "")
                            for s in sorted(items, key=lambda x: x.sentiment)[:3]
                        ],
                    })
            frustration_hotspots.sort(key=lambda x: -x["frustration_score"])

            # By issue type
            type_sentiments: dict[str, list[SentimentResult]] = defaultdict(list)
            for s in sentiment:
                ticket = tickets_by_id.get(s.ticket_id)
                if ticket:
                    type_sentiments[ticket["issue_type"]].append(s)

            for issue_type, items in type_sentiments.items():
                if not issue_type:
                    continue
                avg = round(sum(s.sentiment for s in items) / len(items), 2)
                frustration_by_type.append({
                    "issue_type": issue_type,
                    "avg_sentiment": avg,
                    "ticket_count": len(items),
                })
            frustration_by_type.sort(key=lambda x: x["avg_sentiment"])

        if sentiment:
            self._emit("result", f"Sentiment complete: mean={sentiment_summary.get('mean')}, {len(frustration_hotspots)} hotspots", {"hotspot_count": len(frustration_hotspots)})

        # 9B: Category suggestions (Unknown/Other only)
        uncategorized = [t for t in all_tickets if
                         t["issue_type"].lower() in ("unknown", "other", "") or
                         t["sub_issue_type"].lower() in ("unknown", "other", "")]
        self._emit("phase", f"CATEGORY ANALYSIS — {len(uncategorized)} uncategorized tickets")
        category_suggestions = self.categorize_tickets_batch(uncategorized)

        # 9B+: Build hygiene report from category suggestions
        hygiene_report: dict = {"total_unknown": len(uncategorized), "groups": []}
        if category_suggestions:
            groups: dict[str, list[dict]] = defaultdict(list)
            for s in category_suggestions:
                ticket = tickets_by_id.get(s.ticket_id, {})
                groups[s.suggested_issue_type].append({
                    "ticket_id": s.ticket_id,
                    "title": ticket.get("title", ""),
                    "company": ticket.get("company", ""),
                    "current_type": s.current_issue_type,
                    "suggested_sub": s.suggested_sub_issue,
                    "confidence": s.confidence,
                    "reason": s.reason,
                })
            hygiene_report["groups"] = sorted(
                [{"category": cat, "count": len(items), "tickets": items}
                 for cat, items in groups.items()],
                key=lambda x: -x["count"],
            )

        self._emit("result", f"Hygiene: {hygiene_report['total_unknown']} unknown, {len(hygiene_report.get('groups',[]))} reclassification groups")

        # 9C: Talking points
        self._emit("phase", "GENERATING GOVERNANCE TALKING POINTS")
        metrics_dict = dict(artifacts.headline_metrics) if artifacts else {}
        observations = artifacts.service_observations if artifacts else []
        actions = artifacts.priority_actions if artifacts else []

        company_data = []
        if artifacts and artifacts.company_table is not None and not artifacts.company_table.empty:
            company_data = artifacts.company_table.head(10).to_dict("records")

        talking_points = self.generate_talking_points(metrics_dict, observations, company_data)

        self._emit("result", f"Generated {len(talking_points)} talking points")

        # 9D: Executive summary
        self._emit("phase", "GENERATING EXECUTIVE SUMMARY" + (" (custom instructions)" if self.custom_instructions else ""))
        executive_summary = self.generate_executive_summary(
            metrics_dict, observations, actions,
            custom_instructions=self.custom_instructions,
        )

        self._emit("result", f"Executive summary: {len(executive_summary)} chars")

        # 9E: Anomaly narration
        anomaly_narratives = []
        if comparison_deltas:
            self._emit("phase", "ANOMALY DETECTION")
            significant_deltas = {k: v for k, v in comparison_deltas.items()
                                  if abs(v.get("pct", 0)) >= 10}
            if significant_deltas:
                anomaly_narratives = self.narrate_anomalies(significant_deltas, all_tickets[:20])

        self._emit("complete", f"Analysis complete: {self._calls_made} calls, {self._tokens_used} tokens")

        return AIAnalysisResult(
            sentiment=sentiment,
            sentiment_summary=sentiment_summary,
            category_suggestions=category_suggestions,
            executive_summary=executive_summary,
            anomaly_narratives=anomaly_narratives,
            frustration_hotspots=frustration_hotspots,
            frustration_by_type=frustration_by_type,
            hygiene_report=hygiene_report,
            talking_points=talking_points,
            calls_made=self._calls_made,
            tokens_used=self._tokens_used,
            errors=self._errors,
        )


def serialize_ai_results(result: AIAnalysisResult | None) -> dict:
    """Convert AI results to JSON-safe dict for the template."""
    if result is None:
        return {"has_ai": False}

    return {
        "has_ai": True,
        "calls_made": result.calls_made,
        "tokens_used": result.tokens_used,
        "errors": result.errors,
        # Sentiment (all results)
        "sentiment_summary": result.sentiment_summary,
        "sentiment_all": [
            {"id": s.ticket_id, "score": s.sentiment, "indicators": ", ".join(s.indicators)}
            for s in result.sentiment
        ],
        # Frustration hotspots
        "frustration_hotspots": result.frustration_hotspots[:15],
        "frustration_by_type": result.frustration_by_type[:10],
        # Categories (with current type included)
        "category_suggestions": [
            {
                "id": c.ticket_id,
                "current": c.current_issue_type,
                "suggested": c.suggested_issue_type,
                "sub": c.suggested_sub_issue,
                "confidence": c.confidence,
                "reason": c.reason,
            }
            for c in result.category_suggestions
        ],
        "category_count": len(result.category_suggestions),
        # Data hygiene report
        "hygiene_report": result.hygiene_report,
        # Governance talking points
        "talking_points": result.talking_points,
        # Executive summary
        "executive_summary": result.executive_summary,
        # Anomaly narratives
        "anomaly_narratives": result.anomaly_narratives,
    }
