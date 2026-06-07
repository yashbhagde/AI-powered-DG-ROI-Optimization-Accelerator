from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class AssetOwner(BaseModel):
    name: str = Field(..., description="Name or identifier of the owner")
    role: str = Field(..., description="Role of the owner (e.g., Business Owner, Technical Owner, Steward)")
    email: Optional[str] = Field(None, description="Email address of the owner")

class DataQualitySummary(BaseModel):
    rules_run: int = Field(default=0, description="Total number of data quality rules executed")
    rules_passed: int = Field(default=0, description="Number of data quality rules that passed successfully")
    last_profiled: Optional[datetime] = Field(None, description="Timestamp of the last data profiling run")

    @property
    def pass_rate(self) -> float:
        if self.rules_run == 0:
            return 0.0
        return self.rules_passed / self.rules_run

class AssetLineage(BaseModel):
    upstream_assets: List[str] = Field(default_factory=list, description="IDs of direct upstream data assets")
    downstream_assets: List[str] = Field(default_factory=list, description="IDs of direct downstream data assets")

class UsageMetrics(BaseModel):
    query_count: int = Field(default=0, description="Number of times this asset was queried in the last 30 days")
    user_count: int = Field(default=0, description="Number of unique users who accessed this asset in the last 30 days")
    size_in_bytes: int = Field(default=0, description="Size of the asset in bytes (if applicable)")
    last_accessed: Optional[datetime] = Field(None, description="Timestamp of the last access/query")
    storage_tier: Optional[str] = Field("Standard", description="Cloud storage class (e.g., Standard, Infrequent, Glacier, DeepArchive)")
    query_compute_hours: Optional[float] = Field(0.0, description="Warehouse execution hours spent on this asset in the last 30 days")
    data_warehouse_size: Optional[str] = Field("X-Small", description="Snowflake/Databricks warehouse size (X-Small, Small, Medium, Large, etc.) used for queries")

class CanonicalAsset(BaseModel):
    asset_id: str = Field(..., description="Globally unique identifier for the asset in the canonical model")
    name: str = Field(..., description="Name of the asset")
    asset_type: str = Field(..., description="Type of asset (e.g., Table, Column, File, Dashboard)")
    source_platform: str = Field(..., description="Source governance vendor (alation, collibra, informatica_idmc, ataccama, purview)")
    source_id: str = Field(..., description="Vendor-specific original asset ID")
    description: str = Field(default="", description="Description of the asset")
    owners: List[AssetOwner] = Field(default_factory=list, description="List of business, technical, or steward owners")
    glossary_terms: List[str] = Field(default_factory=list, description="Associated business glossary term names")
    classifications: List[str] = Field(default_factory=list, description="Classification tags (e.g., PII, PHI, Confidential, Public)")
    data_quality: DataQualitySummary = Field(default_factory=DataQualitySummary, description="Summary of DQ rules and profile info")
    lineage: AssetLineage = Field(default_factory=AssetLineage, description="Upstream and downstream lineage connections")
    usage: UsageMetrics = Field(default_factory=UsageMetrics, description="Usage and popularity metrics")

import hashlib

def parse_date(date_val: Any) -> Optional[datetime]:
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val
    try:
        if isinstance(date_val, str):
            return datetime.fromisoformat(date_val.replace("Z", "+00:00"))
    except ValueError:
        pass
    return None

