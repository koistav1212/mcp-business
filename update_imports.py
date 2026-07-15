import os
import re

def update_imports():
    root = "services"
    
    # We will map old imports to new imports
    replacements = {
        "from services.research.models": "from services.schemas.insight",
        "import services.research.models": "import services.schemas.insight",
        "from services.planning.models": "from services.core.models",
        "from services.reports.models": "from services.schemas.report",
        "from services.ui.schemas": "from services.schemas.ui",
        "from services.research.ui_models": "from services.schemas.ui",
        "from services.models.research_execution_plan": "from services.core.models",
        "from services.models.planning_models": "from services.core.models",
    }
    
    for dirpath, _, filenames in os.walk(root):
        for file in filenames:
            if not file.endswith(".py"): continue
            filepath = os.path.join(dirpath, file)
            with open(filepath, "r") as f:
                content = f.read()
                
            original = content
            for old, new in replacements.items():
                content = content.replace(old, new)
                # also handle specific class imports if they were scattered, but python handles `from ... import X, Y`
                
            if original != content:
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"Updated imports in {filepath}")

if __name__ == "__main__":
    update_imports()
