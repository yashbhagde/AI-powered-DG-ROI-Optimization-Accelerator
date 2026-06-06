from typing import List, Dict, Any, Optional
import os
import json
import pandas as pd
import time
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from canonical_metadata_model import CanonicalAsset

# Load environment variables
load_dotenv()

class APIRateLimiter:
    def __init__(self, rpm_limit=600, tpm_limit=600000, rpd_limit=6000, cache_file=".rate_limit_cache.json"):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit
        self.cache_file = cache_file
        
        # In-memory tracking for sliding windows
        self.request_times = []
        self.token_history = []  # List of tuples: (timestamp, token_count)
        self._lock = asyncio.Lock()  # Ensure async lock for concurrent checks
        
        # Load persistent daily request counter
        self.daily_requests = self._load_daily_requests()

    def _load_daily_requests(self) -> List[str]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                cutoff = datetime.now() - timedelta(days=1)
                valid_times = []
                for ts_str in data.get("daily_requests", []):
                    ts = datetime.fromisoformat(ts_str)
                    if ts > cutoff:
                        valid_times.append(ts.isoformat())
                return valid_times
            except:
                return []
        return []

    def _save_daily_requests(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump({"daily_requests": self.daily_requests}, f)
        except:
            pass

    async def check_and_throttle(self, estimated_tokens=350):
        async with self._lock:
            now = datetime.now()
            now_ts = now.timestamp()
            
            # 1. Check RPD (Requests Per Day)
            cutoff_24h = now - timedelta(days=1)
            self.daily_requests = [ts for ts in self.daily_requests if datetime.fromisoformat(ts) > cutoff_24h]
            if len(self.daily_requests) >= self.rpd_limit:
                raise RuntimeError(f"RateLimiter: 60% Daily Request Quota ({self.rpd_limit}) exceeded.")

            # 2. Check RPM (Requests Per Minute)
            self.request_times = [t for t in self.request_times if now_ts - t < 60]
            if len(self.request_times) >= self.rpm_limit:
                wait_time = 60 - (now_ts - self.request_times[0])
                if wait_time > 0:
                    print(f"[RateLimiter] Approaching 60% RPM threshold. Pausing execution for {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    now_ts = time.time()
                    self.request_times = [t for t in self.request_times if now_ts - t < 60]

            # 3. Check TPM (Tokens Per Minute)
            self.token_history = [(t, count) for (t, count) in self.token_history if now_ts - t < 60]
            current_tpm = sum(count for (_, count) in self.token_history)
            if current_tpm + estimated_tokens >= self.tpm_limit:
                wait_time = 60 - (now_ts - self.token_history[0][0])
                if wait_time > 0:
                    print(f"[RateLimiter] Approaching 60% TPM threshold ({current_tpm} tokens). Pausing execution for {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    now_ts = time.time()
                    self.token_history = [(t, count) for (t, count) in self.token_history if now_ts - t < 60]

            # Log this request
            self.request_times.append(now_ts)
            self.token_history.append((now_ts, estimated_tokens))
            self.daily_requests.append(datetime.now().isoformat())
            self._save_daily_requests()

class GovernanceScoringEngine:
    def __init__(self, doc_weight: float = 0.3, dq_weight: float = 0.4, lineage_weight: float = 0.2, risk_weight: float = 0.1):
        self.doc_weight = doc_weight
        self.dq_weight = dq_weight
        self.lineage_weight = lineage_weight
        self.risk_weight = risk_weight
        
        # Verify weights sum to 1.0 (approximately)
        assert abs(doc_weight + dq_weight + lineage_weight + risk_weight - 1.0) < 1e-5, "Weights must sum to 1.0"
        
        # Initialize Gemini Client if API key is provided
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            print(f"Loaded Gemini key prefix: {self.api_key[:12]}")
        else:
            print("No Gemini key loaded")
        self.use_gemini = False
        
        # 60% Throttling Limits
        self.rate_limiter = APIRateLimiter(rpm_limit=600, tpm_limit=600000, rpd_limit=6000)
        
        if self.api_key and self.api_key.strip() and self.api_key != "YOUR_GEMINI_API_KEY":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                self.use_gemini = True
                
                # Verify credits and billing status before scheduling concurrent calls
                try:
                    self.client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents='Ping',
                    )
                    print("[Gemini API] Successfully validated Gemini client for cognitive scoring.")
                except Exception as val_err:
                    print(f"[Gemini API Warning] Key validation failed (credit/billing issue): {val_err}")
                    print("[Gemini API Warning] Instantly falling back to rule-based heuristics to prevent slow retry delays.")
                    self.use_gemini = False
            except ImportError:
                print("[Gemini API] google-genai is not installed. Falling back to rule-based heuristics.")
            except Exception as e:
                print(f"[Gemini API] Error initializing client: {e}. Falling back to rule-based heuristics.")

    def score_asset_heuristics(self, asset: CanonicalAsset) -> Dict[str, Any]:
        """Calculates documentation and security risk scores using rule-based heuristics."""
        # 1. Documentation Score Heuristic
        doc_score = 40.0 + (10.0 if asset.description and len(asset.description.strip()) > 50 else 0.0)
        if asset.owners:
            doc_score += 30.0
        if asset.glossary_terms:
            doc_score += 20.0
        doc_score = min(doc_score, 100.0)

        # 2. Security Risk Score Heuristic
        is_sensitive = False
        sensitive_keywords = ["ssn", "payroll", "salary", "bank", "credit", "phone", "email", "address", "tax", "pii", "phi"]
        for c in asset.classifications:
            if any(term in c.lower() for term in ["pii", "phi", "confidential", "restricted", "sensitive"]):
                is_sensitive = True
                break
        name_desc = ((asset.name or "") + " " + (asset.description or "")).lower()
        if any(keyword in name_desc for keyword in sensitive_keywords):
            is_sensitive = True

        risk = 0.0
        if is_sensitive:
            risk += 20.0  # Base risk
            if not asset.owners:
                risk += 40.0
            if not asset.classifications:
                risk += 20.0
            if asset.data_quality.rules_run == 0:
                risk += 20.0
            elif asset.data_quality.pass_rate < 0.8:
                risk += 15.0
        else:
            if not asset.owners:
                risk += 15.0
            if asset.data_quality.rules_run == 0:
                risk += 10.0
        risk_score = min(risk, 100.0)

        dq_score = self.calculate_data_quality_score(asset)
        lineage_score = self.calculate_lineage_score(asset)
        ghi = self.calculate_governance_health_index(doc_score, dq_score, lineage_score, risk_score)

        return {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "source_platform": asset.source_platform,
            "documentation_score": doc_score,
            "data_quality_score": dq_score,
            "lineage_score": lineage_score,
            "security_risk_score": risk_score,
            "governance_health_index": ghi
        }

    async def calculate_documentation_score_async(self, asset: CanonicalAsset) -> float:
        res = await self.score_asset_async(asset)
        return res["documentation_score"]

    def calculate_documentation_score(self, asset: CanonicalAsset) -> float:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.calculate_documentation_score_async(asset))
        finally:
            loop.close()

    def calculate_data_quality_score(self, asset: CanonicalAsset) -> float:
        if asset.data_quality.rules_run == 0:
            return 0.0
        return asset.data_quality.pass_rate * 100.0

    def calculate_lineage_score(self, asset: CanonicalAsset) -> float:
        score = 0.0
        if asset.lineage.upstream_assets:
            score += 50.0
        if asset.lineage.downstream_assets:
            score += 50.0
        return score

    async def calculate_security_risk_score_async(self, asset: CanonicalAsset) -> float:
        res = await self.score_asset_async(asset)
        return res["security_risk_score"]

    def calculate_security_risk_score(self, asset: CanonicalAsset) -> float:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.calculate_security_risk_score_async(asset))
        finally:
            loop.close()

    def calculate_governance_health_index(self, doc_score: float, dq_score: float, lineage_score: float, risk_score: float) -> float:
        inverted_risk = 100.0 - risk_score
        ghi = (doc_score * self.doc_weight +
               dq_score * self.dq_weight +
               lineage_score * self.lineage_weight +
               inverted_risk * self.risk_weight)
        return ghi

    async def score_assets_batch_async(self, assets: List[CanonicalAsset]) -> List[Dict[str, Any]]:
        """Scores a batch of canonical assets concurrently using Gemini API."""
        if not self.use_gemini:
            return [self.score_asset_heuristics(asset) for asset in assets]

        try:
            batch_data = []
            for asset in assets:
                batch_data.append({
                    "asset_id": asset.asset_id,
                    "name": asset.name,
                    "asset_type": asset.asset_type,
                    "description": asset.description or "",
                    "owners": [o.name for o in asset.owners],
                    "glossary_terms": asset.glossary_terms,
                    "classifications": asset.classifications,
                    "rules_run": asset.data_quality.rules_run if asset.data_quality else 0,
                    "pass_rate": asset.data_quality.pass_rate if asset.data_quality else 0.0,
                    "upstream_count": len(asset.lineage.upstream_assets) if asset.lineage else 0,
                    "downstream_count": len(asset.lineage.downstream_assets) if asset.lineage else 0
                })

            prompt = f"""
            You are a Data Governance compliance officer and metadata auditor.
            Evaluate the following batch of data assets and return a score and assessment for each asset.
            
            For each asset, you must calculate:
            1. "documentation_score" (0-100):
               - 80-100: Excellent. Clear context, explain purpose, owners are documented, and key glossary terms/classifications are aligned.
               - 50-79: Partially documented. Vague/short description or missing ownership.
               - 0-49: Poorly documented. Empty, placeholder, or lacks any context.
            2. "is_sensitive" (boolean):
               - true if the asset contains sensitive/restricted/internal corporate, privacy, financial, PII, PHI, or PCI data.
            3. "sensitive_type" (string or null):
               - Type of sensitivity (e.g. "PII", "PHI", "PCI", "Confidential", or null if not sensitive).
            4. "security_risk_score" (0-100):
               - 70-100 (High Risk): Contains sensitive data but lacks ownership, tags, or validation rules.
               - 30-69 (Medium Risk): Contains sensitive data but is well-governed, OR is non-sensitive but completely unowned and unmonitored.
               - 0-29 (Low Risk): Non-sensitive, well-documented, owned, and actively monitored.
               
            Assets Batch:
            {json.dumps(batch_data, indent=2)}
            
            Return ONLY a JSON object with key "results" containing a list of objects, one for each asset in the same order. Each object must have:
            - "asset_id": string
            - "documentation_score": integer
            - "is_sensitive": boolean
            - "sensitive_type": string or null
            - "security_risk_score": integer
            - "doc_reason": short reason string
            - "risk_reason": short reason string
            """

            # Dynamic rate limiter check based on batch size
            await self.rate_limiter.check_and_throttle(estimated_tokens=500 + len(assets) * 100)
            from google.genai import types

            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )

            data = json.loads(response.text)
            results = data.get("results", [])
            results_map = {r["asset_id"]: r for r in results if "asset_id" in r}

            scored_assets = []
            for asset in assets:
                r = results_map.get(asset.asset_id)
                if r:
                    doc_score = max(0.0, min(100.0, float(r.get("documentation_score", 50.0))))
                    risk_score = max(0.0, min(100.0, float(r.get("security_risk_score", 50.0))))
                    is_sensitive = bool(r.get("is_sensitive", False))
                    sensitive_type = r.get("sensitive_type")

                    if is_sensitive and sensitive_type:
                        if sensitive_type not in asset.classifications:
                            asset.classifications.append(sensitive_type)

                    dq_score = self.calculate_data_quality_score(asset)
                    lineage_score = self.calculate_lineage_score(asset)
                    ghi = self.calculate_governance_health_index(doc_score, dq_score, lineage_score, risk_score)

                    print(f"[Gemini Batch API] Evaluated '{asset.name}': Doc={doc_score}/100, Risk={risk_score}/100 (Reason: {r.get('doc_reason')})")

                    scored_assets.append({
                        "asset_id": asset.asset_id,
                        "name": asset.name,
                        "asset_type": asset.asset_type,
                        "source_platform": asset.source_platform,
                        "documentation_score": doc_score,
                        "data_quality_score": dq_score,
                        "lineage_score": lineage_score,
                        "security_risk_score": risk_score,
                        "governance_health_index": ghi
                    })
                else:
                    scored_assets.append(self.score_asset_heuristics(asset))
            return scored_assets

        except Exception as e:
            print(f"[Gemini Batch API Exception] Falling back to heuristics for batch: {e}")
            return [self.score_asset_heuristics(asset) for asset in assets]

    async def score_asset_async(self, asset: CanonicalAsset) -> Dict[str, Any]:
        """Scores a single canonical asset asynchronously by wrapping it in a batch of 1."""
        results = await self.score_assets_batch_async([asset])
        return results[0]

    def score_asset(self, asset: CanonicalAsset) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.score_asset_async(asset))
        finally:
            loop.close()

    async def _score_all_assets_async(self, assets: List[CanonicalAsset], batch_size: int = 15) -> List[Dict[str, Any]]:
        """Splits assets into batches and scores them sequentially."""
        all_results = []
        for i in range(0, len(assets), batch_size):
            batch = assets[i:i + batch_size]
            batch_results = await self.score_assets_batch_async(batch)
            all_results.extend(batch_results)
        return all_results

    def score_all_assets(self, assets: List[CanonicalAsset]) -> pd.DataFrame:
        """Scores a list of assets concurrently using asyncio and returns a pandas DataFrame."""
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            scored_data = loop.run_until_complete(self._score_all_assets_async(assets))
        finally:
            loop.close()
        return pd.DataFrame(scored_data)

    def generate_platform_report(self, scored_df: pd.DataFrame) -> pd.DataFrame:
        if scored_df.empty:
            return pd.DataFrame()
            
        platform_report = scored_df.groupby("source_platform").agg(
            total_assets=("asset_id", "count"),
            avg_documentation=("documentation_score", "mean"),
            avg_data_quality=("data_quality_score", "mean"),
            avg_lineage=("lineage_score", "mean"),
            avg_security_risk=("security_risk_score", "mean"),
            avg_ghi=("governance_health_index", "mean")
        ).reset_index()
        
        return platform_report