def get_deterministic_usage_metrics(asset_id: str, size_in_bytes: int, query_count: int) -> dict:
    """Generates consistent storage tier and compute hour metrics based on asset ID hash."""
    h = int(hashlib.md5(asset_id.encode('utf-8')).hexdigest(), 16)
    
    # 1. Determine storage tier
    if size_in_bytes == 0:
        storage_tier = "Standard"
    elif query_count < 5:
        tiers = ["Glacier", "DeepArchive", "Standard-IA"]
        storage_tier = tiers[h % len(tiers)]
    else:
        tiers = ["Standard", "Standard-IA"]
        storage_tier = tiers[h % len(tiers)]
        
    # 2. Determine query compute hours
    if query_count == 0:
        query_compute_hours = 0.0
    else:
        query_compute_hours = round(query_count * ((h % 10) + 1) * 0.005, 2)
        
    # 3. Determine data warehouse size
    if query_count > 1000:
        sizes = ["Large", "X-Large"]
        data_warehouse_size = sizes[h % len(sizes)]
    elif query_count > 200:
        sizes = ["Medium", "Large"]
        data_warehouse_size = sizes[h % len(sizes)]
    else:
        sizes = ["X-Small", "Small"]
        data_warehouse_size = sizes[h % len(sizes)]
        
    return {
        "storage_tier": storage_tier,
        "query_compute_hours": query_compute_hours,
        "data_warehouse_size": data_warehouse_size
    }

def map_alation_to_canonical(raw: Dict[str, Any]) -> CanonicalAsset:
    """Maps raw Alation table metadata to CanonicalAsset."""
    source_id = str(raw.get("id", ""))
    asset_id = f"alation_{source_id}"
    
    owners = []
    for steward in raw.get("stewards", []):
        owners.append(AssetOwner(
            name=steward.get("username", "Unknown"),
            role="Data Steward",
            email=steward.get("email")
        ))
        
    custom_fields = raw.get("custom_fields", {})
    classifications = []
    if custom_fields.get("PII") == "Yes" or custom_fields.get("Classification") == "Confidential":
        classifications.append("PII")
    elif custom_fields.get("PII") == "No" and custom_fields.get("Classification"):
        classifications.append(custom_fields.get("Classification"))
        
    glossary_terms = []
    if "Glossary Term" in custom_fields:
        term = custom_fields["Glossary Term"]
        if isinstance(term, list):
            glossary_terms.extend(term)
        else:
            glossary_terms.append(term)
            
    # Alation popularity values are typically 0-100 or query counts
    popularity = raw.get("popularity", 0)
    view_count = raw.get("view_count", 0)
    
    # Mock some data quality metrics since Alation displays them but integrates from other tools
    dq_raw = raw.get("data_quality", {})
    dq = DataQualitySummary(
        rules_run=dq_raw.get("rules_run", 0),
        rules_passed=dq_raw.get("rules_passed", 0),
        last_profiled=parse_date(dq_raw.get("last_profiled"))
    )

    det = get_deterministic_usage_metrics(asset_id, raw.get("size_in_bytes", 0), view_count)
    usage = UsageMetrics(
        query_count=view_count,
        user_count=int(popularity * 0.2) if popularity else 0, # approximation for popularity
        size_in_bytes=raw.get("size_in_bytes", 0),
        last_accessed=parse_date(raw.get("last_accessed")),
        storage_tier=raw.get("storage_tier", raw.get("custom_fields", {}).get("Storage Tier", det["storage_tier"])),
        query_compute_hours=float(raw.get("query_compute_hours", raw.get("custom_fields", {}).get("Query Compute Hours", det["query_compute_hours"]))),
        data_warehouse_size=raw.get("data_warehouse_size", raw.get("custom_fields", {}).get("Warehouse Size", det["data_warehouse_size"]))
    )
    
    lineage_raw = raw.get("lineage", {})
    lineage = AssetLineage(
        upstream_assets=lineage_raw.get("upstream", []),
        downstream_assets=lineage_raw.get("downstream", [])
    )

    return CanonicalAsset(
        asset_id=asset_id,
        name=raw.get("name", "Unnamed Asset"),
        asset_type=raw.get("type", "Table"),
        source_platform="alation",
        source_id=source_id,
        description=raw.get("description", ""),
        owners=owners,
        glossary_terms=glossary_terms,
        classifications=classifications,
        data_quality=dq,
        lineage=lineage,
        usage=usage
    )

