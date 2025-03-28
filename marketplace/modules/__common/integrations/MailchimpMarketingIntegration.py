from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
import requests
from typing import Optional, List, Dict

LOGO_URL = "https://logo.clearbit.com/mailchimp.com"

@dataclass
class MailchimpMarketingIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for MailchimpMarketingIntegration.
    
    Attributes:
        api_key (str): Mailchimp API key
        dc (str): Data Center for Mailchimp API. Defaults to "us1"
        version (str): Version of Mailchimp API. Defaults to "3.0"
    """
    api_key: str
    dc: str = "us1"
    version: str = "3.0"

class MailchimpMarketingIntegration(Integration):
    """MailchimpMarketingIntegration class for interacting with Mailchimp's Marketing API.
    
    This class provides methods to interact with Mailchimp's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (MailchimpMarketingIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = MailchimpMarketingIntegrationConfiguration(
        ...     api_key="your_api_key",
        ...     base_url="https://<dc>.api.mailchimp.com/3.0"
        ... )
        >>> integration = MailchimpMarketingIntegration(config)
    """

    __configuration: MailchimpMarketingIntegrationConfiguration

    def __init__(self, configuration: MailchimpMarketingIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.base_url = f"https://{self.__configuration.dc}.api.mailchimp.com/{self.__configuration.version}"
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[dict] = None) -> dict:
        """Make a request to the Mailchimp API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint to request
            data (dict, optional): Data to send with the request. Defaults to None.
        
        Returns:
            dict: Response from the API
        """
        response = requests.request(method, endpoint, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def list_account_exports(
        self, 
        fields: Optional[List[str]] = None, 
        exclude_fields: Optional[List[str]] = None, 
        count: Optional[int] = 10, 
        offset: Optional[int] = 0
    ) -> dict:
        """Get a list of account exports for the Mailchimp account.
        
        Args:
            fields (List[str], optional): A comma-separated list of fields to return. Reference parameters 
                of sub-objects with dot notation.
            exclude_fields (List[str], optional): A comma-separated list of fields to exclude. Reference 
                parameters of sub-objects with dot notation.
            count (int, optional): The number of records to return. Default value is 10. Maximum value is 1000.
            offset (int, optional): Used for pagination, this is the number of records to skip. Default value is 0.
        
        Returns:
            dict: Response containing list of account exports
        """
        endpoint = f"{self.base_url}/account-exports"
        params = {}
        
        if fields:
            params['fields'] = ','.join(fields)
        if exclude_fields:
            params['exclude_fields'] = ','.join(exclude_fields)
        if count:
            params['count'] = min(count, 1000)
        if offset:
            params['offset'] = offset
            
        endpoint = f"{endpoint}?{'&'.join(f'{k}={v}' for k,v in params.items())}" if params else endpoint
        return self._make_request("GET", endpoint)
    
    def create_account_export(
        self,
        include_stages: List[str], 
        since_timestamp: Optional[str] = None
    ) -> dict:
        """Create a new account export in the Mailchimp account.
        
        Args:
            include_stages (List[str]): The stages of an account export to include
            since_timestamp (str, optional): An ISO 8601 date that will limit the export to only records 
                created after a given time. For instance, the reports stage will contain any campaign 
                sent after the given timestamp. Audiences are excluded from this limit.
        
        Returns:
            dict: Response containing details of the created export
        """
        endpoint = f"{self.base_url}/account-exports"
        data = {
            "include_stages": include_stages
        }
        if since_timestamp:
            data["since_timestamp"] = since_timestamp
            
        return self._make_request("POST", endpoint, data=data)

    def get_account_export(
        self,
        export_id: str,
        fields: Optional[List[str]] = None, 
        exclude_fields: Optional[List[str]] = None
    ) -> dict:
        """Get information about a specific account export.
        
        Args:
            export_id (str): The unique ID of the export to retrieve
            fields (List[str], optional): A comma-separated list of fields to return. Reference parameters 
                of sub-objects with dot notation.
            exclude_fields (List[str], optional): A comma-separated list of fields to exclude. Reference 
                parameters of sub-objects with dot notation.
            
        Returns:
            dict: Response containing export details
        """
        endpoint = f"{self.base_url}/account-exports/{export_id}"
        params = {}
        
        if fields:
            params['fields'] = ','.join(fields)
        if exclude_fields:
            params['exclude_fields'] = ','.join(exclude_fields)
            
        endpoint = f"{endpoint}?{'&'.join(f'{k}={v}' for k,v in params.items())}" if params else endpoint
        return self._make_request("GET", endpoint)
    
    def list_campaigns(self, fields: Optional[List[str]] = None) -> dict:
        """Get all campaigns in the Mailchimp account.
        
        Args:
            fields (List[str], optional): A comma-separated list of fields to return. Reference parameters
                of sub-objects with dot notation.
                
        Returns:
            dict: Response containing list of campaigns
        """
        endpoint = f"{self.base_url}/campaigns"
        params = {'fields': ','.join(fields)} if fields else {}
        return self._make_request("GET", endpoint, params=params)

    def create_campaign(self, data: dict) -> dict:
        """Create a new Mailchimp campaign.
        
        Args:
            data (dict): The campaign settings. Required fields include:
                type (str): The campaign type (regular, plaintext, absplit, rss, variate)
                settings (dict): The campaign settings including subject_line, title, from_name, reply_to
                recipients (dict): List settings for the campaign including list_id
                
        Returns:
            dict: Response containing created campaign details
        """
        endpoint = f"{self.base_url}/campaigns"
        return self._make_request("POST", endpoint, data=data)

    def get_campaign_info(self, campaign_id: str) -> dict:
        """Get information about a specific campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Response containing campaign details
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}"
        return self._make_request("GET", endpoint)

    def update_campaign_settings(self, campaign_id: str, data: dict) -> dict:
        """Update some or all of the settings for a specific campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            data (dict): The updated campaign settings
            
        Returns:
            dict: Response containing updated campaign details
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_campaign(self, campaign_id: str) -> dict:
        """Remove a campaign from your Mailchimp account.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}"
        return self._make_request("DELETE", endpoint)

    def cancel_campaign(self, campaign_id: str) -> dict:
        """Cancel a Regular or Plain-Text Campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/cancel-send"
        return self._make_request("POST", endpoint)

    def send_campaign(self, campaign_id: str) -> dict:
        """Send a Mailchimp campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/send"
        return self._make_request("POST", endpoint)

    def schedule_campaign(self, campaign_id: str, data: dict) -> dict:
        """Schedule a campaign for delivery.
        
        Args:
            campaign_id (str): The unique id for the campaign
            data (dict): The scheduling information including:
                schedule_time (str): The UTC date/time to schedule the campaign (ISO 8601)
                timewarp (bool, optional): Whether to use Timewarp
                batch_delivery (dict, optional): Batch delivery settings
                
        Returns:
            dict: Response containing scheduled campaign details
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/schedule"
        return self._make_request("POST", endpoint, data=data)

    def unschedule_campaign(self, campaign_id: str) -> dict:
        """Unschedule a scheduled campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/unschedule"
        return self._make_request("POST", endpoint)

    def pause_rss_campaign(self, campaign_id: str) -> dict:
        """Pause an RSS-Driven campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/pause"
        return self._make_request("POST", endpoint)

    def resume_rss_campaign(self, campaign_id: str) -> dict:
        """Resume an RSS-Driven campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/resume"
        return self._make_request("POST", endpoint)

    def replicate_campaign(self, campaign_id: str) -> dict:
        """Replicate a campaign in saved or send status.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Response containing replicated campaign details
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/replicate"
        return self._make_request("POST", endpoint)

    def send_test_email(self, campaign_id: str, data: dict) -> dict:
        """Send a test email.
        
        Args:
            campaign_id (str): The unique id for the campaign
            data (dict): The test email settings including:
                test_emails (List[str]): Array of email addresses to send test to
                send_type (str, optional): Type of test email (html or plaintext)
                
        Returns:
            dict: Empty response on success
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/test"
        return self._make_request("POST", endpoint, data=data)

    def resend_campaign(self, campaign_id: str) -> dict:
        """Creates a Resend to Non-Openers version of this campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Response containing resend campaign details
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/actions/create-resend"
        return self._make_request("POST", endpoint)

    def get_campaign_content(self, campaign_id: str) -> dict:
        """Get the HTML and plain-text content for a campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Response containing campaign content
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/content"
        return self._make_request("GET", endpoint)

    def set_campaign_content(self, campaign_id: str, data: dict) -> dict:
        """Set the content for a campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            data (dict): The content settings including:
                html (str, optional): The raw HTML for the campaign
                plain_text (str, optional): The plain-text content
                template (dict, optional): The template configuration
                
        Returns:
            dict: Response containing updated campaign content
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/content"
        return self._make_request("PUT", endpoint, data=data)

    def list_campaign_feedback(self, campaign_id: str) -> dict:
        """Get team feedback for a campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            
        Returns:
            dict: Response containing campaign feedback
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/feedback"
        return self._make_request("GET", endpoint)

    def add_campaign_feedback(self, campaign_id: str, data: dict) -> dict:
        """Add feedback on a specific campaign.
        
        Args:
            campaign_id (str): The unique id for the campaign
            data (dict): The feedback details including:
                message (str): The content of the feedback
                is_complete (bool, optional): Whether feedback is complete
                
        Returns:
            dict: Response containing created feedback
        """
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/feedback"
        return self._make_request("POST", endpoint, data=data)

    def get_campaign_feedback_message(self, campaign_id: str, feedback_id: str) -> dict:
        """Get a specific feedback message from a campaign."""
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/feedback/{feedback_id}"
        return self._make_request("GET", endpoint)

    def update_campaign_feedback_message(self, campaign_id: str, feedback_id: str, data: dict) -> dict:
        """Update a specific feedback message for a campaign."""
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/feedback/{feedback_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_campaign_feedback_message(self, campaign_id: str, feedback_id: str) -> dict:
        """Remove a specific feedback message for a campaign."""
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/feedback/{feedback_id}"
        return self._make_request("DELETE", endpoint)

    def get_campaign_send_checklist(self, campaign_id: str) -> dict:
        """Review the send checklist for a campaign."""
        endpoint = f"{self.base_url}/campaigns/{campaign_id}/send-checklist"
        return self._make_request("GET", endpoint)

    def list_audiences(self) -> dict:
        """Get information about all lists in the Mailchimp account."""
        endpoint = f"{self.base_url}/lists"
        return self._make_request("GET", endpoint)

    def create_audience(self, data: dict) -> dict:
        """Create a new list in your Mailchimp account."""
        endpoint = f"{self.base_url}/lists"
        return self._make_request("POST", endpoint, data=data)

    def get_audience_info(self, list_id: str) -> dict:
        """Get information about a specific list in your Mailchimp account."""
        endpoint = f"{self.base_url}/lists/{list_id}"
        return self._make_request("GET", endpoint)

    def update_audience(self, list_id: str, data: dict) -> dict:
        """Update the settings for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_audience(self, list_id: str) -> dict:
        """Delete a list from your Mailchimp account."""
        endpoint = f"{self.base_url}/lists/{list_id}"
        return self._make_request("DELETE", endpoint)

    def batch_subscribe_unsubscribe(self, list_id: str, data: dict) -> dict:
        """Batch subscribe or unsubscribe list members."""
        endpoint = f"{self.base_url}/lists/{list_id}"
        return self._make_request("POST", endpoint, data=data)

    def list_abuse_reports(self, list_id: str) -> dict:
        """Get all abuse reports for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/abuse-reports"
        return self._make_request("GET", endpoint)

    def get_abuse_report(self, list_id: str, report_id: str) -> dict:
        """Get details about a specific abuse report."""
        endpoint = f"{self.base_url}/lists/{list_id}/abuse-reports/{report_id}"
        return self._make_request("GET", endpoint)

    def list_recent_activity(self, list_id: str) -> dict:
        """Get up to the previous 180 days of daily detailed aggregated activity stats for a list."""
        endpoint = f"{self.base_url}/lists/{list_id}/activity"
        return self._make_request("GET", endpoint)

    def list_top_email_clients(self, list_id: str) -> dict:
        """Get a list of the top email clients based on user-agent strings."""
        endpoint = f"{self.base_url}/lists/{list_id}/clients"
        return self._make_request("GET", endpoint)

    def list_member_events(self, list_id: str, subscriber_hash: str) -> dict:
        """Get events for a contact."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/events"
        return self._make_request("GET", endpoint)

    def add_member_event(self, list_id: str, subscriber_hash: str, data: dict) -> dict:
        """Add an event for a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/events"
        return self._make_request("POST", endpoint, data=data)

    def list_growth_history(self, list_id: str) -> dict:
        """Get a month-by-month summary of a specific list's growth activity."""
        endpoint = f"{self.base_url}/lists/{list_id}/growth-history"
        return self._make_request("GET", endpoint)

    def get_growth_history_by_month(self, list_id: str, month: str) -> dict:
        """Get a summary of a specific list's growth activity for a specific month and year."""
        endpoint = f"{self.base_url}/lists/{list_id}/growth-history/{month}"
        return self._make_request("GET", endpoint)

    def list_interest_categories(self, list_id: str) -> dict:
        """Get information about a list's interest categories."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories"
        return self._make_request("GET", endpoint)

    def create_interest_category(self, list_id: str, data: dict) -> dict:
        """Create a new interest category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories"
        return self._make_request("POST", endpoint, data=data)

    def get_interest_category_info(self, list_id: str, interest_category_id: str) -> dict:
        """Get information about a specific interest category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}"
        return self._make_request("GET", endpoint)

    def update_interest_category(self, list_id: str, interest_category_id: str, data: dict) -> dict:
        """Update a specific interest category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_interest_category(self, list_id: str, interest_category_id: str) -> dict:
        """Delete a specific interest category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}"
        return self._make_request("DELETE", endpoint)

    def list_interests_in_category(self, list_id: str, interest_category_id: str) -> dict:
        """Get a list of this category's interests."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}/interests"
        return self._make_request("GET", endpoint)

    def add_interest_in_category(self, list_id: str, interest_category_id: str, data: dict) -> dict:
        """Create a new interest or 'group name' for a specific category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}/interests"
        return self._make_request("POST", endpoint, data=data)

    def get_interest_in_category(self, list_id: str, interest_category_id: str, interest_id: str) -> dict:
        """Get interests or 'group names' for a specific category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}/interests/{interest_id}"
        return self._make_request("GET", endpoint)

    def update_interest_in_category(self, list_id: str, interest_category_id: str, interest_id: str, data: dict) -> dict:
        """Update interests or 'group names' for a specific category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}/interests/{interest_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_interest_in_category(self, list_id: str, interest_category_id: str, interest_id: str) -> dict:
        """Delete interests or group names in a specific category."""
        endpoint = f"{self.base_url}/lists/{list_id}/interest-categories/{interest_category_id}/interests/{interest_id}"
        return self._make_request("DELETE", endpoint)

    def list_locations(self, list_id: str) -> dict:
        """Get the locations (countries) that the list's subscribers have been tagged to based on geocoding their IP address."""
        endpoint = f"{self.base_url}/lists/{list_id}/locations"
        return self._make_request("GET", endpoint)

    def list_member_activity(self, list_id: str, subscriber_hash: str) -> dict:
        """Get the last 50 events of a member's activity on a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/activity"
        return self._make_request("GET", endpoint)

    def list_member_activity_feed(self, list_id: str, subscriber_hash: str) -> dict:
        """Get a member's activity on a specific list, including opens, clicks, and unsubscribes."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/activity-feed"
        return self._make_request("GET", endpoint)

    def list_member_goals(self, list_id: str, subscriber_hash: str) -> dict:
        """Get the last 50 Goal events for a member on a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/goals"
        return self._make_request("GET", endpoint)

    def list_member_notes(self, list_id: str, subscriber_hash: str) -> dict:
        """Get recent notes for a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/notes"
        return self._make_request("GET", endpoint)

    def add_member_note(self, list_id: str, subscriber_hash: str, data: dict) -> dict:
        """Add a new note for a specific subscriber."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/notes"
        return self._make_request("POST", endpoint, data=data)

    def get_member_note(self, list_id: str, subscriber_hash: str, note_id: str) -> dict:
        """Get a specific note for a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/notes/{note_id}"
        return self._make_request("GET", endpoint)

    def update_member_note(self, list_id: str, subscriber_hash: str, note_id: str, data: dict) -> dict:
        """Update a specific note for a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/notes/{note_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_member_note(self, list_id: str, subscriber_hash: str, note_id: str) -> dict:
        """Delete a specific note for a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/notes/{note_id}"
        return self._make_request("DELETE", endpoint)

    def list_member_tags(self, list_id: str, subscriber_hash: str) -> dict:
        """Get the tags on a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/tags"
        return self._make_request("GET", endpoint)

    def add_or_remove_member_tags(self, list_id: str, subscriber_hash: str, data: dict) -> dict:
        """Add or remove tags from a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/tags"
        return self._make_request("POST", endpoint, data=data)

    def list_members_info(self, list_id: str) -> dict:
        """Get information about members in a specific Mailchimp list."""
        endpoint = f"{self.base_url}/lists/{list_id}/members"
        return self._make_request("GET", endpoint)

    def add_member_to_list(self, list_id: str, data: dict) -> dict:
        """Add a new member to the list."""
        endpoint = f"{self.base_url}/lists/{list_id}/members"
        return self._make_request("POST", endpoint, data=data)

    def get_member_info(self, list_id: str, subscriber_hash: str) -> dict:
        """Get information about a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}"
        return self._make_request("GET", endpoint)

    def add_or_update_list_member(self, list_id: str, subscriber_hash: str, data: dict) -> dict:
        """Add or update a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}"
        return self._make_request("PUT", endpoint, data=data)

    def update_list_member(self, list_id: str, subscriber_hash: str, data: dict) -> dict:
        """Update information for a specific list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}"
        return self._make_request("PATCH", endpoint, data=data)

    def archive_list_member(self, list_id: str, subscriber_hash: str) -> dict:
        """Archive a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}"
        return self._make_request("DELETE", endpoint)

    def delete_list_member(self, list_id: str, subscriber_hash: str) -> dict:
        """Delete all personally identifiable information related to a list member."""
        endpoint = f"{self.base_url}/lists/{list_id}/members/{subscriber_hash}/actions/delete-permanent"
        return self._make_request("POST", endpoint)

    def list_merge_fields(self, list_id: str) -> dict:
        """Get a list of all merge fields for an audience."""
        endpoint = f"{self.base_url}/lists/{list_id}/merge-fields"
        return self._make_request("GET", endpoint)

    def add_merge_field(self, list_id: str, data: dict) -> dict:
        """Add a new merge field for a specific audience."""
        endpoint = f"{self.base_url}/lists/{list_id}/merge-fields"
        return self._make_request("POST", endpoint, data=data)

    def get_merge_field(self, list_id: str, merge_id: str) -> dict:
        """Get information about a specific merge field."""
        endpoint = f"{self.base_url}/lists/{list_id}/merge-fields/{merge_id}"
        return self._make_request("GET", endpoint)

    def update_merge_field(self, list_id: str, merge_id: str, data: dict) -> dict:
        """Update a specific merge field."""
        endpoint = f"{self.base_url}/lists/{list_id}/merge-fields/{merge_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def delete_merge_field(self, list_id: str, merge_id: str) -> dict:
        """Delete a specific merge field."""
        endpoint = f"{self.base_url}/lists/{list_id}/merge-fields/{merge_id}"
        return self._make_request("DELETE", endpoint)

    def list_segments(self, list_id: str) -> dict:
        """Get information about all available segments for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments"
        return self._make_request("GET", endpoint)

    def add_segment(self, list_id: str, data: dict) -> dict:
        """Create a new segment in a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments"
        return self._make_request("POST", endpoint, data=data)

    def get_segment_info(self, list_id: str, segment_id: str) -> dict:
        """Get information about a specific segment."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments/{segment_id}"
        return self._make_request("GET", endpoint)

    def delete_segment(self, list_id: str, segment_id: str) -> dict:
        """Delete a specific segment in a list."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments/{segment_id}"
        return self._make_request("DELETE", endpoint)

    def update_segment(self, list_id: str, segment_id: str, data: dict) -> dict:
        """Update a specific segment in a list."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments/{segment_id}"
        return self._make_request("PATCH", endpoint, data=data)

    def batch_add_remove_members(self, list_id: str, segment_id: str, data: dict) -> dict:
        """Batch add/remove list members to static segment."""
        endpoint = f"{self.base_url}/lists/{list_id}/segments/{segment_id}"
        return self._make_request("POST", endpoint, data=data)

    def list_signup_forms(self, list_id: str) -> dict:
        """Get signup forms for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/signup-forms"
        return self._make_request("GET", endpoint)

    def customize_signup_form(self, list_id: str, data: dict) -> dict:
        """Customize a list's default signup form."""
        endpoint = f"{self.base_url}/lists/{list_id}/signup-forms"
        return self._make_request("POST", endpoint, data=data)

    def list_surveys(self, list_id: str) -> dict:
        """Get information about all available surveys for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/surveys"
        return self._make_request("GET", endpoint)

    def get_survey(self, list_id: str, survey_id: str) -> dict:
        """Get details about a specific survey."""
        endpoint = f"{self.base_url}/lists/{list_id}/surveys/{survey_id}"
        return self._make_request("GET", endpoint)

    def publish_survey(self, list_id: str, survey_id: str) -> dict:
        """Publish a survey that is in draft, unpublished, or has been previously published and edited."""
        endpoint = f"{self.base_url}/lists/{list_id}/surveys/{survey_id}/actions/publish"
        return self._make_request("POST", endpoint)

    def unpublish_survey(self, list_id: str, survey_id: str) -> dict:
        """Unpublish a survey that has been published."""
        endpoint = f"{self.base_url}/lists/{list_id}/surveys/{survey_id}/actions/unpublish"
        return self._make_request("POST", endpoint)

    def search_tags(self, list_id: str, name: Optional[str] = None) -> dict:
        """Search for tags on a list by name."""
        endpoint = f"{self.base_url}/lists/{list_id}/tag-search"
        params = {'name': name} if name else {}
        return self._make_request("GET", endpoint, params=params)

    def list_webhooks(self, list_id: str) -> dict:
        """Get information about all webhooks for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/webhooks"
        return self._make_request("GET", endpoint)

    def add_webhook(self, list_id: str, data: dict) -> dict:
        """Create a new webhook for a specific list."""
        endpoint = f"{self.base_url}/lists/{list_id}/webhooks"
        return self._make_request("POST", endpoint, data=data)

    def get_webhook_info(self, list_id: str, webhook_id: str) -> dict:
        """Get information about a specific webhook."""
        endpoint = f"{self.base_url}/lists/{list_id}/webhooks/{webhook_id}"
        return self._make_request("GET", endpoint)

    def delete_webhook(self, list_id: str, webhook_id: str) -> dict:
        """Delete a specific webhook in a list."""
        endpoint = f"{self.base_url}/lists/{list_id}/webhooks/{webhook_id}"
        return self._make_request("DELETE", endpoint)

    def update_webhook(self, list_id: str, webhook_id: str, data: dict) -> dict:
        """Update the settings for an existing webhook."""
        endpoint = f"{self.base_url}/lists/{list_id}/webhooks/{webhook_id}"
        return self._make_request("PATCH", endpoint, data=data)

