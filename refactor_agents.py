import os
import re

files_to_refactor = {
    "services/agents/event_extractor_agent.py": "event_extractor",
    "services/agents/theme_detection_agent.py": "theme_detector",
    "services/agents/cross_provider_reasoning_agent.py": "cross_provider_reasoning",
    "services/agents/synthesizer_agent.py": "synthesizer",
    "services/planning/insight_planner.py": "insight_planner",
    "services/ui/ui_agent.py": "ui_agent",
    "services/agents/section_generators/base_section_generator.py": "section_generator"
}

for file_path, agent_name in files_to_refactor.items():
    if not os.path.exists(file_path):
        continue
        
    with open(file_path, "r") as f:
        content = f.read()
        
    # Add ProviderRouter import if missing
    if "from services.llm.provider_router import ProviderRouter" not in content:
        content = content.replace("import httpx", "import httpx\nfrom services.llm.provider_router import ProviderRouter")
        
    # Replace the httpx post block
    httpx_pattern = r'data = \{.*?try:\s+async with httpx\.AsyncClient\(\) as client:.*?response = await client\.post\(.*?settings\.LLM_API_BASE,.*?json=data,.*?headers=headers,.*?timeout=.*?\)[\s\S]*?parsed = json\.loads\(content\)'
    
    replacement = f"""        try:
            parsed = await ProviderRouter.generate_json(
                agent_name="{agent_name}",
                system_prompt=system_instruction,
                user_prompt=prompt
            )"""
            
    # Also need to handle base_section_generator where the prompt variable is named differently or we just use regex
    # Wait, the regex might be too complex because of indentation and nested braces.
