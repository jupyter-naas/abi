from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations import YourIntegration, YourIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field

@dataclass
class YourWorkflowConfiguration(WorkflowConfiguration):
    attribute_1 : str
    attribute_2 : int

class YourWorkflow(Workflow):
    __configuration: YourWorkflowConfiguration
    
    def __init__(self, configuration: YourWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__your_integration = YourIntegration(
            YourIntegrationConfiguration(attribute_1=self.__configuration.attribute_1, attribute_2=self.__configuration.attribute_2)
        )
    def run(self) -> str:

        # ... Add your code here
        
        return "Your result"
        

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.get("/your_endpoint")
    def your_endpoint():
        configuration = YourWorkflowConfiguration()
        workflow = YourWorkflow(configuration)
        return workflow.run()
    
    uvicorn.run(app, host="0.0.0.0", port=9877)  # Note: Using different port from github workflow

def main():
    
    configuration = YourWorkflowConfiguration(attribute_1="attribute_1", attribute_2=1)
    workflow = YourWorkflow(configuration)
    turtle = workflow.run()
    print(turtle)

def as_tool():
    from langchain_core.tools import StructuredTool
    
    def your_tool_function():
        configuration = YourWorkflowConfiguration(attribute_1="attribute_1", attribute_2=1)
        workflow = YourWorkflow(configuration)
        return workflow.run()
    
    
    class YourToolSchema(BaseModel):
        attribute_1: str = Field(..., description="The attribute_1 of the tool.")
        attribute_2: int = Field(..., description="The attribute_2 of the tool.")
    
    return StructuredTool(
        name="your_tool_name",
        description="Your tool description.",
        func=your_tool_function,
        args_schema=YourToolSchema
    )

if __name__ == "__main__":
    main()