def map_collibra_to_canonical(raw: Dict[str, Any]) -> CanonicalAsset:
    """Maps raw Collibra asset metadata to CanonicalAsset."""
    source_id = str(raw.get("id", ""))
    asset_id = f"collibra_{source_id}"
    
    description = ""
    classifications = []
    
    for attr in raw.get("attributes", []):
        attr_type = attr.get("type", "")
        attr_val = attr.get("value", "")
        if attr_type == "Description" or attr_type == "Definition":
            description = attr_val
        elif attr_type in ["Data Classification", "Security Level"]:
            classifications.append(attr_val)
            
    owners = []
    glossary_terms = []
    upstream = []
    downstream = []
    
    for rel in raw.get("relations", []):
        rel_type = rel.get("type", "")
        target = rel.get("target", "")
        role = rel.get("role", "Steward")
        
        if "owned by" in rel_type.lower() or "steward" in rel_type.lower() or role.endswith("Steward") or role.endswith("Owner"):
            owners.append(AssetOwner(
                name=target,
                role=role,
                email=rel.get("email")
            ))
        elif "glossary" in rel_type.lower() or "governed by term" in rel_type.lower():
            glossary_terms.append(target)
        elif "upstream" in rel_type.lower() or "feeds" in rel_type.lower() or "source" in rel_type.lower():
            upstream.append(target)
        elif "downstream" in rel_type.lower() or "fed by" in rel_type.lower() or "target" in rel_type.lower():
            downstream.append(target)
            
    dq_raw = raw.get("dataQuality", {})
    dq = DataQualitySummary(
        rules_run=dq_raw.get("rulesRun", 0),
        rules_passed=dq_raw.get("rulesPassed", 0),
        last_profiled=parse_date(dq_raw.get("lastProfiled"))
    )
    
    usage_raw = raw.get("usage", {})
    det = get_deterministic_usage_metrics(asset_id, usage_raw.get("sizeInBytes", 0), usage_raw.get("queryCount", 0))
    usage = UsageMetrics(
        query_count=usage_raw.get("queryCount", 0),
        user_count=usage_raw.get("userCount", 0),
        size_in_bytes=usage_raw.get("sizeInBytes", 0),
        last_accessed=parse_date(usage_raw.get("lastAccessed")),
        storage_tier=usage_raw.get("storageTier", det["storage_tier"]),
        query_compute_hours=float(usage_raw.get("queryComputeHours", det["query_compute_hours"])),
        data_warehouse_size=usage_raw.get("dataWarehouseSize", det["data_warehouse_size"])
    )

    return CanonicalAsset(
        asset_id=asset_id,
        name=raw.get("name", "Unnamed Asset"),
        asset_type=raw.get("type", "Table"),
        source_platform="collibra",
        source_id=source_id,
        description=description,
        owners=owners,
        glossary_terms=glossary_terms,
        classifications=classifications,
        data_quality=dq,
        lineage=AssetLineage(upstream_assets=upstream, downstream_assets=downstream),
        usage=usage
    )

