from .component_catalog import COMPONENT_CATALOG

class ComponentRegistry:
    def __init__(self):
        self.catalog = COMPONENT_CATALOG

    def get_component(self, name: str) -> dict:
        return self.catalog.get(name)

    def list_components(self) -> dict:
        return self.catalog

component_registry = ComponentRegistry()
