import pytest

from src.core.chatgpt.agents.ChatGPTResponsesAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("what is your name")

    # ChatGPT: I am ChatGPT, your AI conversational assistant. How can I help you today?   

    assert result is not None, result
    assert "ChatGPT" in result, result

def test_search_news(agent):
    result = agent.invoke("search news about artificial intelligence")

    # ChatGPT: Here are some recent developments in artificial intelligence:                                                                                                                                                                          

    # United Nations Discusses AI's Dual Impact                                                                                                                                                                                              

    # On September 24, 2025, during a U.N. Security Council meeting, global leaders debated AI's transformative potential alongside its risks. U.N. Secretary-General António Guterres highlighted AI's role in peacekeeping and crisis      
    # mitigation but cautioned against its misuse in warfare and disinformation. The session underscored the need for responsible AI governance, with the U.N. adopting new oversight frameworks, including the upcoming Global Dialogue on  
    # AI Governance. (apnews.com)                                                                                                                                                                                                            

    # White House Directs Agencies to Enhance AI Use                                                                                                                                                                                         

    # In April 2025, the White House mandated federal agencies to appoint chief AI officers and develop strategies for responsible AI implementation. This directive aims to accelerate AI deployment by removing bureaucratic barriers,     
    # emphasizing innovation, and prioritizing American-made AI technologies. Agencies are encouraged to focus on interoperability and privacy protection. (reuters.com)                                                                     

    # Apple Halts AI-Generated News Summaries Due to Inaccuracies                                                                                                                                                                            

    # In January 2025, Apple suspended its AI-generated news and entertainment feature in the beta version of iOS 18.3. The decision was prompted by the feature's tendency to produce false information, known as "hallucinations." This    
    # move reflects broader challenges in AI integration, as similar issues have led other tech companies to reevaluate their AI applications. (apnews.com)                                                                                  

    # Bipartisan Effort to Ban Chinese AI in Federal Agencies                                                                                                                                                                                

    # In June 2025, a bipartisan group of U.S. lawmakers introduced legislation to prohibit Chinese AI systems from being used in federal agencies. This initiative responds to concerns over the rapid advancement of Chinese AI firms and  
    # aims to bolster national security by restricting foreign adversaries' influence within the U.S. government. (apnews.com)                                                                                                               

    # Public Perception of AI Usage in the U.S.                                                                                                                                                                                              

    # A recent AP-NORC poll reveals that 60% of American adults use AI for information searches, with younger individuals more likely to use AI for tasks like brainstorming and idea generation. However, fewer adults utilize AI for       
    # work-related tasks, drafting emails, shopping, or entertainment, indicating a cautious approach to AI integration in daily life. (apnews.com)                                                                                          


    #                                                                                             Recent Developments in Artificial Intelligence:                                                                                            

    #  • AI's double-edged sword: UN leaders weigh its promise and peril                                                                                                                                                                     
    #  • Expanding AI use, White House orders agencies to develop strategies and name leaders                                                                                                                                                
    #  • Apple pulls error-prone AI-generated news summaries in its beta iPhone software                                                                                                                                                     

    # Annotations:                                                                                                                                                                                                                           

    #  • AI's double-edged sword: UN leaders weigh its promise and peril                                                                                                                                                                     
    #  • Expanding AI use, White House orders agencies to develop strategies and name leaders                                                                                                                                                
    #  • Apple pulls error-prone AI-generated news summaries in its beta iPhone software                                                                                                                                                     
    #  • Bipartisan bill aims to block Chinese AI from federal agencies                                                                                                                                                                      
    #  • How US adults are using AI, according to AP-NORC polling                                                                                                                                                                            
    #  • AI's double-edged sword: UN leaders weigh its promise and peril                                                                                                                                                                     
    #  • Expanding AI use, White House orders agencies to develop strategies and name leaders                                                                                                                                                
    #  • Apple pulls error-prone AI-generated news summaries in its beta iPhone software         
    
    assert result is not None, result
    assert "artificial intelligence" in result.lower(), result
    assert "annotations" in result.lower(), result

