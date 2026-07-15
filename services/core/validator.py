import json
import logging
from typing import TypeVar, Type, Any, Dict, Optional
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("uvicorn.error")

T = TypeVar("T", bound=BaseModel)

class SchemaValidator:
    """
    A single robust validator that replaces over-engineered critic and verifier agents.
    It simply attempts to parse unstructured or partially structured dictionaries 
    into strict Pydantic schemas, raising or logging errors if it fails.
    """
    
    @classmethod
    def validate(cls, data: Any, schema_class: Type[T]) -> Optional[T]:
        """
        Attempts to coerce and validate `data` against `schema_class`.
        """
        if data is None:
            return None
            
        try:
            # If data is already an instance of the schema, return it
            if isinstance(data, schema_class):
                return data
                
            # If data is a string, try to parse it as JSON
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning(f"SchemaValidator: Failed to decode string as JSON for {schema_class.__name__}")
                    return None
                    
            # Use Pydantic's robust validation
            if isinstance(data, dict):
                return schema_class.model_validate(data)
            
            logger.warning(f"SchemaValidator: Data is neither dict nor string for {schema_class.__name__}")
            return None
            
        except ValidationError as e:
            logger.error(f"SchemaValidator: Validation failed for {schema_class.__name__}: {e}")
            return None