def map_informatica_to_canonical(raw: Dict[str, Any]) -> CanonicalAsset:
    """Maps raw Informatica IDMC asset metadata to CanonicalAsset."""
    source_id = str(raw.get("assetId", ""))
    asset_id = f"informatica_{source_id}"
    
    owners = []
    for owner in raw.get("owners", []):
        owners.append(AssetOwner(
            name=owner.get("name", "Unknown Owner"),
            role=owner.get("role", "Data Owner"),
            email=owner.get("email")
        ))
        
    glossary_terms = [t.get("termName") for t in raw.get("glossaryAssignments", []) if t.get("termName")]
    
    classifications = []
    if raw.get("sensitive") or raw.get("isPII"):
        classifications.append("PII")
    if raw.get("classification"):
        classifications.append(raw.get("classification"))
        
    dq = DataQualitySummary(
        rules_run=raw.get("dqRulesCount", 0),
        rules_passed=raw.get("dqRulesPassed", 0),
        last_profiled=parse_date(raw.get("dqLastRun"))
    )
    
    lineage_raw = raw.get("lineageInfo", {})
    lineage = AssetLineage(
        upstream_assets=lineage_raw.get("upstream", []),
        downstream_assets=lineage_raw.get("downstream", [])
    )
    
    usage_raw = raw.get("usageStats", {})
    det = get_deterministic_usage_metrics(asset_id, usage_raw.get("sizeInBytes", 0), usage_raw.get("readsCount", 0))
    usage = UsageMetrics(
        query_count=usage_raw.get("readsCount", 0),
        user_count=usage_raw.get("usersCount", 0),
        size_in_bytes=usage_raw.get("sizeInBytes", 0),
        last_accessed=parse_date(usage_raw.get("lastAccessTime")),
        storage_tier=usage_raw.get("storageTier", det["storage_tier"]),
        query_compute_hours=float(usage_raw.get("queryComputeHours", det["query_compute_hours"])),
        data_warehouse_size=usage_raw.get("dataWarehouseSize", det["data_warehouse_size"])
    )

    return CanonicalAsset(
        asset_id=asset_id,
        name=raw.get("assetName", "Unnamed Asset"),
        asset_type=raw.get("assetType", "Table"),
        source_platform="informatica_idmc",
        source_id=source_id,
        description=raw.get("description", ""),
        owners=owners,
        glossary_terms=glossary_terms,
        classifications=classifications,
        data_quality=dq,
        lineage=lineage,
        usage=usage
    )

def map_ataccama_to_canonical(raw: Dict[str, Any]) -> CanonicalAsset:
    """Maps raw Ataccama metadata to CanonicalAsset."""
    source_id = str(raw.get("id", ""))
    asset_id = f"ataccama_{source_id}"
    
    owners = []
    if raw.get("owner"):
        owners.append(AssetOwner(
            name=raw.get("owner"),
            role="Data Owner",
            email=raw.get("owner") if "@" in raw.get("owner", "") else None
        ))
        
    glossary_terms = raw.get("terms", [])
    
    classifications = []
    sec_class = raw.get("securityClassification")
    if sec_class:
        classifications.append(sec_class)
        
    dq_raw = raw.get("dataQuality", {})
    dq = DataQualitySummary(
        rules_run=dq_raw.get("rulesRun", 0),
        rules_passed=dq_raw.get("rulesPassed", 0),
        last_profiled=parse_date(dq_raw.get("profiledDate"))
    )
    
    lineage_raw = raw.get("lineage", {})
    lineage = AssetLineage(
        upstream_assets=lineage_raw.get("sources", []),
        downstream_assets=lineage_raw.get("targets", [])
    )
    
    usage_raw = raw.get("usage", {})
    det = get_deterministic_usage_metrics(asset_id, raw.get("sizeBytes", 0), usage_raw.get("reads", 0))
    usage = UsageMetrics(
        query_count=usage_raw.get("reads", 0),
        user_count=usage_raw.get("users", 0),
        size_in_bytes=raw.get("sizeBytes", 0),
        last_accessed=parse_date(usage_raw.get("lastRead")),
        storage_tier=usage_raw.get("storageTier", raw.get("storage_tier", det["storage_tier"])),
        query_compute_hours=float(usage_raw.get("queryComputeHours", raw.get("query_compute_hours", det["query_compute_hours"]))),
        data_warehouse_size=usage_raw.get("dataWarehouseSize", raw.get("data_warehouse_size", det["data_warehouse_size"]))
    )

    return CanonicalAsset(
        asset_id=asset_id,
        name=raw.get("title", "Unnamed Asset"),
        asset_type=raw.get("type", "Table"),
        source_platform="ataccama",
        source_id=source_id,
        description=raw.get("description", ""),
        owners=owners,
        glossary_terms=glossary_terms,
        classifications=classifications,
        data_quality=dq,
        lineage=lineage,
        usage=usage
    )

