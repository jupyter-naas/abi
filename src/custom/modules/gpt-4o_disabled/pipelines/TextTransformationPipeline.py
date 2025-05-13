from lib.abi.pipeline.pipeline import Pipeline
from typing import Dict, Any, List, Optional
from ..integrations.OpenAIGpt4oIntegration import OpenAIGpt4oIntegration

class TextTransformationPipeline(Pipeline):
    """A pipeline for text transformation using GPT-4o."""
    
    def __init__(self):
        """Initialize the pipeline."""
        super().__init__(
            name="text_transformation_pipeline",
            description="Pipeline for transforming text in various ways using GPT-4o"
        )
        self.integration = OpenAIGpt4oIntegration()
    
    def process(self, 
                input_text: str, 
                transformation_type: str = "summarize", 
                options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process the input text according to the specified transformation type.
        
        Args:
            input_text (str): The text to transform
            transformation_type (str): The type of transformation to apply. 
                Options: "summarize", "translate", "rephrase", "expand", "simplify"
            options (Optional[Dict[str, Any]]): Additional options for the transformation
                - target_language: For translations
                - target_length: For summarization or expansion
                - style: For rephrasing
        
        Returns:
            Dict[str, Any]: The transformed text and metadata
        """
        options = options or {}
        
        # Define the system prompt based on transformation type
        system_prompts = {
            "summarize": "You are a text summarization expert. Create a concise summary of the provided text while preserving all key information.",
            "translate": f"You are a professional translator. Translate the provided text into {options.get('target_language', 'French')} while preserving the original meaning and tone.",
            "rephrase": f"You are a language specialist. Rephrase the provided text in {options.get('style', 'a more professional')} style without changing its meaning.",
            "expand": "You are a content developer. Expand the provided text with additional relevant details and explanations while maintaining the original message.",
            "simplify": "You are a clarity expert. Simplify the provided text to make it more understandable to a general audience while maintaining all essential information."
        }
        
        system_prompt = system_prompts.get(transformation_type, system_prompts["summarize"])
        
        # Add any specific instructions from options
        if options.get("target_length"):
            system_prompt += f" The result should be approximately {options['target_length']} words."
        
        # Process the text with GPT-4o
        result = self.integration.create_chat_completion(
            prompt=input_text,
            system_prompt=system_prompt,
            temperature=0.3
        )
        
        # Return the transformed text and metadata
        return {
            "original_text": input_text,
            "transformed_text": result,
            "transformation_type": transformation_type,
            "options": options
        } 