"""
Process Router Workflow

This module implements the BFO AI Process Network routing functionality.
It provides tools for process-driven agent recommendations and capability mapping.
"""

from typing import Dict, Any

from lib.abi.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
    StructuredTool,
)
from lib.abi.services.agent.beta.ProcessRouter import ProcessRouter


class ProcessRouterWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for the Process Router Workflow."""
    
    def __init__(self, name: str = "process_router"):
        super().__init__(name=name)


class ProcessRouterWorkflowParameters(WorkflowParameters):
    """Parameters for the Process Router Workflow."""
    
    def __init__(self, query: str):
        super().__init__()
        self.query = query


class ProcessRouterWorkflow(Workflow):
    """
    Process Router Workflow
    
    Provides process-driven routing capabilities for the BFO AI Process Network.
    Routes user queries to appropriate agents based on process requirements and capabilities.
    """
    
    def __init__(self, configuration: ProcessRouterWorkflowConfiguration):
        super().__init__(configuration)
        self.process_router = ProcessRouter()
        
        # Register tools
        self.register_tool(self._create_process_recommendation_tool())
    
    def _create_process_recommendation_tool(self) -> StructuredTool:
        """Create the process recommendation tool."""
        
        return StructuredTool(
            name="process_recommendation",
            description="Recommend AI agents and processes based on user query using BFO AI Process Network",
            func=self._recommend_processes,
            args_schema=ProcessRouterWorkflowParameters,
        )
    
    def _recommend_processes(self, parameters: ProcessRouterWorkflowParameters) -> Dict[str, Any]:
        """
        Recommend processes and agents based on user query.
        
        Args:
            parameters: Workflow parameters containing the user query
            
        Returns:
            Dictionary containing process recommendations and agent suggestions
        """
        try:
            # Use the ProcessRouter to get recommendations
            recommendations = self.process_router.route_process(parameters.query)
            
            return {
                "success": True,
                "query": parameters.query,
                "recommendations": recommendations,
                "message": f"Found {len(recommendations.get('agents', []))} suitable agents for your request."
            }
            
        except Exception as e:
            return {
                "success": False,
                "query": parameters.query,
                "error": str(e),
                "message": "Unable to process your request at this time."
            }
    
    def as_api(self, router, route_name: str = "process_router"):
        """Expose the workflow as FastAPI endpoints."""
        
        @router.post(f"/{route_name}/recommend")
        async def recommend_processes(query: str):
            """Recommend processes and agents for a given query."""
            parameters = ProcessRouterWorkflowParameters(query=query)
            return self._recommend_processes(parameters)
        
        @router.get(f"/{route_name}/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "process_router"}