def map_purview_to_canonical(raw: Dict[str, Any]) -> CanonicalAsset:
    """Maps raw Microsoft Purview asset metadata to CanonicalAsset."""
    source_id = str(raw.get("guid", ""))
    asset_id = f"purview_{source_id}"
    
    attributes = raw.get("attributes", {})
    name = raw.get("name") or attributes.get("name") or "Unnamed Asset"
    description = attributes.get("description", "")
    
    owners = []
    contacts = raw.get("contacts", {})
    for contact_role, contact_list in contacts.items():
        for contact in contact_list:
            owners.append(AssetOwner(
                name=contact.get("id", "Unknown"),
                role=f"Purview {contact_role}",
                email=contact.get("info")
            ))
            
    classifications = [c.get("typeName") for c in raw.get("classifications", []) if c.get("typeName")]
    glossary_terms = [m.get("displayText") for m in raw.get("meanings", []) if m.get("displayText")]
    
    dq_raw = raw.get("dataQuality", {})
    dq = DataQualitySummary(
        rules_run=dq_raw.get("rulesRun", 0),
        rules_passed=dq_raw.get("rulesPassed", 0),
        last_profiled=parse_date(dq_raw.get("lastProfiled"))
    )
    
    lineage_raw = raw.get("lineage", {})
    lineage = AssetLineage(
        upstream_assets=lineage_raw.get("inputs", []),
        downstream_assets=lineage_raw.get("outputs", [])
    )
    
    usage_raw = raw.get("usage", {})
    det = get_deterministic_usage_metrics(asset_id, attributes.get("sizeInBytes", 0), usage_raw.get("queries", 0))
    usage = UsageMetrics(
        query_count=usage_raw.get("queries", 0),
        user_count=usage_raw.get("users", 0),
        size_in_bytes=attributes.get("sizeInBytes", 0),
        last_accessed=parse_date(usage_raw.get("lastAccessed")),
        storage_tier=usage_raw.get("storageTier", attributes.get("storageTier", det["storage_tier"])),
        query_compute_hours=float(usage_raw.get("queryComputeHours", attributes.get("queryComputeHours", det["query_compute_hours"]))),
        data_warehouse_size=usage_raw.get("dataWarehouseSize", attributes.get("dataWarehouseSize", det["data_warehouse_size"]))
    )

    return CanonicalAsset(
        asset_id=asset_id,
        name=name,
        asset_type=raw.get("typeName", "Table"),
        source_platform="purview",
        source_id=source_id,
        description=description,
        owners=owners,
        glossary_terms=glossary_terms,
        classifications=classifications,
        data_quality=dq,
        lineage=lineage,
        usage=usage
    )

def map_raw_to_canonical(platform: str, raw: Dict[str, Any]) -> CanonicalAsset:
    """Orchestrates mapping from vendor-specific raw structures to the canonical schema."""
    plat_lower = platform.lower()
    if plat_lower == "alation":
        return map_alation_to_canonical(raw)
    elif plat_lower == "collibra":
        return map_collibra_to_canonical(raw)
    elif plat_lower in ["informatica", "informatica_idmc", "idmc"]:
        return map_informatica_to_canonical(raw)
    elif plat_lower == "ataccama":
        return map_ataccama_to_canonical(raw)
    elif plat_lower == "purview":
        return map_purview_to_canonical(raw)
    elif plat_lower in ["canonical", "generic", "standard"]:
        return CanonicalAsset.model_validate(raw)
    else:
        # Fallback: Try to parse directly as a CanonicalAsset if the structure matches
        try:
            return CanonicalAsset.model_validate(raw)
        except Exception:
            raise ValueError(
                f"Unsupported source platform: '{platform}'. "
                f"Please map to the canonical schema or ensure input matches CanonicalAsset structures."
            )
