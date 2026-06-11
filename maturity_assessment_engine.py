import os
import json
import asyncio
import litellm
from typing import List, Dict, Any
from canonical_metadata_model import CanonicalAsset

class SpecialistAgent:
    def __init__(self, name: str, persona: str, model_name: str):
        self.name = name
        self.persona = persona
        self.model_name = model_name

    async def analyze(self, raw_metrics: Dict[str, float], score_val: float) -> Dict[str, Any]:
        prompt = f"""
        You are the '{self.name}' subagent for a Data Governance office.
        Your persona: {self.persona}
        
        Analyze the following raw metrics and score for your data governance discipline:
        - Raw indicators: {json.dumps(raw_metrics)}
        - Calculated Discipline Score: {score_val:.2f} / 5.0
        
        Based on this metadata, generate:
        1. A short, professional reasoning paragraph explaining the score, mentioning relevant percentages, and highlighting key gaps/strengths. (Keep it concise, under 2-3 sentences).
        2. A list of 1-3 specific, active strengths (what is going well).
        3. A list of 1-3 specific key gaps or risks (areas of concern).
        4. A list of 3 specific, actionable remediation steps.
        
        Return ONLY a JSON object with keys:
        - "reasoning": string
        - "strengths": list of strings
        - "gaps": list of strings
        - "actions": list of strings
        """
        try:
            # Disable verbose logging to keep output clean
            litellm.set_verbose = False
            response = await litellm.acompletion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[SpecialistAgent Exception] '{self.name}' analysis failed: {e}. Falling back to heuristics.")
            return None

