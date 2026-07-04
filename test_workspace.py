import os
import sys
import json
import asyncio
import shutil

sys.path.append("/Users/koustavsarkar/Documents/mba_projects/mcp-business")

from services.host.host_agent import HostAgent
from services.artifacts.artifact_manager import ArtifactManager

ARTIFACTS_DIR = "artifacts"
PROVIDER_OUTPUTS_DIR = os.path.join(ARTIFACTS_DIR, "provider_outputs")
FINAL_CONTEXT_PATH = os.path.join(ARTIFACTS_DIR, "final", "final_context.json")

COMPANY_PROMPTS = [
    "Analyse Nvidia",
]

def load_provider_evidence(prefix: str, company_key: str):
    if not os.path.exists(PROVIDER_OUTPUTS_DIR):
        return []
    files = [
        f for f in os.listdir(PROVIDER_OUTPUTS_DIR)
        if f.startswith(f"{prefix}_{company_key}")
    ]
    evidence = []
    for fname in files:
        with open(os.path.join(PROVIDER_OUTPUTS_DIR, fname), "r") as f:
            evidence.extend(json.load(f))
    return evidence

def validate_context(ctx: dict, company_name: str):
    print(f"\n=== Validation for {company_name} ===")

    # 1. Company entity present
    entity = ctx.get("entity", {})
    entity = ctx.get("entity") or {}
    core_entity = entity.get("entity") or {}
    print("Entity:", core_entity.get("name", "None"))
    assert entity, "Missing entity in final_context"
    assert core_entity.get("name"), "Missing name in entity"

    # 2. Company profile present
    profile = ctx.get("profile") or {}
    print("Profile name:", profile.get("name"))
    if not profile or not profile.get("overview"):
        print("Warning: Missing profile or overview. (Synthesizer LLM might have rate-limited and returned fallback)")

    # 3. News output present
    news = ctx.get("news") or []
    print(f"News articles count: {len(news)}")
    assert len(news) > 0, "No news output generated"

    # 4. Evidence graph nodes have confidence
    graph = ctx.get("evidence_graph") or {}
    nodes = graph.get("nodes") or []
    print(f"Evidence nodes count: {len(nodes)}")
    assert len(nodes) > 0, "No evidence graph nodes"
    
    for node in nodes:
        assert node.get("confidence", 0) > 0, f"Node {node.get('id')} has zero or missing confidence"
    # 5. Check Financials
    financials = ctx.get("financials") or {}
    print(f"Financials keys: {list(financials.keys())}")
    
    # 6. Check Analytics
    analytics = ctx.get("analytics") or {}
    print(f"Analytics available: {bool(analytics)}")

    print("Validation passed!")

async def main():
    for prompt in COMPANY_PROMPTS:
        print(f"\n### Running workspace for prompt: {prompt}")
        
        # Clear artifacts to avoid old data
        if os.path.exists(ARTIFACTS_DIR):
            shutil.rmtree(ARTIFACTS_DIR)
            
        ArtifactManager.initialize_workspace()
        
        agent = HostAgent()
        ctx = await agent.run(prompt)
        
        company_name = "Unknown"
        # Check files
        if os.path.exists(FINAL_CONTEXT_PATH):
            with open(FINAL_CONTEXT_PATH, "r") as f:
                saved_ctx = json.load(f)
                company_name = saved_ctx.get("entity", {}).get("company_name", "Unknown")
                validate_context(saved_ctx, company_name)
        else:
            print("ERROR: final_context.json not found!")

        company_ev = load_provider_evidence("company_evidence", company_name)
        print("Company evidence items:", len(company_ev))

        news_ev = load_provider_evidence("news_evidence", company_name.lower().replace(" ", "_"))
        print("News evidence items:", len(news_ev))

if __name__ == "__main__":
    asyncio.run(main())
