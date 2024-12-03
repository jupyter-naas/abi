import pytest

def test_perplexity_response(mock_perplexity_response):
    response = mock_perplexity_response
    
    # Assert the response has the expected structure
    assert 'choices' in response
    assert len(response['choices']) > 0
    assert 'message' in response['choices'][0]
    assert 'content' in response['choices'][0]['message']
    
    # Assert the content is a non-empty string
    content = response['choices'][0]['message']['content']
    assert isinstance(content, str)
    assert len(content) > 0 