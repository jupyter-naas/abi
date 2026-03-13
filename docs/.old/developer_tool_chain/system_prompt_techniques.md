# Prompting Techniques

## Chain of Thought (CoT)

Chain of Thought prompting encourages the model to break down complex problems into step-by-step reasoning, making the thought process explicit and transparent.

**Structure:**
- Present the problem
- Request step-by-step thinking
- Ask for explicit reasoning at each step
- Conclude with the final answer

**Example:**
```
Problem: A store sells apples for $2 per pound and oranges for $3 per pound. If I buy 4 pounds of apples and 2 pounds of oranges, how much do I spend in total?

Let me think through this step by step:
1. First, I'll calculate the cost of apples: 4 pounds × $2/pound = $8
2. Next, I'll calculate the cost of oranges: 2 pounds × $3/pound = $6
3. Finally, I'll add both costs together: $8 + $6 = $14

Therefore, the total cost is $14.
```

**When to use:**
- Complex mathematical problems
- Multi-step reasoning tasks
- Debugging logical errors
- Planning and decision-making scenarios

## Few-Shot Learning

Few-Shot Learning provides the model with a few examples of the desired input-output pattern before presenting the actual task, helping establish the expected format and style.

**Structure:**
- Provide 2-5 examples of input-output pairs
- Maintain consistent formatting across examples
- Present the actual task using the same format
- Let the model infer the pattern

**Example:**
```
Task: Convert these sentences to a more professional tone.

Example 1:
Input: "Hey, can you get back to me ASAP about this?"
Output: "I would appreciate your prompt response regarding this matter."

Example 2:
Input: "This is totally wrong and needs to be fixed right now."
Output: "There appears to be an error that requires immediate attention."

Example 3:
Input: "Thanks a bunch for helping me out with this stuff."
Output: "Thank you for your assistance with these matters."

Now convert this sentence:
Input: "Can you double-check this thing before we send it out?"
Output: "Could you please review this document before distribution?"
```

**When to use:**
- Establishing specific output formats
- Teaching new writing styles or tones
- Pattern recognition tasks
- Classification problems
- When you need consistent formatting across responses

## ROC-T-TOC

**Structure:**
- Role: Define who the agent is, their function and expertise (Example: 'Email summarizer assistant')
- Objective: Clearly state the overall objective or goal to achieve/solve. Acts as the guiding star for all tasks
- Context: Provide additional context and relevant background information
- Tools: List available tools with their expected inputs and outputs
- Tasks: Lay out clear step-by-step tasks the agent will execute
- Operating Guidelines: Specify how the agent should execute each task. Include which tools to use. Define how to interact with users. Outline process steps
- Constraints: Define rules. Specify expected formats. Outline off-topic areas