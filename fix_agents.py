import os
import re

files_to_refactor = {
    "services/agents/theme_detection_agent.py": "theme_detector",
    "services/agents/cross_provider_reasoning_agent.py": "cross_provider_reasoning",
    "services/agents/synthesizer_agent.py": "synthesizer",
    "services/planning/insight_planner.py": "insight_planner",
    "services/ui/ui_agent.py": "ui_agent",
    "services/agents/section_generators/base_section_generator.py": "section_generator"
}

directory = "/Users/koustavsarkar/Documents/mba_projects/mcp-business"

for file_path, agent_name in files_to_refactor.items():
    full_path = os.path.join(directory, file_path)
    if not os.path.exists(full_path):
        continue
        
    with open(full_path, "r") as f:
        content = f.read()
        
    if "from services.llm.provider_router import ProviderRouter" in content:
        continue

    # 1. Add import
    content = content.replace("import httpx", "import httpx\nfrom services.llm.provider_router import ProviderRouter")
    
    # 2. Extract prompt variable parsing - this regex targets the data={} and httpx.post logic and replaces it.
    # Because each file might define `prompt = ...` right before `data = ...`, we don't want to delete `prompt = ...`.
    
    # Match the block starting from `data = {` up to `parsed = json.loads(content)` (or similar)
    pattern = r'data = \{[\s\S]*?try:\s+async with httpx\.AsyncClient\(\) as client:[\s\S]*?response = await client\.post\([\s\S]*?parsed = json\.loads\(content\)'
    
    replacement = f"""try:
            parsed = await ProviderRouter.generate_json(
                agent_name="{agent_name}",
                system_prompt=system_instruction,
                user_prompt=prompt
            )"""
            
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(full_path, "w") as f:
            f.write(new_content)
        print(f"Refactored {file_path}")
    else:
        print(f"Pattern not found in {file_path}")
