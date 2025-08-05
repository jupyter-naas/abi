# Basic Browser Automation Examples

This document provides practical examples of how browser-use integration would work within the ABI framework.

## Simple Web Automation Agent

### Basic Setup Example

```python
# src/core/modules/browser/agents/WebAutomationAgent.py
from abi.services.agent.IntentAgent import IntentAgent, Intent, IntentType, AgentConfiguration
from browser_use import Agent as BrowserUseAgent
from browser_use.llm import ChatOpenAI
import asyncio

class WebAutomationAgent(IntentAgent):
    """AI agent with browser automation capabilities"""
    
    NAME = "WebAutomation"
    DESCRIPTION = "AI agent capable of browser automation and web interaction"
    
    SYSTEM_PROMPT = """
    You are a web automation specialist. You can:
    - Navigate to websites and interact with web pages
    - Extract data from web pages
    - Fill out forms and submit them
    - Take screenshots and capture page content
    - Perform multi-step web workflows
    
    Always respect website terms of service and implement appropriate delays.
    """
    
    def __init__(self):
        super().__init__(
            name=self.NAME,
            description=self.DESCRIPTION,
            configuration=AgentConfiguration(system_prompt=self.SYSTEM_PROMPT)
        )
        self.browser_agent = None
    
    async def initialize_browser(self):
        """Initialize browser automation capabilities"""
        self.browser_agent = BrowserUseAgent(
            task="Web automation assistant",
            llm=ChatOpenAI(model="gpt-4o"),
        )
    
    async def execute_web_task(self, task_description: str) -> str:
        """Execute a web automation task"""
        if not self.browser_agent:
            await self.initialize_browser()
        
        try:
            result = await self.browser_agent.run(task_description)
            return f"Web task completed successfully: {result}"
        except Exception as e:
            return f"Web task failed: {str(e)}"
    
    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser_agent:
            # Clean up browser session
            pass

def create_agent() -> WebAutomationAgent:
    """Factory function to create the WebAutomation agent"""
    return WebAutomationAgent()
```

### Integration with ABI Intent System

```python
# Extension to handle browser-specific intents
class WebAutomationAgent(IntentAgent):
    # ... previous code ...
    
    def __init__(self):
        super().__init__()
        
        # Add browser-specific intents
        self.intents.extend([
            Intent(
                intent_type=IntentType.TASK, 
                intent_value="browse to", 
                intent_target=self._handle_navigation
            ),
            Intent(
                intent_type=IntentType.TASK, 
                intent_value="extract data from", 
                intent_target=self._handle_data_extraction
            ),
            Intent(
                intent_type=IntentType.TASK, 
                intent_value="fill out form", 
                intent_target=self._handle_form_filling
            ),
            Intent(
                intent_type=IntentType.TASK, 
                intent_value="take screenshot", 
                intent_target=self._handle_screenshot
            ),
        ])
    
    async def _handle_navigation(self, user_input: str) -> str:
        """Handle navigation requests"""
        # Extract URL from user input
        url = self._extract_url_from_input(user_input)
        task = f"Navigate to {url} and describe what you see"
        return await self.execute_web_task(task)
    
    async def _handle_data_extraction(self, user_input: str) -> str:
        """Handle data extraction requests"""
        task = f"Extract the requested data: {user_input}"
        return await self.execute_web_task(task)
    
    async def _handle_form_filling(self, user_input: str) -> str:
        """Handle form filling requests"""
        task = f"Fill out the form as requested: {user_input}"
        return await self.execute_web_task(task)
    
    async def _handle_screenshot(self, user_input: str) -> str:
        """Handle screenshot requests"""
        task = f"Take a screenshot of the current page or specific element: {user_input}"
        return await self.execute_web_task(task)
```

## Example Use Cases

### 1. Web Research and Data Collection

```python
# Example conversation with ABI
user_query = "Browse to GitHub and find the most popular Python AI libraries"

# This would trigger the WebAutomationAgent to:
# 1. Navigate to github.com
# 2. Search for "Python AI libraries"
# 3. Sort by popularity/stars
# 4. Extract the top results
# 5. Return a structured summary

expected_response = """
I've browsed GitHub and found the most popular Python AI libraries:

1. **TensorFlow** (185k stars) - Google's machine learning framework
2. **PyTorch** (75k stars) - Facebook's deep learning framework  
3. **Scikit-learn** (58k stars) - Machine learning library for Python
4. **Transformers** (125k stars) - Hugging Face's NLP library
5. **OpenCV** (75k stars) - Computer vision library

Each library has strong community support and extensive documentation.
"""
```

