use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};

mod downloader;
mod sitemap;

use downloader::download_url as download_url_internal;
use downloader::extract_text_from_html as extract_text_from_html_internal;
use sitemap::load_sitemap_internals;

static RUNNING: AtomicBool = AtomicBool::new(true);

fn init() {
    ctrlc::set_handler(move || {
        RUNNING.store(false, Ordering::SeqCst);
    }).expect("Error setting Ctrl-C handler");
}

#[pyfunction]
fn load_sitemap(base_url: String) -> PyResult<String> {
    tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(load_sitemap_internals(&base_url))
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

#[pyfunction]
fn download_url(url: String) -> PyResult<String> {
    tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(download_url_internal(&url))
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}

#[pyfunction]
fn extract_text_from_html(html_content: String) -> PyResult<String> {
    Ok(extract_text_from_html_internal(&html_content))
}

#[pymodule]
fn siteanalyzer(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    init();
    m.add_function(wrap_pyfunction!(load_sitemap, m)?)?;
    m.add_function(wrap_pyfunction!(download_url, m)?)?;
    m.add_function(wrap_pyfunction!(extract_text_from_html, m)?)?;
    Ok(())
} 