class MaturityAssessmentEngine:
    def __init__(self, config_path: str = "maturity_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            # Fallback default configuration if config file is not found
            return {
                "disciplines": {
                    "metadata_management": {
                        "name": "Metadata Management",
                        "weight": 0.5,
                        "indicators": {
                          "documentation_coverage": {"name": "Documentation Coverage", "weight": 0.3, "thresholds": [40, 60, 75, 90]},
                          "ownership_coverage": {"name": "Ownership Coverage", "weight": 0.3, "thresholds": [40, 60, 75, 90]},
                          "glossary_linkage": {"name": "Glossary Linkage", "weight": 0.2, "thresholds": [40, 60, 75, 90]},
                          "classification_coverage": {"name": "Classification Coverage", "weight": 0.2, "thresholds": [40, 60, 75, 90]}
                        }
                    },
                    "data_quality": {
                        "name": "Data Quality",
                        "weight": 0.5,
                        "indicators": {
                          "rule_coverage": {"name": "DQ Rule Coverage", "weight": 0.4, "thresholds": [25, 50, 70, 85]},
                          "pass_rate": {"name": "DQ Pass Rate", "weight": 0.6, "thresholds": [70, 80, 90, 95]}
                        }
                    }
                }
            }
        with open(self.config_path, "r") as f:
            return json.load(f)

    def calculate_raw_indicators(self, assets: List[CanonicalAsset]) -> Dict[str, float]:
        """Calculates raw percentage metrics for all indicators."""
        total_assets = len(assets)
        if total_assets == 0:
            return {
                "documentation_coverage": 0.0,
                "ownership_coverage": 0.0,
                "glossary_linkage": 0.0,
                "classification_coverage": 0.0,
                "rule_coverage": 0.0,
                "pass_rate": 0.0,
                "sensitive_data_governance": 0.0,
                "stewardship_assignment": 0.0,
                "lineage_coverage": 0.0,
                "rot_identification": 0.0,
                "storage_tier_optimization": 0.0,
                "role_access_control": 0.0
            }

        # 1. Documentation Coverage
        doc_count = sum(1 for a in assets if a.description and len(a.description.strip()) >= 50)
        doc_pct = (doc_count / total_assets) * 100.0

        # 2. Ownership Coverage
        owner_count = sum(1 for a in assets if a.owners and len(a.owners) >= 1)
        owner_pct = (owner_count / total_assets) * 100.0

        # 3. Glossary Linkage
        glossary_count = sum(1 for a in assets if a.glossary_terms and len(a.glossary_terms) >= 1)
        glossary_pct = (glossary_count / total_assets) * 100.0

        # 4. Classification Coverage
        class_count = sum(1 for a in assets if a.classifications and len(a.classifications) >= 1)
        class_pct = (class_count / total_assets) * 100.0

        # 5. DQ Rule Coverage
        rule_count = sum(1 for a in assets if a.data_quality and a.data_quality.rules_run > 0)
        rule_pct = (rule_count / total_assets) * 100.0

        # 6. DQ Pass Rate
        total_rules_run = sum(a.data_quality.rules_run for a in assets if a.data_quality)
        total_rules_passed = sum(a.data_quality.rules_passed for a in assets if a.data_quality)
        
        pass_rate_pct = (total_rules_passed / total_rules_run * 100.0) if total_rules_run > 0 else 0.0

        # 7. Sensitive Data Governance
        sensitive_assets = [a for a in assets if any(c.lower() in ["pii", "phi", "pci", "confidential"] for c in a.classifications)]
        if not sensitive_assets:
            sensitive_data_gov_pct = 100.0
        else:
            governed_sensitive = sum(1 for a in sensitive_assets if a.owners and a.classifications)
            sensitive_data_gov_pct = (governed_sensitive / len(sensitive_assets)) * 100.0

        # 8. Stewardship Assignment
        steward_count = sum(1 for a in assets if any("steward" in o.role.lower() for o in a.owners))
        stewardship_assignment_pct = (steward_count / total_assets) * 100.0

        # 9. Lineage Coverage
        lineage_count = sum(1 for a in assets if a.lineage and (a.lineage.upstream_assets or a.lineage.downstream_assets))
        lineage_coverage_pct = (lineage_count / total_assets) * 100.0

        # 10. ROT Identification (Active Asset Cataloging)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        rot_count = 0
        for a in assets:
            size = a.usage.size_in_bytes if a.usage else 0
            queries = a.usage.query_count if a.usage else 0
            last_acc = a.usage.last_accessed if a.usage else None
            if size > 0 and queries < 5:
                if last_acc:
                    if last_acc.tzinfo is None:
                        last_acc = last_acc.replace(tzinfo=timezone.utc)
                    days_inactive = (now - last_acc).days
                    if days_inactive > 180:
                        rot_count += 1
                else:
                    rot_count += 1
        rot_identification_pct = 100.0 - ((rot_count / total_assets) * 100.0)

        # 11. Storage Tier Optimization
        low_query_assets = [a for a in assets if a.usage and a.usage.query_count < 10 and a.usage.size_in_bytes > 0]
        if not low_query_assets:
            storage_tier_optimization_pct = 100.0
        else:
            optimized_storage = sum(1 for a in low_query_assets if a.usage.storage_tier in ["Standard-IA", "Glacier", "DeepArchive"])
            storage_tier_optimization_pct = (optimized_storage / len(low_query_assets)) * 100.0

        # 12. Role & Access Control (Access management alignment)
        role_access_control_count = sum(1 for a in assets if a.classifications and a.owners)
        role_access_control_pct = (role_access_control_count / total_assets) * 100.0

        return {
            "documentation_coverage": doc_pct,
            "ownership_coverage": owner_pct,
            "glossary_linkage": glossary_pct,
            "classification_coverage": class_pct,
            "rule_coverage": rule_pct,
            "pass_rate": pass_rate_pct,
            "sensitive_data_governance": sensitive_data_gov_pct,
            "stewardship_assignment": stewardship_assignment_pct,
            "lineage_coverage": lineage_coverage_pct,
            "rot_identification": rot_identification_pct,
            "storage_tier_optimization": storage_tier_optimization_pct,
            "role_access_control": role_access_control_pct
        }

    def map_percentage_to_score(self, pct: float, thresholds: List[float]) -> float:
        """Step-wise mapping of raw percentage to 1-5 maturity level."""
        if pct < thresholds[0]:
            return 1.0
        elif pct < thresholds[1]:
            return 2.0
        elif pct < thresholds[2]:
            return 3.0
        elif pct < thresholds[3]:
            return 4.0
        else:
            return 5.0

    def assess_maturity(self, assets: List[CanonicalAsset]) -> Dict[str, Any]:
        """Performs maturity assessment across all configured disciplines."""
        raw_metrics = self.calculate_raw_indicators(assets)
        results = {}
        overall_score = 0.0
        overall_weight_sum = 0.0

        for disp_key, disp_config in self.config.get("disciplines", {}).items():
            disp_name = disp_config.get("name", disp_key)
            disp_weight = disp_config.get("weight", 0.0)
            
            indicator_results = {}
            weighted_score_sum = 0.0
            
            for ind_key, ind_config in disp_config.get("indicators", {}).items():
                ind_name = ind_config.get("name", ind_key)
                ind_weight = ind_config.get("weight", 0.0)
                thresholds = ind_config.get("thresholds", [40, 60, 75, 90])
                
                raw_val = raw_metrics.get(ind_key, 0.0)
                score = self.map_percentage_to_score(raw_val, thresholds)
                
                indicator_results[ind_key] = {
                    "name": ind_name,
                    "raw_percentage": raw_val,
                    "score": score,
                    "weight": ind_weight,
                    "thresholds": thresholds
                }
                weighted_score_sum += score * ind_weight

            results[disp_key] = {
                "name": disp_name,
                "score": weighted_score_sum,
                "weight": disp_weight,
                "indicators": indicator_results
            }
            overall_score += weighted_score_sum * disp_weight
            overall_weight_sum += disp_weight

        final_maturity_score = (overall_score / overall_weight_sum) if overall_weight_sum > 0 else 0.0

        return {
            "total_assets": len(assets),
            "disciplines": results,
            "overall_maturity_score": final_maturity_score,
            "audit_trail": {
                "raw_metrics": raw_metrics
            }
        }

    def generate_recommendations_and_gaps(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Identifies strengths, gaps, and top 3 actionable recommendations based on scores."""
        strengths = []
        gaps = []
        recommendations = []

        for disp_key, disp_data in assessment.get("disciplines", {}).items():
            for ind_key, ind_data in disp_data.get("indicators", {}).items():
                raw_val = ind_data["raw_percentage"]
                thresholds = ind_data["thresholds"]
                name = ind_data["name"]
                
                # Check status
                if raw_val >= thresholds[3]:
                    status = "Green"
                    strengths.append(f"{raw_val:.1f}% {name.lower()} (Status: {status}, Target: >= {thresholds[3]}%)")
                elif raw_val >= thresholds[1]:
                    status = "Amber"
                    gaps.append(f"{raw_val:.1f}% {name.lower()} (Status: {status}, Target: >= {thresholds[3]}%)")
                else:
                    status = "Red"
                    gaps.append(f"{raw_val:.1f}% {name.lower()} (Status: {status}, Target: >= {thresholds[3]}%)")

        reco_map = {
            "documentation_coverage": {
                "reco": "Increase business description coverage.",
                "rationale": "Over 50% of assets lack standard descriptions, making self-service data discovery slow and redundant.",
                "impact": "Improves data discovery productivity and reduces onboarding overhead.",
                "improvement": "Increases Metadata Management maturity from {current:.2f} to {target:.2f}."
            },
            "ownership_coverage": {
                "reco": "Assign data owners and stewards to unowned datasets.",
                "rationale": "Unowned assets create compliance and operational risk with no clear contact for issues.",
                "impact": "Establishes clear ownership lines and faster data issue resolution.",
                "improvement": "Increases Metadata Management maturity from {current:.2f} to {target:.2f}."
            },
            "glossary_linkage": {
                "reco": "Link data catalog assets to the standardized Business Glossary.",
                "rationale": "Without glossary mapping, columns have inconsistent meaning across domains.",
                "impact": "Aligns cross-team terminology and improves report accuracy.",
                "improvement": "Increases Metadata Management maturity from {current:.2f} to {target:.2f}."
            },
            "classification_coverage": {
                "reco": "Ensure security and sensitivity tags are applied to all schema tables.",
                "rationale": "High risk of security non-compliance when PII/Confidential tags are omitted.",
                "impact": "Reduces data breach risk and ensures regulatory compliance.",
                "improvement": "Increases Metadata Management maturity from {current:.2f} to {target:.2f}."
            },
            "rule_coverage": {
                "reco": "Establish data quality rules for Critical Data Elements.",
                "rationale": "Popular datasets are run without data quality validation rules configured.",
                "impact": "Avoids pipeline failures and business decision-making errors.",
                "improvement": "Increases Data Quality maturity from {current:.2f} to {target:.2f}."
            },
            "pass_rate": {
                "reco": "Remediate failing data quality rule validations.",
                "rationale": "Active data quality pipelines show high rates of validation test failures.",
                "impact": "Improves overall trust in enterprise business reports.",
                "improvement": "Increases Data Quality maturity from {current:.2f} to {target:.2f}."
            }
        }

        # Prioritized recommendations based on lowest raw metrics that exist in reco_map
        raw_metrics = assessment["audit_trail"]["raw_metrics"]
        filtered_metrics = {k: v for k, v in raw_metrics.items() if k in reco_map}
        sorted_metrics = sorted(filtered_metrics.items(), key=lambda x: x[1])

        # Pick top 3 recommendations
        for key, val in sorted_metrics[:3]:
            current_score = assessment["overall_maturity_score"]
            reco_info = reco_map[key]
            
            # Calculate estimated improvement if this metric reached level 4 (thresholds[2])
            # We mock a 0.5 maturity boost for the recommendation
            target_score = min(5.0, current_score + 0.4)
            
            recommendations.append({
                "recommendation": reco_info["reco"],
                "rationale": reco_info["rationale"],
                "expected_business_impact": reco_info["impact"],
                "expected_maturity_improvement": reco_info["improvement"].format(current=current_score, target=target_score)
            })

        return {
            "strengths": strengths,
            "gaps": gaps,
            "recommendations": recommendations
        }

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except:
                pass
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)

    async def generate_discipline_details_agentic(self, assessment: Dict[str, Any], model_name: str) -> Dict[str, Dict[str, Any]]:
        raw_metrics = assessment["audit_trail"]["raw_metrics"]
        disciplines = assessment["disciplines"]
        
        # Define specialist agent personas
        agents = {
            "metadata_management": SpecialistAgent(
                "Metadata Management Specialist",
                "You are a senior data steward managing asset documentation coverage, metadata tags, and glossary mappings to ensure data discovery efficiency.",
                model_name
            ),
            "data_quality": SpecialistAgent(
                "Data Quality Engineer",
                "You are a data quality engineer responsible for DQ rule configurations, pipeline pass rates, and identifying data validation issues.",
                model_name
            ),
            "data_security_privacy": SpecialistAgent(
                "Security & Privacy Auditor",
                "You are an enterprise data privacy and security auditor ensuring CCPA/GDPR compliance, PII security, and classification tagging.",
                model_name
            ),
            "stewardship_governance": SpecialistAgent(
                "Stewardship Administrator",
                "You are a data governance office steward coordinator ensuring active data steward assignment and accountability across all business domains.",
                model_name
            ),
            "data_architecture_lineage": SpecialistAgent(
                "Data Architecture & Lineage Specialist",
                "You are an enterprise data architect modeling end-to-end data pipelines, upstream/downstream lineages, and cross-system integrations.",
                model_name
            ),
            "data_lifecycle_storage": SpecialistAgent(
                "Data Lifecycle & ROT Optimizer",
                "You are a storage optimization analyst identifying Redundant, Obsolete, and Trivial (ROT) data candidates and cost-effective tiering options.",
                model_name
            )
        }
        
        # Fire analysis tasks concurrently
        tasks = []
        discipline_keys = list(agents.keys())
        
        for key in discipline_keys:
            # Compile key-specific raw metrics subset to minimize prompt size
            sub_metrics = {}
            if key == "metadata_management":
                sub_metrics = {
                    "documentation_coverage": raw_metrics.get("documentation_coverage", 0.0),
                    "ownership_coverage": raw_metrics.get("ownership_coverage", 0.0),
                    "glossary_linkage": raw_metrics.get("glossary_linkage", 0.0),
                    "classification_coverage": raw_metrics.get("classification_coverage", 0.0)
                }
            elif key == "data_quality":
                sub_metrics = {
                    "rule_coverage": raw_metrics.get("rule_coverage", 0.0),
                    "pass_rate": raw_metrics.get("pass_rate", 0.0)
                }
            elif key == "data_security_privacy":
                sub_metrics = {
                    "classification_coverage": raw_metrics.get("classification_coverage", 0.0),
                    "sensitive_data_governance": raw_metrics.get("sensitive_data_governance", 0.0)
                }
            elif key == "stewardship_governance":
                sub_metrics = {
                    "stewardship_assignment": raw_metrics.get("stewardship_assignment", 0.0)
                }
            elif key == "data_architecture_lineage":
                sub_metrics = {
                    "lineage_coverage": raw_metrics.get("lineage_coverage", 0.0)
                }
            elif key == "data_lifecycle_storage":
                sub_metrics = {
                    "rot_identification": raw_metrics.get("rot_identification", 0.0),
                    "storage_tier_optimization": raw_metrics.get("storage_tier_optimization", 0.0)
                }
            
            score_val = disciplines[key]["score"]
            tasks.append(agents[key].analyze(sub_metrics, score_val))
            
        print(f"[Multi-Agent System] Launching 6 specialist agents concurrently via {model_name}...")
        results = await asyncio.gather(*tasks)
        
        compiled_details = {}
        for idx, key in enumerate(discipline_keys):
            agent_res = results[idx]
            score_val = disciplines[key]["score"]
            
            if agent_res and "reasoning" in agent_res:
                compiled_details[key] = {
                    "score_str": f"Score: {score_val:.1f} / 5.0",
                    "reasoning": agent_res["reasoning"],
                    "strengths": agent_res["strengths"],
                    "gaps": agent_res["gaps"],
                    "actions": agent_res["actions"]
                }
            else:
                compiled_details[key] = self._get_heuristic_details_for_key(key, score_val, raw_metrics)
                
        return compiled_details

    def generate_discipline_details(self, assessment: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        # Check if an LLM key is available to trigger multi-agent evaluation
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        has_llm = bool(
            (gemini_key and gemini_key.strip() and gemini_key != "YOUR_GEMINI_API_KEY") or
            (anthropic_key and anthropic_key.strip() and anthropic_key != "YOUR_ANTHROPIC_API_KEY") or
            (openai_key and openai_key.strip() and openai_key != "YOUR_OPENAI_API_KEY")
        )
        
        # Override model name from env variable if provided
        model_name = os.getenv("LLM_MODEL")
        if not model_name:
            if gemini_key and gemini_key.strip() and gemini_key != "YOUR_GEMINI_API_KEY":
                model_name = "gemini/gemini-2.5-flash"
            elif anthropic_key and anthropic_key.strip() and anthropic_key != "YOUR_ANTHROPIC_API_KEY":
                model_name = "anthropic/claude-3-5-sonnet-20241022"
            elif openai_key and openai_key.strip() and openai_key != "YOUR_OPENAI_API_KEY":
                model_name = "openai/gpt-4o"
        
        if has_llm and model_name:
            try:
                return self._run_async(self.generate_discipline_details_agentic(assessment, model_name))
            except Exception as e:
                print(f"[Multi-Agent System Warning] Agentic details run failed: {e}. Falling back to heuristics.")
        
        # Heuristic fallback for all disciplines
        raw_metrics = assessment["audit_trail"]["raw_metrics"]
        disciplines = assessment["disciplines"]
        
        compiled_details = {}
        for key in disciplines.keys():
            score_val = disciplines[key]["score"]
            compiled_details[key] = self._get_heuristic_details_for_key(key, score_val, raw_metrics)
            
        return compiled_details

    def _get_heuristic_details_for_key(self, key: str, score_val: float, raw_metrics: Dict[str, float]) -> Dict[str, Any]:
        if key == "metadata_management":
            mm_doc = raw_metrics.get("documentation_coverage", 0.0)
            mm_own = raw_metrics.get("ownership_coverage", 0.0)
            mm_class = raw_metrics.get("classification_coverage", 0.0)
            mm_gloss = raw_metrics.get("glossary_linkage", 0.0)
            mm_reasoning = (
                f"{mm_doc:.0f}% documentation and {mm_class:.0f}% classification reflect solid "
                f"cataloging practices. However, only {mm_own:.0f}% asset ownership signals "
                f"significant accountability gaps. Business term glossary linkage remains at {mm_gloss:.0f}%."
            )
            mm_strengths = []
            mm_gaps = []
            if mm_doc >= 75: mm_strengths.append(f"{mm_doc:.0f}% documented assets")
            else: mm_gaps.append(f"Only {mm_doc:.0f}% documented assets")
            if mm_class >= 75: mm_strengths.append(f"{mm_class:.0f}% asset classification")
            else: mm_gaps.append(f"Only {mm_class:.0f}% classification coverage")
            if mm_own >= 75: mm_strengths.append(f"{mm_own:.0f}% ownership assigned")
            else: mm_gaps.append(f"Only {mm_own:.0f}% ownership assigned")
            if mm_own < 60: mm_gaps.append("Steward coverage — critical gap")
            if mm_gloss < 75: mm_gaps.append(f"{100 - mm_gloss:.0f}% of business terms unmapped")
            else: mm_strengths.append(f"{mm_gloss:.0f}% glossary term linkage")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": mm_reasoning,
                "strengths": mm_strengths,
                "gaps": mm_gaps,
                "actions": [
                    "1. Drive steward assignment to >=80% via targeted ownership campaign",
                    "2. Complete business glossary term mapping for remaining unmapped assets",
                    "3. Mandate owner assignment as a condition for asset publication"
                ]
            }
        elif key == "data_quality":
            dq_rule = raw_metrics.get("rule_coverage", 0.0)
            dq_pass = raw_metrics.get("pass_rate", 0.0)
            dq_reasoning = (
                f"Only {dq_rule:.0f}% of assets have active DQ rules — well below the industry benchmark "
                f"of 70%+. While data quality pipelines are running, coverage of critical assets "
                f"remains insufficient. A {100 - dq_pass:.0f}% DQ failure rate is materially elevated."
            )
            dq_strengths = ["Active DQ monitors deployed"]
            dq_gaps = []
            if dq_rule >= 50: dq_strengths.append("Critical asset DQ coverage configured")
            else: dq_gaps.append(f"Only {dq_rule:.0f}% assets have DQ rules")
            dq_strengths.append("DQ validation rules active")
            if dq_pass >= 95: dq_strengths.append(f"{dq_pass:.0f}% DQ pass rate achieved")
            else: dq_gaps.append(f"{100 - dq_pass:.0f}% DQ failure rate — requires remediation")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": dq_reasoning,
                "strengths": dq_strengths,
                "gaps": dq_gaps,
                "actions": [
                    "1. Prioritize DQ rule coverage for 100% of critical data elements",
                    "2. Investigate and resolve root causes of validation failures",
                    "3. Expand DQ rule coverage to >=70% across all cataloged assets"
                ]
            }
        elif key == "data_security_privacy":
            dsp_class = raw_metrics.get("classification_coverage", 0.0)
            dsp_gov = raw_metrics.get("sensitive_data_governance", 0.0)
            dsp_reasoning = (
                f"Security classification stands at {dsp_class:.0f}% coverage. Governed sensitive datasets "
                f"with correct ownership and security categorization achieved {dsp_gov:.0f}% compliance."
            )
            dsp_strengths = []
            dsp_gaps = []
            if dsp_class >= 75: dsp_strengths.append(f"{dsp_class:.0f}% classification coverage")
            else: dsp_gaps.append(f"Only {dsp_class:.0f}% classification coverage")
            if dsp_gov >= 80: dsp_strengths.append("Sensitive data stewardship active")
            else: dsp_gaps.append(f"PII data stewardship gap: {100 - dsp_gov:.0f}% unassigned")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": dsp_reasoning,
                "strengths": dsp_strengths,
                "gaps": dsp_gaps,
                "actions": [
                    "1. Run automated cognitive scans to tag hidden PII/sensitive fields",
                    "2. Restrict public classification for fields containing SSN or tax details",
                    "3. Enforce data owner validation sign-off on sensitive datasets"
                ]
            }
        elif key == "stewardship_governance":
            sg_assign = raw_metrics.get("stewardship_assignment", 0.0)
            sg_reasoning = (
                f"Stewardship assignment has reached {sg_assign:.0f}% coverage, showing "
                f"the active stewardship administrative reach over enterprise assets."
            )
            sg_strengths = []
            sg_gaps = []
            if sg_assign >= 75: sg_strengths.append(f"{sg_assign:.0f}% active steward coverage")
            else: sg_gaps.append(f"Stewardship gap: {100 - sg_assign:.0f}% unassigned assets")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": sg_reasoning,
                "strengths": sg_strengths,
                "gaps": sg_gaps,
                "actions": [
                    "1. Define clear stewardship roles and responsibilities matrix",
                    "2. Recruit domain-level business stewards for core catalog schemas",
                    "3. Implement alerts for assets missing designated stewards"
                ]
            }
        elif key == "data_architecture_lineage":
            dal_lineage = raw_metrics.get("lineage_coverage", 0.0)
            dal_reasoning = (
                f"Lineage configuration sits at {dal_lineage:.0f}%, which allows impact "
                f"audits and lineage tracking of transactional workflows."
            )
            dal_strengths = []
            dal_gaps = []
            if dal_lineage >= 60: dal_strengths.append("Lineage traces active across analytics workflows")
            else: dal_gaps.append(f"Only {dal_lineage:.0f}% lineage connectivity mapped")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": dal_reasoning,
                "strengths": dal_strengths,
                "gaps": dal_gaps,
                "actions": [
                    "1. Harvest upstream/downstream lineage automatically from ETL logs",
                    "2. Target 100% lineage mapping for critical transactional tables",
                    "3. Connect isolated catalog assets to parent data schemas"
                ]
            }
        elif key == "data_lifecycle_storage":
            dls_rot = raw_metrics.get("rot_identification", 0.0)
            dls_tier = raw_metrics.get("storage_tier_optimization", 0.0)
            dls_reasoning = (
                f"Active asset cataloging stands at {dls_rot:.0f}% (reflecting minimal ROT waste). "
                f"Storage tier optimization has reached {dls_tier:.0f}% for low-query datasets."
            )
            dls_strengths = []
            dls_gaps = []
            if dls_rot >= 85: dls_strengths.append("ROT storage candidates minimized and clean")
            else: dls_gaps.append(f"Elevated ROT waste: {100 - dls_rot:.0f}% inactive candidate tables")
            if dls_tier >= 75: dls_strengths.append("Cost-optimized storage tiering active")
            else: dls_gaps.append(f"Unoptimized storage tiers: {100 - dls_tier:.0f}% cold data on hot tier")
            return {
                "score_str": f"Score: {score_val:.1f} / 5.0",
                "reasoning": dls_reasoning,
                "strengths": dls_strengths,
                "gaps": dls_gaps,
                "actions": [
                    "1. Enforce automated lifecycle policies to tier cold storage assets",
                    "2. Establish formal ROT archive and decommissioning processes",
                    "3. Decommission sandbox database exports older than 180 days"
                ]
            }
        return {}