### 2. E-commerce Price Comparison

```python
# Example conversation
user_query = "Compare prices for iPhone 15 Pro across Amazon, Best Buy, and Apple Store"

# WebAutomationAgent would:
# 1. Open multiple browser tabs
# 2. Navigate to each store
# 3. Search for iPhone 15 Pro
# 4. Extract prices and availability
# 5. Generate comparison report

expected_response = """
iPhone 15 Pro Price Comparison:

📱 **iPhone 15 Pro 128GB:**
- Apple Store: $999.00 (In stock)
- Amazon: $999.00 (In stock, Prime shipping)
- Best Buy: $999.00 (In stock, store pickup available)

📱 **iPhone 15 Pro 256GB:**
- Apple Store: $1,099.00 (In stock)
- Amazon: $1,099.00 (In stock)
- Best Buy: $1,099.00 (Limited stock)

💰 **Best Deal:** All retailers have the same MSRP pricing. 
Amazon offers free Prime shipping, Best Buy has store pickup option.
"""
```

### 3. Form Automation

```python
# Example conversation
user_query = "Fill out the contact form on example.com with my information"
user_data = {
    "name": "John Doe",
    "email": "john@example.com", 
    "message": "Interested in your services"
}

# WebAutomationAgent would:
# 1. Navigate to example.com
# 2. Locate the contact form
# 3. Fill in the provided information
# 4. Submit the form
# 5. Confirm successful submission

expected_response = """
✅ Contact form successfully submitted!

Form Details:
- Website: example.com
- Name: John Doe
- Email: john@example.com
- Message: "Interested in your services"
- Submission Time: 2025-01-15 10:30:00 UTC
- Confirmation: Form submitted successfully with reference #12345

The website confirmed receipt and mentioned they'll respond within 24 hours.
"""
```

### 4. Social Media Automation

```python
# Example conversation
user_query = "Post a LinkedIn update about our new product launch"
post_content = "Excited to announce the launch of ABI 2.0 with browser automation! 🚀"

# WebAutomationAgent would:
# 1. Navigate to LinkedIn
# 2. Go to post creation
# 3. Enter the post content
# 4. Add any media if specified
# 5. Publish the post

expected_response = """
📱 LinkedIn post published successfully!

Post Content: "Excited to announce the launch of ABI 2.0 with browser automation! 🚀"
Published: January 15, 2025 at 10:30 AM
Visibility: Public
Post URL: https://linkedin.com/posts/yourprofile_12345

The post is now live on your LinkedIn profile and has been shared with your network.
"""
```

## Advanced Multi-Step Workflows

### Example: Job Application Automation

```python
async def job_application_workflow(job_search_criteria: dict):
    """Complex workflow for automated job searching and application"""
    
    # Step 1: Search for jobs on multiple platforms
    jobs = await search_jobs_multi_platform(job_search_criteria)
    
    # Step 2: Filter and rank jobs based on criteria
    qualified_jobs = await filter_and_rank_jobs(jobs, job_search_criteria)
    
    # Step 3: For each qualified job, apply automatically
    application_results = []
    for job in qualified_jobs[:5]:  # Apply to top 5
        try:
            result = await apply_to_job(job)
            application_results.append(result)
            
            # Wait between applications to be respectful
            await asyncio.sleep(30)
            
        except Exception as e:
            application_results.append({
                "job": job,
                "status": "failed",
                "error": str(e)
            })
    
    return generate_application_report(application_results)

async def search_jobs_multi_platform(criteria: dict):
    """Search for jobs across LinkedIn, Indeed, and company websites"""
    platforms = [
        {"name": "LinkedIn", "url": "linkedin.com/jobs"},
        {"name": "Indeed", "url": "indeed.com"},
        {"name": "Glassdoor", "url": "glassdoor.com"}
    ]
    
    all_jobs = []
    for platform in platforms:
        jobs = await search_platform(platform, criteria)
        all_jobs.extend(jobs)
    
    return all_jobs

async def apply_to_job(job: dict):
    """Apply to a specific job posting"""
    # Navigate to job posting
    # Click "Apply" button
    # Fill out application form with pre-configured information
    # Upload resume and cover letter
    # Submit application
    # Capture confirmation
    pass
```

## Error Handling Examples

### Graceful Error Recovery

