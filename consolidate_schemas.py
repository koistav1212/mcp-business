import os
import re

research_models = open('services/research/models.py').read()
planning_models = open('services/planning/models.py').read()
reports_models = open('services/reports/models.py').read()

core_models = """from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime

# Consolidated core models
""" + planning_models

entity_models = """from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

# Extracted from research/models.py
"""
insight_models = """from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Any

# Extracted from research/models.py
"""
evidence_models = """from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal

# Extracted from research/models.py
"""
report_models = """from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

# Extracted from reports/models.py
""" + reports_models

ui_models = """from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

# Extracted from UI models
"""

os.makedirs('services/core', exist_ok=True)
os.makedirs('services/schemas', exist_ok=True)

with open('services/core/models.py', 'w') as f: f.write(core_models)
with open('services/schemas/entity.py', 'w') as f: f.write(entity_models)
with open('services/schemas/evidence.py', 'w') as f: f.write(evidence_models)
with open('services/schemas/insight.py', 'w') as f: f.write(insight_models)
with open('services/schemas/report.py', 'w') as f: f.write(report_models)
with open('services/schemas/ui.py', 'w') as f: f.write(ui_models)

print("Created schema stubs.")
