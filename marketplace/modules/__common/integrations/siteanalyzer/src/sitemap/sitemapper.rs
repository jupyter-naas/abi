use std::error::Error;
use reqwest;
use quick_xml::Reader;
use quick_xml::events::Event;
use url::Url;

pub async fn load_sitemap_internals(base_url: &str) -> Result<String, Box<dyn Error>> {
    let urls = find_sitemap_urls(base_url).await?;
    let mut unique_locations = Vec::new();
    
    for url in urls {

        match fetch_and_parse_sitemap(&url).await {
            Ok(locations) => {
                for loc in locations {

                    if loc.contains("sitemap") && loc.ends_with(".xml") {
                        if let Ok(sub_locations) = fetch_and_parse_sitemap(&loc).await {
                            for sub_loc in sub_locations {
                                if !unique_locations.contains(&sub_loc) {
                                    unique_locations.push(sub_loc);
                                }
                            }
                        }
                    }
                    else if !unique_locations.contains(&loc) {
                        unique_locations.push(loc);
                    }
                }
            }
            Err(e) => println!("Error processing sitemap {}: {}", url, e),
        }
    }
    
    // Create JSON string from locations
    let json_string = serde_json::to_string_pretty(&unique_locations)?;
    
    Ok(json_string)
}

async fn find_sitemap_urls(base_url: &str) -> Result<Vec<String>, Box<dyn Error>> {
    let mut sitemap_urls = Vec::new();
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)  // Allow invalid certificates
        .build()?;

    // Common sitemap locations
    let potential_paths = vec![
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/robots.txt",
    ];

    let base = Url::parse(base_url)?;

    for path in potential_paths {
        println!("Checking path: {}", path);
        let url = base.join(path)?;
        let response = client.get(url.as_str())
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0")
            .send()
            .await;

        match response {
            Ok(resp) => {
                println!("Response status: {}", resp.status());
                if resp.status().is_success() {
                    let content = resp.text().await?;
                    
                    if path == "/robots.txt" {
                        // Parse robots.txt for Sitemap entries
                        for line in content.lines() {
                            if line.to_lowercase().starts_with("sitemap:") {
                                if let Some(sitemap_url) = line.split_once(':').map(|(_, url)| url.trim()) {
                                    sitemap_urls.push(sitemap_url.to_string());
                                }
                            }
                        }
                    } else {
                        sitemap_urls.push(url.to_string());
                    }
                }
            }
            Err(e) => {
                println!("Error fetching {}: {}", url, e);
                continue;
            },
        }
    }

    Ok(sitemap_urls)
}

async fn fetch_and_parse_sitemap(url: &str) -> Result<Vec<String>, Box<dyn Error>> {
    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)  // Allow invalid certificates
        .build()?;
        
    let response = client.get(url)
        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0")
        .send()
        .await?;
    let content = response.text().await?;

    let mut reader = Reader::from_str(&content);
    reader.trim_text(true);

    let mut urls = Vec::new();
    let mut buf = Vec::new();
    let mut in_loc = false;

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) => {
                if e.name().as_ref() == b"loc" {
                    in_loc = true;
                }
            }
            Ok(Event::Text(e)) if in_loc => {
                urls.push(e.unescape()?.into_owned());
            }
            Ok(Event::End(ref e)) => {
                if e.name().as_ref() == b"loc" {
                    in_loc = false;
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(Box::new(e)),
            _ => (),
        }
        buf.clear();
    }

    Ok(urls)
}