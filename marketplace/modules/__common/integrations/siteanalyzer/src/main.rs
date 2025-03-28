use std::error::Error;
use std::sync::atomic::{AtomicBool, Ordering};
use ctrlc;

mod downloader;
use downloader::download_url as download_url_internal;
use downloader::extract_text_from_html as extract_text_from_html_internal;

mod sitemap;
use sitemap::load_sitemap_internals;


static RUNNING: AtomicBool = AtomicBool::new(true);

fn init() {
    ctrlc::set_handler(move || {
        RUNNING.store(false, Ordering::SeqCst);
    }).expect("Error setting Ctrl-C handler");
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let base_url = std::env::args().nth(1).expect("Please provide a base URL as an argument");

    let html_content = download_url_internal(&base_url).await?;
    let text = extract_text_from_html_internal(&html_content);
    println!("{}", text);
    
    Ok(())
}

