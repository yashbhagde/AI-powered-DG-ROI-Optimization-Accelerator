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

    async def calculate_documentation_score_async(self, asset: CanonicalAsset) -> float:
        """
        Calculates documentation score between 0 and 100 asynchronously.
        Uses Gemini API if available to semantically score documentation completeness.
        """
        if not asset.description or not asset.description.strip():
            score = 0.0
        elif self.use_gemini:
            try:
                await self.rate_limiter.check_and_throttle(estimated_tokens=350)
                from google.genai import types
                prompt = f"""
                You are a Data Governance metadata evaluator. Analyze the metadata of the following data asset and rate its documentation completeness, semantic utility, and technical clarity on a scale of 0 to 100.

                Asset Name: {asset.name}
                Asset Type: {asset.asset_type}
                Description: {asset.description}
                Owners: {[o.name for o in asset.owners]}
                Glossary Terms: {asset.glossary_terms}
                Classifications: {asset.classifications}

                Scoring Guidelines (0-100):
                - 80-100: Excellent documentation. The description clearly explains business purpose, context, owners are documented, and key glossary terms/classifications are aligned.
                - 50-79: Partially documented. Vague or short description, or missing owners/glossary linkages.
                - 0-49: Poorly documented. Empty description, obvious placeholder, or lacks any context and ownership metadata.

                Return ONLY a JSON object with keys:
                - "score": integer between 0 and 100
                - "reason": a short explanation of the score

                JSON:
                """
                response = await self.client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                data = json.loads(response.text)
                score = float(data.get("score", 0.0))
                score = max(0.0, min(100.0, score))
                print(f"[Gemini API] Evaluated documentation for '{asset.name}': {score}/100 (Reason: {data.get('reason')})")
            except Exception as e:
                print(f"[Gemini API Exception] Falling back to rule-based heuristics for '{asset.name}': {e}")
                # Fallback heuristic
                score = 40.0 + (10.0 if len(asset.description.strip()) > 50 else 0.0)
                if asset.owners:
                    score += 30.0
                if asset.glossary_terms:
                    score += 20.0
        else:
            # Fallback heuristic
            score = 40.0 + (10.0 if len(asset.description.strip()) > 50 else 0.0)
            if asset.owners:
                score += 30.0
            if asset.glossary_terms:
                score += 20.0

        return score

    def calculate_documentation_score(self, asset: CanonicalAsset) -> float:
        # Fallback wrapper for synchronous usage if called directly
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
        """
        Calculates a security/privacy/policy risk score between 0 and 100 (where 100 is highest risk) asynchronously.
        Uses Gemini API if available to perform context-aware classification and risk scoring.
        """
        if self.use_gemini:
            try:
                await self.rate_limiter.check_and_throttle(estimated_tokens=350)
                from google.genai import types
                prompt = f"""
                You are a Data Compliance and Risk Officer. Analyze the metadata of the following data asset and rate its security, privacy, and compliance risk on a scale of 0 to 100 (where 100 is highest risk). Also identify if it contains sensitive data (PII, PHI, PCI, or Confidential information).

                Asset Name: {asset.name}
                Asset Type: {asset.asset_type}
                Description: {asset.description}
                Current Classifications: {asset.classifications}
                Has Owners: {len(asset.owners) > 0} (Owners: {[o.name for o in asset.owners]})
                Data Quality Pass Rate: {asset.data_quality.pass_rate if asset.data_quality.rules_run > 0 else "N/A (No rules run)"}
                Lineage: {len(asset.lineage.upstream_assets)} upstream / {len(asset.lineage.downstream_assets)} downstream assets

                Scoring Guidelines (0-100):
                - 70-100 (High Risk): Contains sensitive data (PII, PHI, financial records) but lacks ownership, proper classifications, or data quality rules.
                - 30-69 (Medium Risk): Contains sensitive data but is well-governed (has owner and high DQ pass rate), OR is non-sensitive but completely unowned and unmonitored.
                - 0-29 (Low Risk): Non-sensitive, well-documented, owned, and actively monitored asset.

                Return ONLY a JSON object with keys:
                - "is_sensitive": boolean
                - "sensitive_type": string or null (e.g. "PII", "PHI", "PCI", "Confidential")
                - "risk_score": integer between 0 and 100
                - "reason": a short explanation of the score and sensitivity assessment

                JSON:
                """
                response = await self.client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.0
                    )
                )
                data = json.loads(response.text)
                is_sensitive = bool(data.get("is_sensitive", False))
                # Add classification dynamically if it is sensitive
                if is_sensitive and data.get("sensitive_type"):
                    sens_type = data.get("sensitive_type")
                    if sens_type not in asset.classifications:
                        asset.classifications.append(sens_type)
                
                risk = float(data.get("risk_score", 0.0))
                risk = max(0.0, min(100.0, risk))
                print(f"[Gemini API] Evaluated risk for '{asset.name}': {risk}/100 (Reason: {data.get('reason')})")
                return risk
            except Exception as e:
                print(f"[Gemini API Exception] Risk check fallback for '{asset.name}': {e}")
                
        # Heuristic fallback if Gemini is not used or API call fails
        is_sensitive = False
        sensitive_keywords = ["ssn", "payroll", "salary", "bank", "credit", "phone", "email", "address", "tax", "pii", "phi"]
        for c in asset.classifications:
            if any(term in c.lower() for term in ["pii", "phi", "confidential", "restricted", "sensitive"]):
                is_sensitive = True
                break
        name_desc = (asset.name + " " + asset.description).lower()
        if any(keyword in name_desc for keyword in sensitive_keywords):
            is_sensitive = True
            
        risk = 0.0
        if is_sensitive:
            risk += 20.0  # Base risk for holding sensitive data
            
            if not asset.owners:
                risk += 40.0
                
            # Check if it has explicit tags
            if not asset.classifications:
                risk += 20.0
                
            if asset.data_quality.rules_run == 0:
                risk += 20.0
            elif asset.data_quality.pass_rate < 0.8:
                risk += 15.0
        else:
            # Non-sensitive asset risk
            if not asset.owners:
                risk += 15.0
            if asset.data_quality.rules_run == 0:
                risk += 10.0
                
        return min(risk, 100.0)

    def calculate_security_risk_score(self, asset: CanonicalAsset) -> float:
        # Fallback wrapper for synchronous usage if called directly
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

    async def score_asset_async(self, asset: CanonicalAsset) -> Dict[str, Any]:
        """Scores a single canonical asset asynchronously."""
        # Execute API requests concurrently for the same asset
        doc_score, risk_score = await asyncio.gather(
            self.calculate_documentation_score_async(asset),
            self.calculate_security_risk_score_async(asset)
        )
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

    def score_asset(self, asset: CanonicalAsset) -> Dict[str, Any]:
        # Fallback wrapper for synchronous single scoring
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.score_asset_async(asset))
        finally:
            loop.close()

    async def _score_all_assets_async(self, assets: List[CanonicalAsset]) -> List[Dict[str, Any]]:
        # Run all scoring tasks concurrently
        tasks = [self.score_asset_async(asset) for asset in assets]
        return await asyncio.gather(*tasks)

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
