use std::fs;
use std::path::PathBuf;
use reqwest;
use url::Url;
use std::error::Error;
use scraper::{Html, Selector};
use wiremock::{MockServer, Mock, ResponseTemplate};
use wiremock::matchers::{method, path};

pub async fn download_url(url_str: &str) -> anyhow::Result<String> {
    // Parse the URL
    let url = Url::parse(url_str)?;
    
    // Create a filename from the URL
    let filename = url.path()
        .trim_start_matches('/')
        .replace('/', "__");
    let filename = if filename.is_empty() { "index".to_string() } else { filename };
    
    // Create a path with the host and path structure
    let mut path_parts = vec!["downloads"];
    if let Some(host) = url.host_str() {
        path_parts.push(host);
    }
    
    // Create the directory structure
    let dir_path = PathBuf::from(path_parts.join("/"));
    fs::create_dir_all(&dir_path)?;
    
    // Add the filename with .html extension
    let mut file_path = dir_path.join(filename);
    file_path.set_extension("html");

    // Download the content with Firefox user agent and disabled certificate verification
    let client = reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0")
        .danger_accept_invalid_certs(true)  // Disable certificate verification
        .build()?;
    
    let response = client.get(url_str)
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(anyhow::anyhow!("Failed to download URL: {}", response.status()));
    }

    // Check if the response status is 200 OK
    let content = response.text().await?;

    // // Print filepath
    // println!("Saving to: {}", file_path.to_string_lossy());

    // // Save the content
    // fs::write(file_path, content)?;

    Ok(content)
}

pub fn extract_text_from_html(html_content: &str) -> String {
    // Parse the HTML string
    let document = Html::parse_document(html_content);
    
    // Create selectors for title and body tags
    let title_selector = Selector::parse("title").unwrap();
    let body_selector = Selector::parse("body").unwrap();
    let script_selector = Selector::parse("script, style").unwrap();
    
    // Extract title text
    let title = document
        .select(&title_selector)
        .next()
        .and_then(|element| Some(element.text().collect::<String>()))
        .unwrap_or_default()
        .trim()
        .to_string();
    
    // Remove script and style tags from the document
    let mut body_text = String::new();

    let mut script_content: Vec<String> = Vec::new();

    for element in document.select(&body_selector) {
        // First, remove all script and style elements
        let content = element.clone();

        content.select(&script_selector).for_each(|node| {
            // Save the script content for later matching
            script_content.push(node.text().collect::<String>());
        });

        // Now collect remaining text
        for text_node in content.text() {
            // Check if the text node is a script content.
            if script_content.contains(&text_node.to_string()) {
                continue;
            }

            let trimmed = text_node.trim();
            if !trimmed.is_empty() {
                if !body_text.is_empty() {
                    body_text.push(' ');
                }
                body_text.push_str(trimmed);
            }
        }
    }
    
    // Combine title and body text
    if title.is_empty() {
        body_text
    } else {
        format!("{}\n\n{}", title, body_text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_text_from_html() {
        let html = r#"
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Test Page</title>
                </head>
                <body>
                    <h1>Hello World</h1>
                    <p>This is a test paragraph.</p>
                    <div>
                        Some <b>bold</b> text
                        <span>and some nested content</span>
                    </div>
                </body>
            </html>
        "#;

        let text = extract_text_from_html(html);
        assert_eq!(
            text,
            "Test Page\n\nHello World This is a test paragraph. Some bold text and some nested content"
        );
    }

    #[tokio::test]
    async fn test_download_url() {
        // Start a mock server
        let mock_server = MockServer::start().await;

        // Create a mock response
        Mock::given(method("GET"))
            .and(path("/test/page"))
            .respond_with(ResponseTemplate::new(200)
                .set_body_string("<html><body>Test content</body></html>"))
            .mount(&mock_server)
            .await;

        // Use the mock server URL for the test
        let test_url = format!("{}/test/page", mock_server.uri());
        let result = download_url(&test_url).await;
        
        assert!(result.is_ok(), "Download should succeed");
        let content = result.unwrap();
        
        assert_eq!(content, "<html><body>Test content</body></html>");
    }

    #[tokio::test]
    async fn test_download_url_error() {
        // Start a mock server
        let mock_server = MockServer::start().await;

        // Create a mock response for a 404 error
        Mock::given(method("GET"))
            .and(path("/not-found"))
            .respond_with(ResponseTemplate::new(404))
            .mount(&mock_server)
            .await;

        // Use the mock server URL for the test
        let test_url = format!("{}/not-found", mock_server.uri());
        let result = download_url(&test_url).await;
        
        assert!(result.is_err(), "Download should fail for 404 response");
    }
}

