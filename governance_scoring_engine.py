from typing import List, Dict, Any, Optional
import os
import json
import pandas as pd
import time
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import hashlib
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
        
        # Initialize LLM Client via LiteLLM with auto-routing based on API keys
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        # Override model name from env variable if provided
        self.model_name = os.getenv("LLM_MODEL")
        
        # If model is not explicitly provided, auto-detect based on active API keys
        if not self.model_name:
            if self.gemini_key and self.gemini_key.strip() and self.gemini_key != "YOUR_GEMINI_API_KEY":
                self.model_name = "gemini/gemini-2.5-flash"
            elif self.anthropic_key and self.anthropic_key.strip() and self.anthropic_key != "YOUR_ANTHROPIC_API_KEY":
                self.model_name = "anthropic/claude-3-5-sonnet-20241022"
            elif self.openai_key and self.openai_key.strip() and self.openai_key != "YOUR_OPENAI_API_KEY":
                self.model_name = "openai/gpt-4o"
            else:
                self.model_name = None
        
        self.use_llm = False
        
        # Verify provider and key configuration
        if self.model_name:
            has_valid_key = False
            if self.model_name.startswith("gemini/") and self.gemini_key:
                has_valid_key = True
            elif self.model_name.startswith("anthropic/") and self.anthropic_key:
                has_valid_key = True
            elif self.model_name.startswith("openai/") and self.openai_key:
                has_valid_key = True
            elif "/" in self.model_name:
                provider = self.model_name.split("/")[0].upper()
                if os.getenv(f"{provider}_API_KEY"):
                    has_valid_key = True
            else:
                # Standard model name without prefix fallback
                if "gpt" in self.model_name.lower() and self.openai_key:
                    has_valid_key = True
                    self.model_name = f"openai/{self.model_name}"
                elif "claude" in self.model_name.lower() and self.anthropic_key:
                    has_valid_key = True
                    self.model_name = f"anthropic/{self.model_name}"
                elif "gemini" in self.model_name.lower() and self.gemini_key:
                    has_valid_key = True
                    self.model_name = f"gemini/{self.model_name}"
            
            # Initialize default 60% Throttling Limits
            self.rate_limiter = APIRateLimiter(rpm_limit=600, tpm_limit=600000, rpd_limit=6000)
            
            if has_valid_key:
                try:
                    import litellm
                    litellm.set_verbose = False
                    
                    print(f"[LLM Router] Instantiating LiteLLM with model: {self.model_name}")
                    
                    # Dry-run validation check (max_tokens=2 to avoid heavy charges)
                    res = litellm.completion(
                        model=self.model_name,
                        messages=[{"role": "user", "content": "ping"}],
                        max_tokens=2
                    )
                    self.use_llm = True
                    print(f"[LLM Router] Successfully validated model '{self.model_name}' connection via LiteLLM.")
                    
                    # Dynamic rate limit discovery
                    try:
                        headers = {}
                        if hasattr(res, "_hidden_params") and isinstance(res._hidden_params, dict):
                            orig_resp = res._hidden_params.get("original_response")
                            if orig_resp and hasattr(orig_resp, "headers"):
                                headers = orig_resp.headers
                            elif "additional_headers" in res._hidden_params:
                                headers = res._hidden_params["additional_headers"]
                        
                        provider = self.model_name.split("/")[0] if "/" in self.model_name else "openai"
                        
                        # Default baseline limits (100%)
                        defaults = {
                            "anthropic": {"rpm": 1000, "tpm": 1000000},
                            "openai": {"rpm": 10000, "tpm": 2000000},
                            "gemini": {"rpm": 2000, "tpm": 4000000}
                        }
                        
                        rpm = defaults.get(provider, {}).get("rpm", 1000)
                        tpm = defaults.get(provider, {}).get("tpm", 1000000)
                        
                        # Override with headers if found
                        header_found = False
                        if provider == "anthropic" and headers:
                            for hk, hv in headers.items():
                                if hk.lower() == "anthropic-ratelimit-requests-limit":
                                    rpm = int(hv)
                                    header_found = True
                                elif hk.lower() == "anthropic-ratelimit-tokens-limit":
                                    tpm = int(hv)
                                    header_found = True
                        elif provider == "openai" and headers:
                            for hk, hv in headers.items():
                                if hk.lower() == "x-ratelimit-limit-requests":
                                    rpm = int(hv)
                                    header_found = True
                                elif hk.lower() == "x-ratelimit-limit-tokens":
                                    tpm = int(hv)
                                    header_found = True
                                    
                        # Apply 60% factor
                        self.rate_limiter.rpm_limit = int(rpm * 0.6)
                        self.rate_limiter.tpm_limit = int(tpm * 0.6)
                        self.rate_limiter.rpd_limit = int(self.rate_limiter.rpm_limit * 10)
                        
                        if header_found:
                            print(f"[RateLimiter] Dynamic Discovery SUCCESS: Detected {provider.upper()} rate limit headers. Configured to 60%: RPM={self.rate_limiter.rpm_limit}, TPM={self.rate_limiter.tpm_limit}")
                        else:
                            print(f"[RateLimiter] Dynamic Discovery: No rate limit headers present in response. Using provider defaults. Configured to 60%: RPM={self.rate_limiter.rpm_limit}, TPM={self.rate_limiter.tpm_limit}")
                    except Exception as parse_err:
                        print(f"[RateLimiter Warning] Rate limit discovery error: {parse_err}. Using default fallback limits.")
                except Exception as val_err:
                    print(f"[LLM Router Warning] Connection validation failed for '{self.model_name}': {val_err}")
                    print("[LLM Router Warning] Instantly falling back to rule-based heuristics to prevent slow retry delays.")
                    self.use_llm = False
            else:
                print(f"[LLM Router Warning] No API key found for model '{self.model_name}'. Falling back to heuristics.")
        else:
            print("[LLM Router] No LLM API key detected. Falling back to rule-based heuristics.")
            self.rate_limiter = APIRateLimiter(rpm_limit=600, tpm_limit=600000, rpd_limit=6000)
            
        # Alias self.use_gemini to self.use_llm to preserve backward compatibility
        self.use_gemini = self.use_llm
        
        # Client-side caching initialization
        self.cache_file = ".governance_score_cache.json"
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except:
            pass

    def _calculate_asset_hash(self, asset: CanonicalAsset) -> str:
        """Calculates a MD5 hash of the asset's metadata parameters to detect changes."""
        params = {
            "name": asset.name or "",
            "asset_type": asset.asset_type or "",
            "description": asset.description or "",
            "owners": sorted([o.name for o in asset.owners or []]),
            "glossary_terms": sorted(asset.glossary_terms or []),
            "classifications": sorted(asset.classifications or []),
            "rules_run": asset.data_quality.rules_run if asset.data_quality else 0,
            "pass_rate": asset.data_quality.pass_rate if asset.data_quality else 0.0
        }
        serialized = json.dumps(params, sort_keys=True)
        return hashlib.md5(serialized.encode('utf-8')).hexdigest()

    def score_asset_heuristics(self, asset: CanonicalAsset) -> Dict[str, Any]:
        """Calculates documentation and security risk scores using rule-based heuristics."""
        # 1. Documentation Score Heuristic
        doc_score = 0.0
        desc = asset.description.strip() if asset.description else ""
        if desc:
            placeholders = {"tbd", "todo", "test", "placeholder", "dummy", "n/a", "none", "will add"}
            is_placeholder = any(p in desc.lower() for p in placeholders)
            
            name_normalized = asset.name.lower().replace("_", "").replace(" ", "")
            desc_normalized = desc.lower().replace("_", "").replace(" ", "")
            is_just_name = name_normalized == desc_normalized
            
            words = [w for w in desc.lower().split() if len(w) > 1]
            has_enough_words = len(words) >= 3
            
            is_quality = not is_placeholder and not is_just_name and has_enough_words
            
            if is_quality:
                doc_score += 30.0
                doc_score += 10.0
                if len(desc) > 50:
                    doc_score += 10.0
            else:
                doc_score += 15.0
                if len(desc) > 50:
                    doc_score += 5.0
                    
        if asset.owners:
            doc_score += 20.0
            if len(asset.owners) > 1:
                doc_score += 10.0
                
        if asset.glossary_terms:
            doc_score += 10.0
            if len(asset.glossary_terms) > 4:
                doc_score += 10.0
                
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
            
        base_score = asset.data_quality.pass_rate * 100.0
        
        last_profiled = asset.data_quality.last_profiled
        if last_profiled is None:
            return base_score * 0.5
            
        from datetime import datetime
        if last_profiled.tzinfo:
            now = datetime.now(last_profiled.tzinfo)
        else:
            now = datetime.now()
            
        days_old = (now - last_profiled).days
        
        if days_old <= 7:
            penalty = 0.0
        elif days_old <= 30:
            penalty = 0.10
        else:
            penalty = 0.50
            
        return base_score * (1.0 - penalty)

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
            import litellm

            response = await litellm.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )

            response_text = response.choices[0].message.content
            data = json.loads(response_text)
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

    def get_asset_criticality_tier(self, asset: CanonicalAsset) -> int:
        """Determines the criticality tier of an asset (1 = Critical, 2 = Core, 3 = Local)."""
        if asset.usage.query_count >= 100 or asset.usage.user_count >= 10:
            return 1
        elif asset.usage.query_count >= 10 or asset.usage.user_count >= 3:
            return 2
        else:
            return 3

    def get_health_status(self, ghi: float, tier: int) -> str:
        """Determines if the GHI is sufficient for the asset's criticality tier."""
        if tier == 1:
            return "Healthy" if ghi >= 80.0 else "Action Needed"
        elif tier == 2:
            return "Healthy" if ghi >= 60.0 else "Action Needed"
        else:
            return "Healthy" if ghi >= 40.0 else "Action Needed"

    def score_asset(self, asset: CanonicalAsset) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(self.score_asset_async(asset))
        finally:
            loop.close()
            
        tier = self.get_asset_criticality_tier(asset)
        res["criticality_tier"] = tier
        res["health_status"] = self.get_health_status(res["governance_health_index"], tier)
        return res

    async def _score_all_assets_async(self, assets: List[CanonicalAsset], batch_size: int = 15) -> List[Dict[str, Any]]:
        """Splits assets into batches and scores them sequentially."""
        all_results = []
        for i in range(0, len(assets), batch_size):
            batch = assets[i:i + batch_size]
            batch_results = await self.score_assets_batch_async(batch)
            all_results.extend(batch_results)
        return all_results

    def score_all_assets(self, assets: List[CanonicalAsset]) -> pd.DataFrame:
        """Scores a list of assets, leveraging local cache for unchanged assets."""
        uncached_assets = []
        scored_data = []
        asset_hashes = {}

        # 1. Check cache for each asset
        for asset in assets:
            h = self._calculate_asset_hash(asset)
            asset_hashes[asset.asset_id] = h
            
            if h in self.cache:
                # Retrieve from cache
                cached_res = self.cache[h].copy()
                cached_res["asset_id"] = asset.asset_id
                cached_res["name"] = asset.name
                scored_data.append(cached_res)

            else:
                uncached_assets.append(asset)

        # 2. Evaluate uncached assets
        if uncached_assets:
            print(f"[Client Cache] Cache miss: Evaluated {len(uncached_assets)} / {len(assets)} assets using engine.")
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                new_scored_data = loop.run_until_complete(self._score_all_assets_async(uncached_assets))
            finally:
                loop.close()

            # Save newly scored assets to cache
            for res in new_scored_data:
                scored_data.append(res)
                h = asset_hashes.get(res["asset_id"])
                if h:
                    self.cache[h] = res
            self._save_cache()
        else:
            print(f"[Client Cache] Cache hit: All {len(assets)} assets loaded from local cache.")

        # Post-process all results to inject criticality tier and health status
        assets_map = {a.asset_id: a for a in assets}
        for res in scored_data:
            asset = assets_map.get(res["asset_id"])
            if asset:
                tier = self.get_asset_criticality_tier(asset)
                res["criticality_tier"] = tier
                res["health_status"] = self.get_health_status(res["governance_health_index"], tier)

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