def test_search_news_with_datetime(agent):
    from datetime import datetime
    result = agent.invoke("What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'")

    # ChatGPT: As of today the date is 2025-09-25                                                                                                                                                                                                     

    # Here are some of the news highlights of the day:                                                                                                                                                                                       

    # Artificial Intelligence:                                                                                                                                                                                                               

    #  • World leaders at the U.N. Security Council discussed the dual impact of AI on society, emphasizing both its potential for peacekeeping and humanitarian efforts and risks related to misuse in warfare and disinformation. A Global 
    #    Dialogue on AI Governance and a scientific expert panel have been established to oversee responsible AI development. (apnews.com)                                                                                                   
    #  • In the legal sphere, the Indian news agency ANI has sued OpenAI over unauthorized use of its content for AI training, alleging fabricated news attribution. (reuters.com)                                                           
    #  • Amazon announced an additional $4 billion investment into AI startup Anthropic, increasing its total investment to $8 billion, focusing on collaboration with AWS. (apnews.com)                                                     

    # Climate Change:                                                                                                                                                                                                                        

    #  • China committed at the U.N. climate summit to reduce emissions by 7% to 10% below peak by 2035 and expand wind and solar capacity sixfold from 2020 levels. This is the first time China officially commits to emission reductions. 
    #    (reuters.com)                                                                                                                                                                                                                       
    #  • The World Meteorological Organization reported 2024 as the warmest year on record globally, with surface temperatures at 1.6°C above pre-industrial levels, exceeding the Paris Agreement’s 1.5°C threshold for the first time.     
    #    (cbsnews.com)                                                                                                                                                                                                                       
    #  • Glaciers are melting faster worldwide, losing over 7 trillion tons of ice since 2000, significantly contributing to sea-level rise. (apnews.com)                                                                                    

    # Other highlights:                                                                                                                                                                                                                      

    #  • The White House has directed federal agencies to improve adoption of AI technologies with appointed chief AI officers and responsible usage strategies. (reuters.com)                                                               
    #  • Apple suspended its AI-generated news and entertainment feature in iOS beta due to inaccuracies and hallucinations. (apnews.com)                                                                                                    

    # If you want more details on any of these topics or news from other areas, please let me know!  

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result
    assert "annotations" in result.lower(), result

def test_analyze_image_from_url(agent):
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    result = agent.invoke(f"analyze an image from URL: {image_url}")

    # ChatGPT: The image depicts a serene natural landscape with a wooden boardwalk leading straight through tall green grass and foliage. The boardwalk is made of wooden planks bordered by narrow wooden strips on each side. The surrounding grass
    # appears lush and vibrant, possibly indicating a well-maintained wetland or meadow area.                                                                                                                                                

    # In the distance, there are scattered trees and shrubs, adding depth to the landscape. The sky above is a bright blue with dispersed, wispy clouds, suggesting a clear and pleasant day. The lighting implies that the photo was taken  
    # during the late afternoon or early evening, as the sunlight casts warm tones on the grass and boardwalk.                                                                                                                               

    # Overall, the image conveys a peaceful, natural environment, ideal for walking and enjoying nature. 

    assert result is not None, result
    assert "boardwalk" in result, result

def test_tell_about_pdf(agent):
    pdf_url = "https://assets.group.accor.com/yrj0orc8tx24/NHhsrTDX0ecCjky5bsvSV/6b631aa9885bf8c3ed84fb323a91e310/ACCOR_IMPACT_REPORT_2023.pdf"
    result = agent.invoke(f"what can you tell about the content of this PDF document: {pdf_url}")

    # ChatGPT: The document is the Accor 2023 Impact Report focusing on the company’s sustainable transformation within the hospitality sector. The report covers Accor’s sustainability vision, strategic goals, achievements, challenges, and future
    # commitments.                                                                                                                                                                                                                           

    # Key points include:                                                                                                                                                                                                                    

    #  • Emphasis on operating hotels within planetary boundaries and achieving carbon neutrality by 2050.                                                                                                                                   
    #  • Targets such as reducing greenhouse gas emissions by 46% (Scopes 1 & 2) and 28% (Scope 3) by 2030, eliminating single-use plastics by 2025, reducing food waste by 60% by 2030, and having 100% eco-certified hotels by 2026.       
    #  • Sustainability initiatives around energy and water consumption reduction, renewable energy use, circular economy, biodiversity support, and food sustainability including waste reduction and sourcing.                             
    #  • Social responsibility programs covering diversity, equity, inclusion, disability accessibility, and local community support.                                                                                                        
    #  • Progress metrics from 2023 including plastic waste avoided, food waste goals, gender parity, and donation programs.                                                                                                                 
    #  • Future outlook focused on balancing financial and environmental/social performance, accelerating transformation, and innovating sustainable hospitality.                                                                            

    # The report combines detailed data, case studies, partnerships, and commitments demonstrating Accor's leadership in responsible hospitality aligned with global climate goals and transparency.                                         

    # If you want me to highlight specific sections or detailed statistics, please let me know!   

    assert result is not None, result
    assert "accor" in result.lower(), result
    assert "2023" in result, result
    assert "impact report" in result.lower(), result

def test_extract_people_from_pdf(agent):
    pdf_url = "https://assets.group.accor.com/yrj0orc8tx24/NHhsrTDX0ecCjky5bsvSV/6b631aa9885bf8c3ed84fb323a91e310/ACCOR_IMPACT_REPORT_2023.pdf"
    result = agent.invoke(f"Extract all people cited in this PDF document: {pdf_url}")

    # ChatGPT: The PDF document cites the following people:                                                                                                                                                                                           

    #  1 Sébastien Bazin – Chairman & CEO                                                                                                                                                                                                    
    #  2 Régis Koch – General Manager of the Ibis Marseille Saint Charles in France                                                                                                                                                          
    #  3 Brune Poirson – Chief Sustainability Officer                                                                                                                                                                                        
    #  4 Hakim Arezki – High-level CeciFoot athlete (emblematic hire to raise awareness about disabilities at Pullman Paris Tour Eiffel, France)                                                                                             
    #  5 Chef Raoni – Mentioned visiting France to improve the integration of biodiversity into Accor sustainable policy  

    assert result is not None, result
    assert "bazin" in result.lower(), result