def as_tools(configuration: MailchimpMarketingIntegrationConfiguration):
    """Convert MailchimpMarketing integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional, List, Dict
    
    integration = MailchimpMarketingIntegration(configuration)
    
    # Schema definitions
    class ListAccountExportsSchema(BaseModel):
        fields: Optional[List[str]] = Field(None, description="A comma-separated list of fields to return")
        exclude_fields: Optional[List[str]] = Field(None, description="A comma-separated list of fields to exclude")
        count: Optional[int] = Field(10, description="The number of records to return")
        offset: Optional[int] = Field(0, description="The number of records to skip")

    class CreateAccountExportSchema(BaseModel):
        include_stages: List[str] = Field(..., description="The stages of an account export to include")
        since_timestamp: Optional[str] = Field(None, description="An ISO 8601 date that will limit the export to only records created after a given time")

    class CampaignSchema(BaseModel):
        campaign_id: str = Field(..., description="The unique id for the campaign")

    class CampaignContentSchema(BaseModel):
        campaign_id: str = Field(..., description="The unique id for the campaign")
        data: Dict = Field(..., description="The content settings including html, plain_text, or template configuration")

    class ListSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")

    class MemberSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        subscriber_hash: str = Field(..., description="The MD5 hash of the lowercase version of the list member's email address")

    class SegmentSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        segment_id: str = Field(..., description="The unique id for the segment")

    class CampaignCreateSchema(BaseModel):
        data: Dict = Field(..., description="Campaign settings including type, settings, recipients")

    class CampaignUpdateSchema(BaseModel):
        campaign_id: str = Field(..., description="The unique id for the campaign")
        data: Dict = Field(..., description="The updated campaign settings")

    class CampaignScheduleSchema(BaseModel):
        campaign_id: str = Field(..., description="The unique id for the campaign")
        data: Dict = Field(..., description="Schedule settings including schedule_time, timewarp, batch_delivery")

    class CampaignTestEmailSchema(BaseModel):
        campaign_id: str = Field(..., description="The unique id for the campaign")
        data: Dict = Field(..., description="Test email settings including test_emails and send_type")

    class ListMemberActionSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        subscriber_hash: str = Field(..., description="The MD5 hash of the lowercase version of the list member's email address")
        data: Dict = Field(..., description="The member data to update")

    class WebhookSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        webhook_id: Optional[str] = Field(None, description="The unique id for the webhook")
        data: Optional[Dict] = Field(None, description="The webhook settings to update")

    class MemberEventSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        subscriber_hash: str = Field(..., description="The MD5 hash of the lowercase version of the list member's email address")
        data: Optional[Dict] = Field(None, description="Event data to add")

    class MemberNoteSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        subscriber_hash: str = Field(..., description="The MD5 hash of the lowercase version of the list member's email address")
        note_id: Optional[str] = Field(None, description="The unique id for the note")
        data: Optional[Dict] = Field(None, description="Note data to add or update")

    class InterestCategorySchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        interest_category_id: Optional[str] = Field(None, description="The unique id for the interest category")
        data: Optional[Dict] = Field(None, description="Interest category data")

    class InterestSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        interest_category_id: str = Field(..., description="The unique id for the interest category")
        interest_id: Optional[str] = Field(None, description="The unique id for the interest")
        data: Optional[Dict] = Field(None, description="Interest data")

    class MergeFieldSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        merge_id: Optional[str] = Field(None, description="The unique id for the merge field")
        data: Optional[Dict] = Field(None, description="Merge field data")

    class SegmentActionSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        segment_id: str = Field(..., description="The unique id for the segment")
        data: Dict = Field(..., description="Segment action data")

    class SurveySchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        survey_id: str = Field(..., description="The unique id for the survey")

    class TagSearchSchema(BaseModel):
        list_id: str = Field(..., description="The unique id for the list")
        name: Optional[str] = Field(None, description="Tag name to search for")

    class AudienceSchema(BaseModel):
        audience_id: str = Field(..., description="The unique id for the audience")

    # Create tools list
    tools = [
        StructuredTool(
            name="mailchimp_list_account_exports",
            description="Get a list of account exports",
            func=lambda **kwargs: integration.list_account_exports(**kwargs),
            args_schema=ListAccountExportsSchema
        ),
        StructuredTool(
            name="mailchimp_create_account_export",
            description="Create a new account export",
            func=lambda **kwargs: integration.create_account_export(**kwargs),
            args_schema=CreateAccountExportSchema
        ),
        StructuredTool(
            name="mailchimp_get_campaign_info",
            description="Get information about a specific campaign",
            func=lambda **kwargs: integration.get_campaign_info(**kwargs),
            args_schema=CampaignSchema
        ),
        StructuredTool(
            name="mailchimp_set_campaign_content",
            description="Set the content for a campaign",
            func=lambda **kwargs: integration.set_campaign_content(**kwargs),
            args_schema=CampaignContentSchema
        ),
        StructuredTool(
            name="mailchimp_list_audiences",
            description="Get information about all lists in the account",
            func=lambda: integration.list_audiences(),
            args_schema=AudienceSchema
        ),
        StructuredTool(
            name="mailchimp_get_audience_info",
            description="Get information about a specific audience",
            func=lambda **kwargs: integration.get_audience_info(**kwargs),
            args_schema=AudienceSchema
        ),
        StructuredTool(
            name="mailchimp_get_member_info",
            description="Get information about a specific list member",
            func=lambda **kwargs: integration.get_member_info(**kwargs),
            args_schema=MemberSchema
        ),
        StructuredTool(
            name="mailchimp_get_segment_info",
            description="Get information about a specific segment",
            func=lambda **kwargs: integration.get_segment_info(**kwargs),
            args_schema=SegmentSchema
        ),
        StructuredTool(
            name="mailchimp_create_campaign",
            description="Create a new Mailchimp campaign",
            func=lambda **kwargs: integration.create_campaign(**kwargs),
            args_schema=CampaignCreateSchema
        ),
        StructuredTool(
            name="mailchimp_update_campaign_settings",
            description="Update settings for a specific campaign",
            func=lambda **kwargs: integration.update_campaign_settings(**kwargs),
            args_schema=CampaignUpdateSchema
        ),
        StructuredTool(
            name="mailchimp_delete_campaign",
            description="Remove a campaign from your Mailchimp account",
            func=lambda **kwargs: integration.delete_campaign(**kwargs),
            args_schema=CampaignSchema
        ),
        StructuredTool(
            name="mailchimp_send_campaign",
            description="Send a Mailchimp campaign",
            func=lambda **kwargs: integration.send_campaign(**kwargs),
            args_schema=CampaignSchema
        ),
        StructuredTool(
            name="mailchimp_schedule_campaign",
            description="Schedule a campaign for delivery",
            func=lambda **kwargs: integration.schedule_campaign(**kwargs),
            args_schema=CampaignScheduleSchema
        ),
        StructuredTool(
            name="mailchimp_unschedule_campaign",
            description="Unschedule a scheduled campaign",
            func=lambda **kwargs: integration.unschedule_campaign(**kwargs),
            args_schema=CampaignSchema
        ),
        StructuredTool(
            name="mailchimp_send_test_email",
            description="Send a test email for a campaign",
            func=lambda **kwargs: integration.send_test_email(**kwargs),
            args_schema=CampaignTestEmailSchema
        ),
        StructuredTool(
            name="mailchimp_add_or_update_list_member",
            description="Add or update a list member",
            func=lambda **kwargs: integration.add_or_update_list_member(**kwargs),
            args_schema=ListMemberActionSchema
        ),
        StructuredTool(
            name="mailchimp_archive_list_member",
            description="Archive a list member",
            func=lambda **kwargs: integration.archive_list_member(**kwargs),
            args_schema=MemberSchema
        ),
        StructuredTool(
            name="mailchimp_delete_list_member",
            description="Delete all personally identifiable information related to a list member",
            func=lambda **kwargs: integration.delete_list_member(**kwargs),
            args_schema=MemberSchema
        ),
        StructuredTool(
            name="mailchimp_list_webhooks",
            description="Get information about all webhooks for a specific list",
            func=lambda **kwargs: integration.list_webhooks(**kwargs),
            args_schema=ListSchema
        ),
        StructuredTool(
            name="mailchimp_add_webhook",
            description="Create a new webhook for a specific list",
            func=lambda **kwargs: integration.add_webhook(**kwargs),
            args_schema=WebhookSchema
        ),
        StructuredTool(
            name="mailchimp_delete_webhook",
            description="Delete a specific webhook in a list",
            func=lambda **kwargs: integration.delete_webhook(**kwargs),
            args_schema=WebhookSchema
        ),
        # Member Events
        StructuredTool(
            name="mailchimp_list_member_events",
            description="Get events for a contact",
            func=lambda **kwargs: integration.list_member_events(**kwargs),
            args_schema=MemberSchema
        ),
        StructuredTool(
            name="mailchimp_add_member_event",
            description="Add an event for a list member",
            func=lambda **kwargs: integration.add_member_event(**kwargs),
            args_schema=MemberEventSchema
        ),
        
        # Member Notes
        StructuredTool(
            name="mailchimp_list_member_notes",
            description="Get recent notes for a specific list member",
            func=lambda **kwargs: integration.list_member_notes(**kwargs),
            args_schema=MemberSchema
        ),
        StructuredTool(
            name="mailchimp_add_member_note",
            description="Add a new note for a specific subscriber",
            func=lambda **kwargs: integration.add_member_note(**kwargs),
            args_schema=MemberNoteSchema
        ),
        StructuredTool(
            name="mailchimp_get_member_note",
            description="Get a specific note for a specific list member",
            func=lambda **kwargs: integration.get_member_note(**kwargs),
            args_schema=MemberNoteSchema
        ),
        StructuredTool(
            name="mailchimp_update_member_note",
            description="Update a specific note for a specific list member",
            func=lambda **kwargs: integration.update_member_note(**kwargs),
            args_schema=MemberNoteSchema
        ),
        StructuredTool(
            name="mailchimp_delete_member_note",
            description="Delete a specific note for a specific list member",
            func=lambda **kwargs: integration.delete_member_note(**kwargs),
            args_schema=MemberNoteSchema
        ),
        
        # Interest Categories
        StructuredTool(
            name="mailchimp_list_interest_categories",
            description="Get information about a list's interest categories",
            func=lambda **kwargs: integration.list_interest_categories(**kwargs),
            args_schema=ListSchema
        ),
        StructuredTool(
            name="mailchimp_create_interest_category",
            description="Create a new interest category",
            func=lambda **kwargs: integration.create_interest_category(**kwargs),
            args_schema=InterestCategorySchema
        ),
        StructuredTool(
            name="mailchimp_get_interest_category_info",
            description="Get information about a specific interest category",
            func=lambda **kwargs: integration.get_interest_category_info(**kwargs),
            args_schema=InterestCategorySchema
        ),
        StructuredTool(
            name="mailchimp_update_interest_category",
            description="Update a specific interest category",
            func=lambda **kwargs: integration.update_interest_category(**kwargs),
            args_schema=InterestCategorySchema
        ),
        StructuredTool(
            name="mailchimp_delete_interest_category",
            description="Delete a specific interest category",
            func=lambda **kwargs: integration.delete_interest_category(**kwargs),
            args_schema=InterestCategorySchema
        ),
        
        # Interests
        StructuredTool(
            name="mailchimp_list_interests_in_category",
            description="Get a list of this category's interests",
            func=lambda **kwargs: integration.list_interests_in_category(**kwargs),
            args_schema=InterestCategorySchema
        ),
        StructuredTool(
            name="mailchimp_add_interest_in_category",
            description="Create a new interest or 'group name' for a specific category",
            func=lambda **kwargs: integration.add_interest_in_category(**kwargs),
            args_schema=InterestSchema
        ),
        StructuredTool(
            name="mailchimp_get_interest_in_category",
            description="Get interests or 'group names' for a specific category",
            func=lambda **kwargs: integration.get_interest_in_category(**kwargs),
            args_schema=InterestSchema
        ),
        StructuredTool(
            name="mailchimp_update_interest_in_category",
            description="Update interests or 'group names' for a specific category",
            func=lambda **kwargs: integration.update_interest_in_category(**kwargs),
            args_schema=InterestSchema
        ),
        StructuredTool(
            name="mailchimp_delete_interest_in_category",
            description="Delete interests or group names in a specific category",
            func=lambda **kwargs: integration.delete_interest_in_category(**kwargs),
            args_schema=InterestSchema
        ),
        
        # Merge Fields
        StructuredTool(
            name="mailchimp_list_merge_fields",
            description="Get a list of all merge fields for an audience",
            func=lambda **kwargs: integration.list_merge_fields(**kwargs),
            args_schema=ListSchema
        ),
        StructuredTool(
            name="mailchimp_add_merge_field",
            description="Add a new merge field for a specific audience",
            func=lambda **kwargs: integration.add_merge_field(**kwargs),
            args_schema=MergeFieldSchema
        ),
        StructuredTool(
            name="mailchimp_get_merge_field",
            description="Get information about a specific merge field",
            func=lambda **kwargs: integration.get_merge_field(**kwargs),
            args_schema=MergeFieldSchema
        ),
        StructuredTool(
            name="mailchimp_update_merge_field",
            description="Update a specific merge field",
            func=lambda **kwargs: integration.update_merge_field(**kwargs),
            args_schema=MergeFieldSchema
        ),
        StructuredTool(
            name="mailchimp_delete_merge_field",
            description="Delete a specific merge field",
            func=lambda **kwargs: integration.delete_merge_field(**kwargs),
            args_schema=MergeFieldSchema
        ),
        
        # Segments
        StructuredTool(
            name="mailchimp_batch_add_remove_members",
            description="Batch add/remove list members to static segment",
            func=lambda **kwargs: integration.batch_add_remove_members(**kwargs),
            args_schema=SegmentActionSchema
        ),
        
        # Surveys
        StructuredTool(
            name="mailchimp_list_surveys",
            description="Get information about all available surveys for a specific list",
            func=lambda **kwargs: integration.list_surveys(**kwargs),
            args_schema=ListSchema
        ),
        StructuredTool(
            name="mailchimp_get_survey",
            description="Get details about a specific survey",
            func=lambda **kwargs: integration.get_survey(**kwargs),
            args_schema=SurveySchema
        ),
        StructuredTool(
            name="mailchimp_publish_survey",
            description="Publish a survey that is in draft, unpublished, or has been previously published and edited",
            func=lambda **kwargs: integration.publish_survey(**kwargs),
            args_schema=SurveySchema
        ),
        StructuredTool(
            name="mailchimp_unpublish_survey",
            description="Unpublish a survey that has been published",
            func=lambda **kwargs: integration.unpublish_survey(**kwargs),
            args_schema=SurveySchema
        ),
        
        # Tags
        StructuredTool(
            name="mailchimp_search_tags",
            description="Search for tags on a list by name",
            func=lambda **kwargs: integration.search_tags(**kwargs),
            args_schema=TagSearchSchema
        )
    ]

    return tools

