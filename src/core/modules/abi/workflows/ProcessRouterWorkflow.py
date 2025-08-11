"""Process Router Workflow - BFO AI Process Network Implementation.

This workflow implements the Process Router Service as an operational bridge between
intent mapping and agent selection, transforming AI from a model-selection problem
into a process-completion problem.
"""

from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from dataclasses import dataclass
from pydantic import Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from typing import List

from lib.abi.services.agent.beta.ProcessRouter import ProcessRouter


@dataclass
class ProcessRouterWorkflowConfiguration(WorkflowConfiguration):
    oxigraph_url: str = "http://localhost:7878"


class ProcessRouterWorkflow(Workflow):
    """Process Router Workflow implementing BFO AI Process Network."""
    
    __configuration: ProcessRouterWorkflowConfiguration
    __process_router: ProcessRouter
    
    def __init__(self, configuration: ProcessRouterWorkflowConfiguration):
        self.__configuration = configuration
        self.__process_router = ProcessRouter(oxigraph_url=configuration.oxigraph_url)
    
    def recommend_agents_for_process(self, user_request: str) -> str:
        """
        Recommend AI agents for a specific process based on BFO AI Process Network.
        
        This tool identifies the process from the user's request, maps it to required
        capabilities, and recommends the best AI agents for the task.
        
        Args:
            user_request: The user's request describing what they want to accomplish
            
        Returns:
            A formatted string with process analysis and agent recommendations
        """
        result = self.__process_router.recommend_agents_for_process(user_request)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error")
            suggestion = result.get("suggestion", "")
            return f"❌ **Process Analysis Failed**\n\n**Error:** {error_msg}\n\n**Suggestion:** {suggestion}"
        
        # Format the response
        process = result["process"]
        process_description = result["process_description"]
        complexity = result["complexity"]
        required_capabilities = result["required_capabilities"]
        recommendations = result["recommendations"]
        total_agents = result["total_agents_found"]
        
        response = f"""🤖 **Process Analysis: {process.title()}**

📋 **Process Details:**
• **Description:** {process_description}
• **Complexity:** {complexity.title()}
• **Required Capabilities:** {', '.join(required_capabilities)}

🎯 **Agent Recommendations ({total_agents} agents found):**

"""
        
        for i, rec in enumerate(recommendations[:5], 1):  # Top 5 recommendations
            agent_name = rec["agent_name"]
            capabilities = rec["matched_capabilities"]
            cost = rec["cost_per_million_tokens"]
            description = rec["description"]
            confidence = rec["confidence_score"]
            
            response += f"""{i}. **{agent_name}**
   💰 **Cost:** {cost}
   🎯 **Capabilities:** {', '.join(capabilities)}
   📝 **Description:** {description[:100]}{'...' if len(description) > 100 else ''}
   ⭐ **Confidence:** {confidence:.1f}

"""
        
        response += f"""
💡 **Next Steps:**
• Ask me to switch to any recommended agent: "use [agent name]"
• Get cost analysis: "analyze costs for {process}"
• Get more details about a specific agent

🔄 **Process-Driven Approach:** Instead of choosing agents, focus on your process - I'll find the best tools for the job!
"""
        
        return response
    
    def analyze_process_costs(self, process: str) -> str:
        """
        Analyze costs for agents that can handle a specific process.
        
        Args:
            process: The process to analyze costs for (e.g., "business proposal", "code generation")
            
        Returns:
            A formatted string with cost analysis
        """
        result = self.__process_router.get_process_costs(process)
        
        if not result.get("success", False):
            return f"❌ **Cost Analysis Failed**\n\n**Error:** {result.get('error', 'Unknown error')}"
        
        complexity = result["complexity"]
        agents = result["agents"]
        cost_summary = result["cost_summary"]
        
        response = f"""💰 **Cost Analysis: {process.title()}**

📊 **Process Details:**
• **Complexity:** {complexity.title()}
• **Total Agents:** {len(agents)}

"""
        
        if cost_summary.get("lowest_cost") is not None:
            response += f"""📈 **Cost Summary:**
• **Lowest Cost:** ${cost_summary['lowest_cost']:.2f}/1M tokens
• **Highest Cost:** ${cost_summary['highest_cost']:.2f}/1M tokens
• **Average Cost:** ${cost_summary['average_cost']:.2f}/1M tokens

"""
        
        response += "🎯 **Agent Cost Breakdown:**\n\n"
        
        for i, agent in enumerate(agents[:10], 1):  # Top 10 agents
            agent_name = agent["agent_name"]
            cost = agent["cost"]
            description = agent["description"]
            
            response += f"""{i}. **{agent_name}**
   💰 **Cost:** {cost}
   📝 **Description:** {description[:80]}{'...' if len(description) > 80 else ''}

"""
        
        response += """
💡 **Cost Optimization Tips:**
• For simple tasks, consider lower-cost agents
• For complex processes, balance cost vs. capability
• Use the process router to find the best value for your specific needs
"""
        
        return response
    
    def list_available_processes(self) -> str:
        """
        List all available processes that can be analyzed.
        
        Returns:
            A formatted string listing all available processes
        """
        processes = self.__process_router.process_capabilities
        
        response = """🔄 **Available Processes for Analysis**

The following processes can be analyzed for agent recommendations and cost analysis:

"""
        
        for process_name, process_info in processes.items():
            capabilities = [cap.value for cap in process_info.capabilities]
            response += f"""**{process_name.title()}**
• **Complexity:** {process_info.complexity.title()}
• **Capabilities:** {', '.join(capabilities)}
• **Description:** {process_info.description}

"""
        
        response += """💡 **Usage Examples:**
• "I want to create a business proposal" → Process: business proposal
• "Help me generate some code" → Process: code generation
• "I need to analyze some data" → Process: data analysis
• "Create an image for me" → Process: image generation

🎯 **Process-Driven Approach:** Focus on what you want to accomplish, not which agent to use!
"""
        
        return response
    
    def as_tools(self) -> List[BaseTool]:
        """Convert workflow methods to LangChain tools."""
        return [
            StructuredTool.from_function(
                func=self.recommend_agents_for_process,
                name="recommend_agents_for_process",
                description="Recommend AI agents for a specific process based on BFO AI Process Network. Use this when users want to accomplish a task but don't know which agent to use.",
                args_schema=ProcessRouterWorkflowParameters
            ),
            StructuredTool.from_function(
                func=self.analyze_process_costs,
                name="analyze_process_costs",
                description="Analyze costs for agents that can handle a specific process. Use this when users want cost information for a particular task.",
                args_schema=ProcessCostAnalysisParameters
            ),
            StructuredTool.from_function(
                func=self.list_available_processes,
                name="list_available_processes",
                description="List all available processes that can be analyzed. Use this when users want to know what processes are supported.",
                args_schema=ListProcessesParameters
            )
        ]
    
    def as_api(self, router: APIRouter) -> None:
        """Expose workflow as FastAPI endpoints."""
        router.add_api_route(
            "/process-router/recommend",
            self.recommend_agents_for_process,
            methods=["POST"],
            summary="Recommend agents for a process",
            description="Recommend AI agents for a specific process based on BFO AI Process Network"
        )
        
        router.add_api_route(
            "/process-router/costs",
            self.analyze_process_costs,
            methods=["POST"],
            summary="Analyze process costs",
            description="Analyze costs for agents that can handle a specific process"
        )
        
        router.add_api_route(
            "/process-router/processes",
            self.list_available_processes,
            methods=["GET"],
            summary="List available processes",
            description="List all available processes that can be analyzed"
        )


class ProcessRouterWorkflowParameters(WorkflowParameters):
    """Parameters for the recommend_agents_for_process tool."""
    user_request: str = Field(
        description="The user's request describing what they want to accomplish",
        examples=["I want to create a business proposal", "Help me generate some code", "I need to analyze data"]
    )


class ProcessCostAnalysisParameters(WorkflowParameters):
    """Parameters for the analyze_process_costs tool."""
    process: str = Field(
        description="The process to analyze costs for",
        examples=["business proposal", "code generation", "data analysis", "image generation"]
    )


class ListProcessesParameters(WorkflowParameters):
    """Parameters for the list_available_processes tool."""
    pass
