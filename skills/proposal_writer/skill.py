from skills.base import BaseSkill

class ProposalWriterSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="proposal_writer", description="Writes proposals.")