```python
class RobustWebAutomationAgent(WebAutomationAgent):
    """Web automation agent with enhanced error handling"""
    
    async def execute_web_task_with_retry(
        self, 
        task_description: str, 
        max_retries: int = 3
    ) -> str:
        """Execute web task with automatic retry on failure"""
        
        for attempt in range(max_retries):
            try:
                return await self.execute_web_task(task_description)
                
            except NetworkTimeoutError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return f"Task failed after {max_retries} attempts due to network timeout"
                
            except ElementNotFoundError as e:
                if attempt < max_retries - 1:
                    # Wait for dynamic content to load
                    await asyncio.sleep(5)
                    continue
                return f"Task failed: Required element not found on page"
                
            except SecurityError as e:
                return f"Task failed: Security restrictions prevent automation"
                
            except Exception as e:
                if attempt < max_retries - 1:
                    continue
                return f"Task failed with unexpected error: {str(e)}"
```

## Testing Examples

### Unit Tests for Browser Agent

```python
import pytest
from unittest.mock import AsyncMock, patch

class TestWebAutomationAgent:
    
    @pytest.fixture
    def agent(self):
        return WebAutomationAgent()
    
    @pytest.mark.asyncio
    async def test_navigation_intent(self, agent):
        """Test that navigation intents are handled correctly"""
        with patch.object(agent, 'execute_web_task', new_callable=AsyncMock) as mock_task:
            mock_task.return_value = "Successfully navigated to example.com"
            
            result = await agent._handle_navigation("browse to example.com")
            
            assert "Successfully navigated" in result
            mock_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, agent):
        """Test error handling in web automation"""
        with patch.object(agent, 'browser_agent') as mock_browser:
            mock_browser.run.side_effect = Exception("Network timeout")
            
            result = await agent.execute_web_task("test task")
            
            assert "Web task failed" in result
            assert "Network timeout" in result
    
    @pytest.mark.asyncio
    async def test_resource_cleanup(self, agent):
        """Test that browser resources are properly cleaned up"""
        await agent.initialize_browser()
        await agent.cleanup()
        
        # Verify cleanup was called
        # This would need actual implementation details
```

## Integration with Existing ABI Agents

### Enhanced ChatGPT Agent with Browser Capabilities

```python
class ChatGPTBrowserAgent(ChatGPTAgent, WebAutomationAgent):
    """ChatGPT agent enhanced with browser automation"""
    
    def __init__(self):
        ChatGPTAgent.__init__(self)
        WebAutomationAgent.__init__(self)
        
        # Merge system prompts
        self.configuration.system_prompt = f"""
        {ChatGPTAgent.SYSTEM_PROMPT}
        
        ADDITIONAL BROWSER CAPABILITIES:
        You now have the ability to browse the web and interact with websites.
        When users request web-based tasks, use your browser automation capabilities
        to navigate, extract data, fill forms, and perform complex web workflows.
        
        Always inform users when you're about to perform web automation and
        confirm the websites you'll be accessing.
        """
    
    async def process_request(self, user_input: str) -> str:
        """Process user requests with both chat and browser capabilities"""
        
        # Check if request requires web automation
        if self._requires_web_automation(user_input):
            return await self.execute_web_task(user_input)
        else:
            return await super().process_request(user_input)
    
    def _requires_web_automation(self, user_input: str) -> bool:
        """Determine if request requires browser automation"""
        web_keywords = [
            "browse", "navigate", "visit", "website", "webpage",
            "extract", "scrape", "data from", "form", "submit",
            "search on", "price compare", "social media"
        ]
        return any(keyword in user_input.lower() for keyword in web_keywords)
```

## Configuration Examples

### Browser Configuration for Different Environments

```python
# config/browser_configs.py

class BrowserConfigs:
    
    @staticmethod
    def development():
        """Development configuration - visible browser for debugging"""
        return {
            "headless": False,
            "devtools": True,
            "slow_mo": 1000,  # Slow down for debugging
            "timeout": 60000,
        }
    
    @staticmethod
    def production():
        """Production configuration - optimized for performance"""
        return {
            "headless": True,
            "devtools": False,
            "timeout": 30000,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions"
            ]
        }
    
    @staticmethod
    def enterprise():
        """Enterprise configuration with security hardening"""
        return {
            "headless": True,
            "ignore_https_errors": False,
            "bypass_csp": False,
            "permissions": [],
            "args": [
                "--disable-extensions",
                "--disable-plugins",
                "--disable-javascript",  # Only for specific use cases
                "--no-first-run"
            ]
        }
```

These examples demonstrate how browser-use can be seamlessly integrated into ABI while maintaining the existing agent architecture and adding powerful new web automation capabilities.