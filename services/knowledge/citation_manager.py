import uuid

class CitationManager:
    """
    Generates stable, repeatable evidence IDs for downstream reports to consume.
    e.g. sec_10k_aapl_2024
    """
    @staticmethod
    def generate_id(source: str, entity: str, attribute: str, freshness: str) -> str:
        base = f"{source}_{entity}_{attribute}_{freshness}".lower()
        # Clean up string
        clean_base = "".join(c if c.isalnum() else "_" for c in base)
        # remove double underscores
        while "__" in clean_base:
            clean_base = clean_base.replace("__", "_")
        
        # Add a short hash to ensure uniqueness even if metadata matches
        short_hash = uuid.uuid4().hex[:6]
        return f"{clean_base}_{short_hash}"
