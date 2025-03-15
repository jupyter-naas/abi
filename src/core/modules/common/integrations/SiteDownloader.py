from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import siteanalyzer
import json

@dataclass
class SiteDownloaderConfiguration(IntegrationConfiguration):
    """Configuration for SiteDownloader.
    
    Currently no configuration parameters are needed as the library
    doesn't require any authentication or special settings.
    """
    pass

class SiteDownloader(Integration):
    """SiteDownloader class for downloading website content and sitemaps.
    
    This class provides methods to interact with websites using the siteanalyzer library.
    It can fetch sitemaps and download individual pages.
    
    Attributes:
        __configuration (SiteDownloaderConfiguration): Configuration instance
            (currently unused but required by Integration interface)
    
    Example:
        >>> config = SiteDownloaderConfiguration()
        >>> downloader = SiteDownloader(config)
        >>> sitemap = downloader.load_sitemap("https://example.com")
        >>> content = downloader.download_url("https://example.com/page")
    """

    __configuration: SiteDownloaderConfiguration

    def __init__(self, configuration: SiteDownloaderConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def load_sitemap(self, url: str) -> str:
        """Loads and parses the sitemap of a given website.

        Args:
            url (str): The base URL of the website to analyze

        Returns:
            str: JSON string containing an array of URLs found in the sitemap
        """
        analyzer = siteanalyzer.load_sitemap(url)
        return json.loads(analyzer)

    def download_url(self, url: str) -> str:
        """Downloads and returns the content of a specific URL.

        Args:
            url (str): The URL to download

        Returns:
            str: The content of the webpage as a string
        """
        return siteanalyzer.download_url(url)

    def extract_text_from_html(self, html: str) -> str:
        """Extracts text from an HTML string.

        Args:
            html (str): The HTML content to extract text from

        Returns:
            str: The extracted text
        """
        return siteanalyzer.extract_text_from_html(html)


if __name__ == "__main__":
    integration = SiteDownloader(SiteDownloaderConfiguration())
    # sitemap = integration.download_url("https://monip.org")
    # print(sitemap)
    # print(integration.load_sitemap("https://beneteau-group.com"))
    print(integration.extract_text_from_html(integration.download_url("https://monip.org")))
