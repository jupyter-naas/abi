from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
import time

LOGO_URL = "https://wpforms.com/wp-content/uploads/cache/integrations/e102d25de690b520bb1136f4175d4570.png"

@dataclass
class BrevoIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Brevo integration.
    
    Attributes:
        api_key (str): Brevo API key
        base_url (str): Base URL for Brevo API. Defaults to "https://api.brevo.com"
        version (str): Version of the Brevo API. Defaults to "v3"
    """
    api_key: str
    base_url: str = "https://api.brevo.com"
    version: str = "v3"

class BrevoIntegration(Integration):
    """Brevo API integration client.
    
    This class provides methods to interact with Brevo's API endpoints
    for managing contacts, lists, and campaigns.
    
    Attributes:
        __configuration (BrevoIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    """

    __configuration: BrevoIntegrationConfiguration

    def __init__(self, configuration: BrevoIntegrationConfiguration):
        """Initialize Brevo client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.headers = {
            "api-key": self.__configuration.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, json: Dict = None) -> Dict:
        """Make HTTP request to Brevo API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            json (Dict, optional): JSON body for request
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}/{self.__configuration.version}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Brevo API request failed: {str(e)}")
    
    def get_all_contacts(self, limit: int = 100) -> List[Dict]:
        """Get all contacts from Brevo.
        
        Args:
            limit (int, optional): Number of contacts to retrieve per request. Defaults to 100.
            
        Returns:
            List[Dict]: List of contacts
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> contacts = integration.get_contacts(limit=50)
        """
        data = []
        offset = 0
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/contacts", params)
            contacts = result.get("contacts", [])
            data.extend(contacts)
            
            if len(contacts) == 0 or len(contacts) < limit:
                break
                
            offset += limit
            
        return data
    
    def get_contact(self, identifier: str, identifier_type: Optional[str] = None) -> Dict:
        """Get details for a specific contact.
        
        Args:
            identifier (str): Contact identifier (email, phone, ID etc.)
            identifier_type (str, optional): Type of identifier. Valid values are:
                - email_id (for EMAIL)
                - phone_id (for SMS) 
                - contact_id (for ID)
                - ext_id (for EXT_ID)
                - whatsapp_id (for WHATSAPP)
                - landline_number_id (for LANDLINE_NUMBER)
                If not provided, assumes identifier is an email_id, phone_id or contact_id.
                
        Returns:
            Dict: Contact details and recent statistics
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get by email
            >>> contact = integration.get_contact("user@example.com")
            >>> # Get by phone with explicit type
            >>> contact = integration.get_contact("+1234567890", "phone_id")
        """
        endpoint = f"/contacts/{identifier}"
        if identifier_type:
            endpoint += f"?identifierType={identifier_type}"
            
        return self._make_request("GET", endpoint)
    
    def create_contact(self, email: str, attributes: Dict = None, list_ids: List[int] = None) -> Dict:
        """Create or update a contact.
        
        Args:
            email (str): Contact's email address
            attributes (Dict, optional): Additional contact attributes
            list_ids (List[int], optional): List IDs to add contact to
            
        Returns:
            Dict: API response
        """
        data = {
            "email": email,
            "attributes": attributes or {},
            "listIds": list_ids or []
        }
        return self._make_request("POST", "/contacts", data)
    
    def update_contact(
        self, 
        identifier: str, 
        attributes: Dict = None,
        list_ids: List[int] = None,
        identifier_type: Optional[str] = None
    ) -> Dict:
        """Update an existing contact.
        
        Args:
            identifier (str): Contact identifier (email, ID, phone etc.)
            attributes (Dict, optional): Contact attributes to update
            list_ids (List[int], optional): List IDs to update contact's list membership
            identifier_type (str, optional): Type of identifier. Valid values are:
                - email_id (for EMAIL)
                - phone_id (for SMS) 
                - contact_id (for ID)
                - ext_id (for EXT_ID)
                - whatsapp_id (for WHATSAPP)
                - landline_number_id (for LANDLINE_NUMBER)
                If not provided, assumes identifier is an email or contact ID.
                
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Update by email
            >>> response = integration.update_contact(
            ...     "user@example.com",
            ...     attributes={"FIRSTNAME": "John", "LASTNAME": "Doe"},
            ...     list_ids=[1, 2]
            ... )
            >>> # Update by phone with explicit type
            >>> response = integration.update_contact(
            ...     "+1234567890",
            ...     attributes={"FIRSTNAME": "John"},
            ...     identifier_type="phone_id"
            ... )
        """
        endpoint = f"/contacts/{identifier}"
        if identifier_type:
            endpoint += f"?identifierType={identifier_type}"
            
        data = {}
        if attributes:
            data["attributes"] = attributes
        if list_ids:
            data["listIds"] = list_ids
            
        return self._make_request("PUT", endpoint, data)
    
    def delete_contact(
        self,
        identifier: str,
        identifier_type: Optional[str] = None
    ) -> Dict:
        """Delete a contact.
        
        Args:
            identifier (str): Contact identifier (email, ID, phone etc.)
            identifier_type (str, optional): Type of identifier. Valid values are:
                - email_id (for EMAIL)
                - phone_id (for SMS) 
                - contact_id (for ID)
                - ext_id (for EXT_ID)
                - whatsapp_id (for WHATSAPP)
                - landline_number_id (for LANDLINE_NUMBER)
                If not provided, assumes identifier is an email or contact ID.
                
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Delete by email
            >>> response = integration.delete_contact("user@example.com")
            >>> # Delete by phone with explicit type
            >>> response = integration.delete_contact(
            ...     "+1234567890",
            ...     identifier_type="phone_id"
            ... )
        """
        endpoint = f"/contacts/{identifier}"
        if identifier_type:
            endpoint += f"?identifierType={identifier_type}"
            
        return self._make_request("DELETE", endpoint)
    
    def get_contact_stats(
        self,
        identifier: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        identifier_type: Optional[str] = None
    ) -> Dict:
        """Get email campaign statistics for a contact.
        
        Args:
            identifier (str): Contact identifier (email, ID, phone etc.)
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            identifier_type (str, optional): Type of identifier. Valid values are:
                - email_id (for EMAIL)
                - phone_id (for SMS) 
                - contact_id (for ID)
                - ext_id (for EXT_ID)
                - whatsapp_id (for WHATSAPP)
                - landline_number_id (for LANDLINE_NUMBER)
                If not provided, assumes identifier is an email or contact ID.
                
        Returns:
            Dict: Campaign statistics for the contact
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get stats by email
            >>> stats = integration.get_contact_stats(
            ...     "user@example.com",
            ...     start_date="2023-01-01",
            ...     end_date="2023-12-31"
            ... )
            >>> # Get stats by phone with explicit type
            >>> stats = integration.get_contact_stats(
            ...     "+1234567890",
            ...     identifier_type="phone_id"
            ... )
        """
        endpoint = f"/contacts/{identifier}/campaignStats"
        params = {}
        
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if identifier_type:
            params["identifierType"] = identifier_type
            
        return self._make_request("GET", endpoint, params=params)

    def get_lists(
        self,
        limit: int = 10,
        offset: int = 0,
        sort: str = "desc"
    ) -> Dict:
        """Get all contact lists.
        
        Args:
            limit (int, optional): Number of lists to return per request. Defaults to 10.
            offset (int, optional): Index of the first list to return. Defaults to 0.
            sort (str, optional): Sort order - 'asc' or 'desc'. Defaults to 'desc'.
            
        Returns:
            Dict: Contact lists information
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> lists = integration.get_lists(limit=20)
        """
        endpoint = "/contacts/lists"
        params = {
            "limit": limit,
            "offset": offset,
            "sort": sort
        }
        
        return self._make_request("GET", endpoint, params=params)
    
    def get_list_details(self, list_id: int) -> Dict:
        """Get details for a specific contact list.
        
        Args:
            list_id (int): ID of the list to retrieve
            
        Returns:
            Dict: List details including name, folder ID, total contacts, etc.
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> list_details = integration.get_list_details(123)
        """
        endpoint = f"/contacts/lists/{list_id}"
        return self._make_request("GET", endpoint)
    
    def create_list(self, name: str, folder_id: Optional[int] = None) -> Dict:
        """Create a new contact list.
        
        Args:
            name (str): Name of the list
            folder_id (int, optional): ID of the folder to create the list in
            
        Returns:
            Dict: Created list details
        """
        data = {"name": name, "folderId": folder_id}
        return self._make_request("POST", "/contacts/lists", data)
    
    def update_list(self, list_id: int, name: str, folder_id: Optional[int] = None) -> Dict:
        """Update an existing contact list.
        
        Args:
            list_id (int): ID of the list to update
            name (str): New name for the list
            folder_id (int, optional): New folder ID for the list
            
        Returns:
            Dict: Updated list details
        """
        data = {"name": name, "folderId": folder_id}
        return self._make_request("PUT", f"/contacts/lists/{list_id}", data)
    
    def delete_list(self, list_id: int) -> Dict:
        """Delete an existing contact list.
        
        Args:
            list_id (int): ID of the list to delete
            
        Returns:
            Dict: API response
        """
        return self._make_request("DELETE", f"/contacts/lists/{list_id}")
    
    def get_contacts_in_list(self, list_id: int, limit: int = 100) -> List[Dict]:
        """Get all contacts in a specific list.
        
        Args:
            list_id (int): ID of the list to get contacts from
            limit (int, optional): Number of contacts to retrieve per request. Defaults to 100.
            
        Returns:
            List[Dict]: List of contacts in the specified list
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> contacts = integration.get_contacts_in_list(123, limit=50)
        """
        data = []
        offset = 0
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", f"/contacts/lists/{list_id}/contacts", params)
            contacts = result.get("contacts", [])
            data.extend(contacts)
            
            if len(contacts) == 0 or len(contacts) < limit:
                break
                
            offset += limit
            
        return data
    
    def add_contacts_to_list(self, list_id: int, contact_ids: List[int]) -> Dict:
        """Add existing contacts to a list.
        
        Args:
            list_id (int): ID of the list to add contacts to
            contact_ids (List[int]): List of contact IDs to add
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> response = integration.add_contacts_to_list(123, [456, 789])
        """
        data = {"ids": contact_ids}
        return self._make_request("POST", f"/contacts/lists/{list_id}/contacts/add", data)
    

    def remove_contacts_from_list(self, list_id: int, contact_ids: List[int]) -> Dict:
        """Remove contacts from a list.
        
        Args:
            list_id (int): ID of the list to remove contacts from
            contact_ids (List[int]): List of contact IDs to remove
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> response = integration.remove_contacts_from_list(123, [456, 789])
        """
        data = {"ids": contact_ids}
        return self._make_request("POST", f"/contacts/lists/{list_id}/contacts/remove", data)
    
    def get_email_campaigns(self, limit: int = 100) -> List[Dict]:
        """Get all email campaigns.
        
        Args:
            limit (int, optional): Number of campaigns to retrieve per request. Defaults to 100.
            
        Returns:
            List[Dict]: List of email campaigns
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> campaigns = integration.get_email_campaigns(limit=50)
        """
        data = []
        offset = 0
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/emailCampaigns", params)
            campaigns = result.get("campaigns", [])
            data.extend(campaigns)
            
            if len(campaigns) == 0 or len(campaigns) < limit:
                break
                
            offset += limit
            
        return data
    
    def get_email_campaign_report(self, campaign_id: int) -> Dict:
        """Get report for a specific email campaign.
        
        Args:
            campaign_id (int): ID of the email campaign
            
        Returns:
            Dict: Campaign report details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> report = integration.get_email_campaign_report(123)
        """
        return self._make_request("GET", f"/emailCampaigns/{campaign_id}")
    
    def get_sms_campaigns(self, limit: int = 100) -> List[Dict]:
        """Get all SMS campaigns.
        
        Args:
            limit (int, optional): Number of campaigns to retrieve per request. Defaults to 100.
            
        Returns:
            List[Dict]: List of SMS campaigns
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> campaigns = integration.get_sms_campaigns(limit=50)
        """
        data = []
        offset = 0
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/smsCampaigns", params)
            campaigns = result.get("campaigns", [])
            data.extend(campaigns)
            
            if len(campaigns) == 0 or len(campaigns) < limit:
                break
                
            offset += limit
            
        return data
    
    def get_sms_campaign(self, campaign_id: int) -> Dict:
        """Get details for a specific SMS campaign.
        
        Args:
            campaign_id (int): ID of the SMS campaign
            
        Returns:
            Dict: SMS campaign details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> campaign = integration.get_sms_campaign(123)
        """
        return self._make_request("GET", f"/smsCampaigns/{campaign_id}")
    
    def get_whatsapp_campaigns(self, limit: int = 100) -> List[Dict]:
        """Get all WhatsApp campaigns.
        
        Args:
            limit (int, optional): Number of campaigns to retrieve per request. Defaults to 100.
            
        Returns:
            List[Dict]: List of WhatsApp campaigns
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> campaigns = integration.get_whatsapp_campaigns(limit=50)
        """
        data = []
        offset = 0
        
        while True:
            params = {
                "limit": limit,
                "offset": offset
            }
            
            result = self._make_request("GET", "/whatsappCampaigns", params)
            campaigns = result.get("campaigns", [])
            data.extend(campaigns)
            
            if len(campaigns) == 0 or len(campaigns) < limit:
                break
                
            offset += limit
            
        return data
    
    def get_whatsapp_campaign(self, campaign_id: int) -> Dict:
        """Get details for a specific WhatsApp campaign.
        
        Args:
            campaign_id (int): ID of the WhatsApp campaign
            
        Returns:
            Dict: WhatsApp campaign details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> campaign = integration.get_whatsapp_campaign(123)
        """
        return self._make_request("GET", f"/whatsappCampaigns/{campaign_id}")
    
    def get_whatsapp_config(self) -> Dict:
        """Get WhatsApp API account configuration information.
        
        Returns:
            Dict: WhatsApp configuration details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> whatsapp_config = integration.get_whatsapp_config()
        """
        return self._make_request("GET", "/whatsappCampaigns/config")
    
    def get_whatsapp_templates(self) -> List[Dict]:
        """Get all WhatsApp templates.
        
        Returns:
            List[Dict]: List of WhatsApp templates
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> templates = integration.get_whatsapp_templates()
        """
        return self._make_request("GET", "/whatsappCampaigns/template-list")
    
    def get_senders(self) -> List[Dict]:
        """Get list of all senders configured in Brevo account.
        
        Returns:
            List[Dict]: List of sender configurations
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> senders = integration.get_senders()
        """
        return self._make_request("GET", "/senders")
    
    def get_domains(self) -> List[Dict]:
        """Get list of all domains configured in Brevo account.
        
        Returns:
            List[Dict]: List of domain configurations
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> domains = integration.get_domains()
        """
        return self._make_request("GET", "/senders/domains")
    
    def get_webhooks(self) -> List[Dict]:
        """Get list of all webhooks configured in Brevo account.
        
        Returns:
            List[Dict]: List of webhook configurations
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> webhooks = integration.get_webhooks()
        """
        return self._make_request("GET", "/webhooks")
    
    def get_webhook(self, webhook_id: int) -> Dict:
        """Get details for a specific webhook.
        
        Args:
            webhook_id (int): ID of the webhook to retrieve
            
        Returns:
            Dict: Webhook details and configuration
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> webhook = integration.get_webhook(123)
        """
        return self._make_request("GET", f"/webhooks/{webhook_id}")
    
    def get_account(self) -> Dict:
        """Get account information, plan and credits details.
        
        Returns:
            Dict: Account information including plan details and credits
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> account = integration.get_account()
        """
        return self._make_request("GET", "/account")
    
    def get_organization_activities(self) -> List[Dict]:
        """Get organization activity logs.
        
        Returns:
            List[Dict]: List of activity logs showing user actions
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> activities = integration.get_organization_activities()
        """
        return self._make_request("GET", "/organization/activities")
    
    def get_organization_users(self) -> List[Dict]:
        """Get list of all users in the organization.
        
        Returns:
            List[Dict]: List of users and their details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> users = integration.get_organization_users()
        """
        return self._make_request("GET", "/organization/invited/users")
    
    def get_user_permissions(self, email: str) -> Dict:
        """Get permissions for a specific user in the organization.
        
        Args:
            email (str): Email address of the user
            
        Returns:
            Dict: User's permission details and access rights
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> permissions = integration.get_user_permissions("user@example.com")
        """
        return self._make_request("GET", f"/organization/user/{email}/permissions")
    
    def revoke_user_invitation(self, email: str) -> Dict:
        """Revoke invitation or access for a user in the organization.
        
        Args:
            email (str): Email address of the user to revoke access from
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> response = integration.revoke_user_invitation("user@example.com")
        """
        return self._make_request("PUT", f"/organization/user/invitation/revoke/{email}")
    
    def resend_user_invitation(self, email: str) -> Dict:
        """Resend invitation to a user to join the organization.
        
        Args:
            email (str): Email address of the user to resend invitation to
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> response = integration.resend_user_invitation("user@example.com")
        """
        return self._make_request("PUT", f"/organization/user/invitation/resend/{email}")

    def cancel_user_invitation(self, email: str) -> Dict:
        """Cancel pending invitation for a user to join the organization.
        
        Args:
            email (str): Email address of the user whose invitation to cancel
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> response = integration.cancel_user_invitation("user@example.com")
        """
        return self._make_request("PUT", f"/organization/user/invitation/cancel/{email}")
    
    def update_user_permissions(
        self,
        email: str,
        all_features_access: bool = False,
        privileges: List[Dict[str, List[str]]] = None
    ) -> Dict:
        """Update permissions for an existing user in the organization.
        
        Args:
            email (str): Email address of the user to update permissions for
            all_features_access (bool, optional): Whether to grant access to all features.
                Defaults to False.
            privileges (List[Dict[str, List[str]]], optional): List of feature privileges.
                Each privilege should have 'feature' and 'permissions' keys.
                Required if all_features_access is False.
                
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Update with specific privileges
            >>> response = integration.update_user_permissions(
            ...     "user@example.com",
            ...     privileges=[{
            ...         "feature": "email_campaigns",
            ...         "permissions": ["create_edit_delete", "send_schedule_suspend"]
            ...     }, {
            ...         "feature": "contacts",
            ...         "permissions": ["view", "create_edit_delete"]
            ...     }]
            ... )
            >>> # Update to grant all features access
            >>> response = integration.update_user_permissions(
            ...     "user@example.com",
            ...     all_features_access=True
            ... )
        """
        data = {
            "allFeaturesAccess": all_features_access
        }
        
        if not all_features_access:
            if not privileges:
                raise ValueError("privileges must be provided when all_features_access is False")
            data["privileges"] = privileges
            
        return self._make_request("POST", f"/organization/user/update/permissions/{email}", data)
    
    def send_user_invitation(
        self,
        email: str,
        all_features_access: bool = False,
        privileges: List[Dict[str, List[str]]] = None
    ) -> Dict:
        """Send invitation to a user to join the organization.
        
        Args:
            email (str): Email address of the user to invite
            all_features_access (bool, optional): Whether to grant access to all features. 
                Defaults to False.
            privileges (List[Dict[str, List[str]]], optional): List of feature privileges.
                Each privilege should have 'feature' and 'permissions' keys.
                Required if all_features_access is False.
                
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Invite with specific privileges
            >>> response = integration.send_user_invitation(
            ...     "user@example.com",
            ...     privileges=[{
            ...         "feature": "email_campaigns",
            ...         "permissions": ["create_edit_delete"]
            ...     }]
            ... )
            >>> # Invite with all features access
            >>> response = integration.send_user_invitation(
            ...     "user@example.com",
            ...     all_features_access=True
            ... )
        """
        data = {
            "email": email,
            "allFeaturesAccess": all_features_access
        }
        
        if not all_features_access:
            if not privileges:
                raise ValueError("privileges must be provided when all_features_access is False")
            data["privileges"] = privileges
            
        return self._make_request("POST", "/organization/user/invitation/send", data)
    
    def get_companies(
        self,
        filters: Optional[Dict] = None,
        linked_contacts_ids: Optional[List[int]] = None,
        linked_deals_ids: Optional[List[str]] = None,
        modified_since: Optional[str] = None,
        created_since: Optional[str] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> Dict:
        """Get list of companies.
        
        Args:
            filters (Dict, optional): Filter by attributes. Example: {"attributes.owner": "123"}
            linked_contacts_ids (List[int], optional): Filter by linked contacts IDs
            linked_deals_ids (List[str], optional): Filter by linked deals IDs
            modified_since (str, optional): Filter companies modified after UTC date-time (YYYY-MM-DDTHH:mm:ss.SSSZ)
            created_since (str, optional): Filter companies created after UTC date-time (YYYY-MM-DDTHH:mm:ss.SSSZ)
            page (int, optional): Index of the first document of the page
            limit (int, optional): Number of documents per page
            sort (str, optional): Sort order - "asc" or "desc". Defaults to "desc" by creation date
            sort_by (str, optional): Field name to sort by
            
        Returns:
            Dict: List of companies matching the filters
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get all companies
            >>> companies = integration.get_companies()
            >>> # Get companies with filters
            >>> companies = integration.get_companies(
            ...     filters={"attributes.owner": "123"},
            ...     limit=10,
            ...     sort="asc",
            ...     sort_by="name"
            ... )
        """
        params = {}
        if filters:
            params["filters"] = filters
        if linked_contacts_ids:
            params["linkedContactsIds"] = linked_contacts_ids
        if linked_deals_ids:
            params["linkedDealsIds"] = linked_deals_ids
        if modified_since:
            params["modifiedSince"] = modified_since
        if created_since:
            params["createdSince"] = created_since
        if page:
            params["page"] = page
        if limit:
            params["limit"] = limit
        if sort:
            params["sort"] = sort
        if sort_by:
            params["sortBy"] = sort_by
            
        return self._make_request("GET", "/companies", params)
    
    def get_company(self, company_id: str) -> Dict:
        """Get details of a specific company.
        
        Args:
            company_id (str): Unique identifier of the company
            
        Returns:
            Dict: Company details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> company = integration.get_company("123")
        """
        return self._make_request("GET", f"/companies/{company_id}")
    
    def link_company(self, company_id: str, contact_ids: List[str] = None, deal_ids: List[str] = None) -> Dict:
        """Link contacts and deals to a company.
        
        Args:
            company_id (str): ID of the company to link
            contact_ids (List[str], optional): List of contact IDs to link
            deal_ids (List[str], optional): List of deal IDs to link
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Link contacts and deals
            >>> response = integration.link_company(
            ...     company_id="123",
            ...     contact_ids=["456", "789"],
            ...     deal_ids=["101", "102"]
            ... )
            >>> # Link only contacts
            >>> response = integration.link_company(
            ...     company_id="123",
            ...     contact_ids=["456", "789"]
            ... )
        """
        data = {
            "linkContactIds": contact_ids or [],
            "linkDealsIds": deal_ids or []
        }
        return self._make_request("PATCH", f"/companies/link-unlink/{company_id}", data)
    
    def unlink_company(self, company_id: str, contact_ids: List[str] = None, deal_ids: List[str] = None) -> Dict:
        """Unlink contacts and deals from a company.
        
        Args:
            company_id (str): ID of the company to unlink from
            contact_ids (List[str], optional): List of contact IDs to unlink
            deal_ids (List[str], optional): List of deal IDs to unlink
            
        Returns:
            Dict: API response
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Unlink contacts and deals
            >>> response = integration.unlink_company(
            ...     company_id="123",
            ...     contact_ids=["456", "789"],
            ...     deal_ids=["101", "102"]
            ... )
            >>> # Unlink only deals
            >>> response = integration.unlink_company(
            ...     company_id="123",
            ...     deal_ids=["101", "102"]
            ... )
        """
        data = {
            "unlinkContactIds": contact_ids or [],
            "unlinkDealsIds": deal_ids or []
        }
        return self._make_request("PATCH", f"/companies/link-unlink/{company_id}", data)
    
    def get_all_pipelines(self) -> Dict:
        """Get all CRM pipelines from Brevo.
        
        Returns:
            Dict: Dictionary containing pipeline details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> pipelines = integration.get_all_pipelines()
        """
        return self._make_request("GET", "/crm/pipeline/details/all")
    
    def get_pipeline(self, pipeline_id: str) -> Dict:
        """Get details of a specific pipeline.
        
        Args:
            pipeline_id (str): ID of the pipeline to get details for
            
        Returns:
            Dict: Pipeline details
        """
        return self._make_request("GET", f"/crm/pipeline/details/{pipeline_id}")
    
    def get_all_deals(
        self,
        filters: Optional[Dict] = None,
        modified_since: Optional[str] = None,
        created_since: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort: Optional[str] = None
    ) -> Dict:
        """Get all CRM deals from Brevo.
        
        Args:
            filters (Dict, optional): Filter criteria for deals. Supported filters:
                - attributes.deal_name: Filter by deal name
                - linkedCompaniesIds: Filter by linked company IDs
                - linkedContactsIds: Filter by linked contact IDs
            modified_since (str, optional): Filter deals modified after given UTC datetime
                (format: YYYY-MM-DDTHH:mm:ss.SSSZ)
            created_since (str, optional): Filter deals created after given UTC datetime
                (format: YYYY-MM-DDTHH:mm:ss.SSSZ)
            limit (int, optional): Number of deals per page. Defaults to 100.
            offset (int, optional): Index of first deal. Defaults to 0.
            sort (str, optional): Sort order ('asc' or 'desc'). Defaults to desc by creation date.
            
        Returns:
            Dict: Dictionary containing deals and pagination info
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get all deals
            >>> deals = integration.get_all_deals()
            >>> # Get deals with filters
            >>> deals = integration.get_all_deals(
            ...     filters={"attributes.deal_name": "Big Sale"},
            ...     modified_since="2023-01-01T00:00:00.000Z",
            ...     limit=50
            ... )
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if filters:
            for key, value in filters.items():
                params[f"filters[{key}]"] = value
                
        if modified_since:
            params["modifiedSince"] = modified_since
            
        if created_since:
            params["createdSince"] = created_since
            
        if sort:
            params["sort"] = sort
            
        return self._make_request("GET", "/crm/deals", params)
    
    def get_deal(self, deal_id: str) -> Dict:
        """Get details of a specific deal.
        
        Args:
            deal_id (str): ID of the deal to get details for
            
        Returns:
            Dict: Deal details
        """
        return self._make_request("GET", f"/crm/deals/{deal_id}")
    
    def get_all_tasks(
        self,
        filter_type: Optional[str] = None,
        filter_status: Optional[str] = None,
        filter_date: Optional[str] = None,
        filter_assign_to: Optional[str] = None,
        filter_contacts: Optional[str] = None,
        filter_deals: Optional[str] = None,
        filter_companies: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
        sort: Optional[str] = None,
        sort_by: Optional[str] = None
    ) -> Dict:
        """Get all tasks with optional filters.
        
        Args:
            filter_type (str, optional): Filter by task type (ID)
            filter_status (str, optional): Filter by task status
            filter_date (str, optional): Filter by date
            filter_assign_to (str, optional): Filter by assignee ID or email
            filter_contacts (str, optional): Filter by contact IDs
            filter_deals (str, optional): Filter by deal IDs
            filter_companies (str, optional): Filter by company IDs
            date_from (int, optional): Start timestamp in milliseconds for date range filter
            date_to (int, optional): End timestamp in milliseconds for date range filter
            offset (int, optional): Index of first document. Defaults to 0
            limit (int, optional): Number of documents per page. Defaults to 50
            sort (str, optional): Sort order ('asc' or 'desc'). Defaults to desc by creation
            sort_by (str, optional): Field name to sort by
            
        Returns:
            Dict: Dictionary containing tasks and pagination info
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get all tasks
            >>> tasks = integration.get_all_tasks()
            >>> # Get tasks with filters
            >>> tasks = integration.get_all_tasks(
            ...     filter_status="completed",
            ...     filter_assign_to="user@example.com",
            ...     limit=25
            ... )
        """
        params = {
            "offset": offset,
            "limit": limit
        }
        
        if filter_type:
            params["filter[type]"] = filter_type
        if filter_status:
            params["filter[status]"] = filter_status
        if filter_date:
            params["filter[date]"] = filter_date
        if filter_assign_to:
            params["filter[assignTo]"] = filter_assign_to
        if filter_contacts:
            params["filter[contacts]"] = filter_contacts
        if filter_deals:
            params["filter[deals]"] = filter_deals
        if filter_companies:
            params["filter[companies]"] = filter_companies
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if sort:
            params["sort"] = sort
        if sort_by:
            params["sortBy"] = sort_by
            
        return self._make_request("GET", "/crm/tasks", params)

    def get_task(self, task_id: str) -> Dict:
        """Get details of a specific task.
        
        Args:
            task_id (str): ID of the task to retrieve
            
        Returns:
            Dict: Task details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> task = integration.get_task("123")
        """
        return self._make_request("GET", f"/crm/tasks/{task_id}")
    
    def create_task(
        self,
        name: str,
        task_type_id: str,
        date: str,
        duration: Optional[int] = None,
        notes: Optional[str] = None,
        done: Optional[bool] = None,
        assign_to_id: Optional[str] = None,
        contact_ids: Optional[List[int]] = None,
        deal_ids: Optional[List[str]] = None,
        company_ids: Optional[List[str]] = None,
        reminder: Optional[Dict] = None
    ) -> Dict:
        """Create a new task.
        
        Args:
            name (str): Name of the task
            task_type_id (str): ID for type of task (e.g Call / Email / Meeting)
            date (str): Task due date and time in ISO format
            duration (int, optional): Duration of task in milliseconds (1 min = 60000 ms)
            notes (str, optional): Notes added to the task
            done (bool, optional): Whether task is marked as done
            assign_to_id (str, optional): User email or ID to assign task to
            contact_ids (List[int], optional): Contact IDs to link to task
            deal_ids (List[str], optional): Deal IDs to link to task
            company_ids (List[str], optional): Company IDs to link to task
            reminder (Dict, optional): Task reminder date/time
            
        Returns:
            Dict: Created task details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> task = integration.create_task(
            ...     name="Follow up call",
            ...     task_type_id="call",
            ...     date="2024-01-20T15:00:00Z",
            ...     duration=1800000,  # 30 minutes
            ...     notes="Discuss proposal",
            ...     assign_to_id="user@example.com",
            ...     contact_ids=[123, 456]
            ... )
        """
        data = {
            "name": name,
            "taskTypeId": task_type_id,
            "date": date
        }
        
        if duration is not None:
            data["duration"] = duration
        if notes:
            data["notes"] = notes
        if done is not None:
            data["done"] = done
        if assign_to_id:
            data["assignToId"] = assign_to_id
        if contact_ids:
            data["contactsIds"] = contact_ids
        if deal_ids:
            data["dealsIds"] = deal_ids
        if company_ids:
            data["companiesIds"] = company_ids
        if reminder:
            data["reminder"] = reminder
            
        return self._make_request("POST", "/crm/tasks", data)
    
    def update_task(self, task_id: str, data: Dict) -> Dict:
        """Update an existing task.
        
        Args:
            task_id (str): ID of the task to update
            data (Dict): Updated task data
            
        Returns:
            Dict: Updated task details
        """
        return self._make_request("PUT", f"/crm/tasks/{task_id}", data)
    
    def delete_task(self, task_id: str) -> Dict:
        """Delete a task.
        
        Args:
            task_id (str): ID of the task to delete
            
        Returns:
            Dict: Deleted task details
        """
        return self._make_request("DELETE", f"/crm/tasks/{task_id}")

    def get_all_notes(
        self,
        entity: Optional[str] = None,
        entity_ids: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
        sort: Optional[str] = None
    ) -> Dict:
        """Get all CRM notes with optional filters.
        
        Args:
            entity (str, optional): Filter by note entity type
            entity_ids (str, optional): Filter by note entity IDs
            date_from (int, optional): Start timestamp in milliseconds for date range filter
            date_to (int, optional): End timestamp in milliseconds for date range filter
            offset (int, optional): Index of first document. Defaults to 0
            limit (int, optional): Number of documents per page. Defaults to 50
            sort (str, optional): Sort order ('asc' or 'desc'). Defaults to desc by creation
            
        Returns:
            Dict: Dictionary containing notes and pagination info
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> # Get all notes
            >>> notes = integration.get_all_notes()
            >>> # Get notes with filters
            >>> notes = integration.get_all_notes(
            ...     entity="contact",
            ...     entity_ids="123,456",
            ...     limit=25,
            ...     sort="asc"
            ... )
        """
        params = {
            "offset": offset,
            "limit": limit
        }
        
        if entity:
            params["entity"] = entity
        if entity_ids:
            params["entityIds"] = entity_ids
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if sort:
            params["sort"] = sort
            
        return self._make_request("GET", "/crm/notes", params)
    
    def get_note(self, note_id: str) -> Dict:
        """Get details of a specific note.
        
        Args:
            note_id (str): ID of the note to retrieve
            
        Returns:
            Dict: Note details
        """
        return self._make_request("GET", f"/crm/notes/{note_id}")
    
    def create_note(
        self,
        text: str,
        contact_ids: Optional[List[int]] = None,
        deal_ids: Optional[List[str]] = None,
        company_ids: Optional[List[str]] = None
    ) -> Dict:
        """Create a new note in Brevo CRM.
        
        Args:
            text (str): Text content of the note (1-3000 characters)
            contact_ids (List[int], optional): List of contact IDs to link to the note
            deal_ids (List[str], optional): List of deal IDs to link to the note
            company_ids (List[str], optional): List of company IDs to link to the note
            
        Returns:
            Dict: Created note details
            
        Example:
            >>> integration = BrevoIntegration(config)
            >>> note = integration.create_note(
            ...     text="Called customer about renewal",
            ...     contact_ids=[123, 456],
            ...     deal_ids=["789"]
            ... )
        """
        data = {
            "text": text,
            "contactIds": contact_ids or [],
            "dealIds": deal_ids or [],
            "companyIds": company_ids or []
        }
        return self._make_request("POST", "/crm/notes", data)
    
    def update_note(self, note_id: str, data: Dict) -> Dict:
        """Update an existing note.
        
        Args:
            note_id (str): ID of the note to update
            data (Dict): Updated note data
            
        Returns:
            Dict: Updated note details
        """
        return self._make_request("PUT", f"/crm/notes/{note_id}", data)
    
    def delete_note(self, note_id: str) -> Dict:
        """Delete a note.
        
        Args:
            note_id (str): ID of the note to delete
            
        Returns:
            Dict: Deleted note details
        """
        return self._make_request("DELETE", f"/crm/notes/{note_id}")


def as_tools(configuration: BrevoIntegrationConfiguration):
    """Convert Brevo integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = BrevoIntegration(configuration)
    
    class GetAllContactsSchema(BaseModel):
        limit: int = Field(100, description="Maximum number of contacts to return per page")
    
    class GetContactSchema(BaseModel):
        identifier: str = Field(..., description="Contact identifier (email, ID, phone etc.)")
        identifier_type: str = Field(None, description="Type of identifier (email_id, phone_id, etc.)")

    class CreateContactSchema(BaseModel):
        email: str = Field(..., description="Email address of the contact")
        attributes: dict = Field(None, description="Additional contact attributes")
        list_ids: list[int] = Field(None, description="List IDs to add contact to")

    class UpdateContactSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the contact to update")
        data: Dict = Field(..., description="Updated contact data")

    class DeleteContactSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the contact to delete")

    class GetContactStatsSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the contact to get stats for")

    class GetListsSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of lists to return")

    class GetListDetailsSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to get details for")

    class CreateListSchema(BaseModel):
        name: str = Field(..., description="Name of the list")
        description: str = Field(..., description="Description of the list")
        contacts: List[str] = Field(..., description="List of contact IDs to add to the list")

    class UpdateListSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to update")
        data: Dict = Field(..., description="Updated list data")

    class DeleteListSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to delete")

    class GetContactsInListSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to get contacts for")

    class AddContactToListSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to add the contact to")
        contact_id: str = Field(..., description="ID of the contact to add to the list")

    class RemoveContactFromListSchema(BaseModel):
        list_id: str = Field(..., description="ID of the list to remove the contact from")
        contact_id: str = Field(..., description="ID of the contact to remove from the list")

    class GetEmailCampaignsSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of campaigns to return")

    class GetEmailCampaignReportSchema(BaseModel):
        campaign_id: str = Field(..., description="ID of the campaign to get report for")
    
    class GetSmsCampaignsSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of campaigns to return")

    class GetSmsCampaignReportSchema(BaseModel):
        campaign_id: str = Field(..., description="ID of the campaign to get report for")

    class GetWhatsappCampaignsSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of campaigns to return")

    class GetWhatsappCampaignReportSchema(BaseModel):
        campaign_id: str = Field(..., description="ID of the campaign to get report for")

    class GetWhatsappConfigurationSchema(BaseModel):
        pass

    class GetWhatsappTemplatesSchema(BaseModel):
        pass

    class GetSendersSchema(BaseModel):
        pass

    class GetDomainsSchema(BaseModel):
        pass

    class GetWebhooksSchema(BaseModel):
        pass
    
    class GetAccountSchema(BaseModel):
        pass
    
    class GetUserActivityLogsSchema(BaseModel):
        start_date: str = Field(..., description="Start date of the activity logs")
        end_date: str = Field(..., description="End date of the activity logs")
        limit: int = Field(25, description="Maximum number of activity logs to return")
        offset: int = Field(0, description="Index of the first activity log to return")

    class GetUsersSchema(BaseModel):
        pass

    class CheckUserSchema(BaseModel):
        email: str = Field(..., description="Email address of the user to check")

    class RevokeUserSchema(BaseModel):
        email: str = Field(..., description="Email address of the user to revoke")
        
    class ResendCancelUserInviteSchema(BaseModel):
        email: str = Field(..., description="Email address of the user to resend invite to")
        action: str = Field(..., description="Action to take ('resend' or 'cancel')")

    class SendUserInviteSchema(BaseModel):
        email: str = Field(..., description="Email address of the user to send invite to")

    class UpdateUserPermissionsSchema(BaseModel):
        email: str = Field(..., description="Email address of the user to update permissions for")
        permissions: List[str] = Field(..., description="List of permissions to update")

    class GetAllCompaniesSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of companies to return")

    class GetCompanySchema(BaseModel):
        company_id: str = Field(..., description="ID of the company to get")

    class CreateCompanySchema(BaseModel):
        name: str = Field(..., description="Name of the company")
        domain: str = Field(..., description="Domain of the company")
        address: str = Field(..., description="Address of the company")
        city: str = Field(..., description="City of the company")
        state: str = Field(..., description="State of the company")
        zip: str = Field(..., description="Zip code of the company")
        country: str = Field(..., description="Country of the company")

    class UpdateCompanySchema(BaseModel):
        company_id: str = Field(..., description="ID of the company to update")
        data: Dict = Field(..., description="Updated company data")

    class DeleteCompanySchema(BaseModel):
        company_id: str = Field(..., description="ID of the company to delete")

    class GetAllPipelinesSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of pipelines to return")

    class GetPipelineSchema(BaseModel):
        pipeline_id: str = Field(..., description="ID of the pipeline to get")

    class GetAllDealsSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of deals to return")

    class GetDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the deal to get")

    class CreateDealSchema(BaseModel):
        deal_name: str = Field(..., description="Name of the deal")
        pipeline_id: str = Field(..., description="ID of the pipeline to create the deal in")
        company_id: str = Field(..., description="ID of the company to associate with the deal")
        contact_ids: List[str] = Field(..., description="List of contact IDs to associate with the deal")
        deal_stage: str = Field(..., description="Stage of the deal")
        deal_amount: float = Field(..., description="Amount of the deal")
        deal_currency: str = Field(..., description="Currency of the deal")
        deal_close_date: str = Field(..., description="Close date of the deal")
    
    class UpdateDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the deal to update")
        data: Dict = Field(..., description="Updated deal data")
    
    class DeleteDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the deal to delete")

    class GetAllTasksSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of tasks to return")

    class GetTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to get")

    class CreateTaskSchema(BaseModel):
        task_name: str = Field(..., description="Name of the task")
        task_type: str = Field(..., description="Type of the task")
        task_due_date: str = Field(..., description="Due date of the task")
        task_status: str = Field(..., description="Status of the task")
        task_priority: str = Field(..., description="Priority of the task")
        task_description: str = Field(..., description="Description of the task")

    class UpdateTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to update")
        data: Dict = Field(..., description="Updated task data")

    class DeleteTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to delete")

    class GetAllNotesSchema(BaseModel):
        limit: int = Field(25, description="Maximum number of notes to return")

    class GetNoteSchema(BaseModel):
        note_id: str = Field(..., description="ID of the note to get")

    class CreateNoteSchema(BaseModel):
        text: str = Field(..., description="Text of the note")
        contact_ids: List[str] = Field(..., description="List of contact IDs to associate with the note")
        deal_ids: List[str] = Field(..., description="List of deal IDs to associate with the note")
        company_ids: List[str] = Field(..., description="List of company IDs to associate with the note")

    class UpdateNoteSchema(BaseModel):
        note_id: str = Field(..., description="ID of the note to update")
        data: Dict = Field(..., description="Updated note data")

    class DeleteNoteSchema(BaseModel):
        note_id: str = Field(..., description="ID of the note to delete")
    
    return [
        StructuredTool(
            name="get_all_contacts",
            description="Get all contacts from Brevo.",
            func=lambda limit: integration.get_all_contacts(limit=limit),
            args_schema=GetAllContactsSchema
        ),
        StructuredTool(
            name="get_contact",
            description="Get details for a specific contact.",
            func=lambda identifier, identifier_type: integration.get_contact(identifier, identifier_type),
            args_schema=GetContactSchema
        ),
        StructuredTool(
            name="create_contact",
            description="Create or update a contact.",
            func=lambda email, attributes, list_ids: integration.create_contact(email, attributes, list_ids),
            args_schema=CreateContactSchema
        ),
        StructuredTool(
            name="update_contact",
            description="Update an existing contact.",
            func=lambda contact_id, data: integration.update_contact(contact_id, data),
            args_schema=UpdateContactSchema
        ),
        StructuredTool(
            name="delete_contact",
            description="Delete a contact.",
            func=lambda contact_id: integration.delete_contact(contact_id),
            args_schema=DeleteContactSchema
        ),
        StructuredTool(
            name="get_contact_stats",
            description="Get stats for a contact.",
            func=lambda contact_id: integration.get_contact_stats(contact_id),
            args_schema=GetContactStatsSchema
        ),
        StructuredTool(
            name="get_lists",
            description="Get all lists.",
            func=lambda limit: integration.get_lists(limit=limit),
            args_schema=GetListsSchema
        ),
        StructuredTool(
            name="get_list_details",
            description="Get details for a list.",
            func=lambda list_id: integration.get_list_details(list_id),
            args_schema=GetListDetailsSchema
        ),
        StructuredTool(
            name="create_list",
            description="Create a new list.",
            func=lambda name, description, contacts: integration.create_list(name, description, contacts),
            args_schema=CreateListSchema
        ),
        StructuredTool(
            name="update_list",
            description="Update an existing list.",
            func=lambda list_id, data: integration.update_list(list_id, data),
            args_schema=UpdateListSchema
        ),
        StructuredTool(
            name="delete_list",
            description="Delete a list.",
            func=lambda list_id: integration.delete_list(list_id),
            args_schema=DeleteListSchema
        ),
        StructuredTool(
            name="get_contacts_in_list",
            description="Get contacts in a list.",
            func=lambda list_id: integration.get_contacts_in_list(list_id),
            args_schema=GetContactsInListSchema
        ),
        StructuredTool(
            name="add_contact_to_list",
            description="Add a contact to a list.",
            func=lambda list_id, contact_id: integration.add_contacts_to_list(list_id, contact_id),
            args_schema=AddContactToListSchema
        ),
        StructuredTool(
            name="remove_contact_from_list",
            description="Remove a contact from a list.",
            func=lambda list_id, contact_id: integration.remove_contacts_from_list(list_id, contact_id),
            args_schema=RemoveContactFromListSchema
        ),
        StructuredTool(
            name="get_email_campaigns",
            description="Get all email campaigns.",
            func=lambda limit: integration.get_email_campaigns(limit=limit),
            args_schema=GetEmailCampaignsSchema
        ),
        StructuredTool(
            name="get_email_campaign_report",
            description="Get report for an email campaign.",
            func=lambda campaign_id: integration.get_email_campaign_report(campaign_id),
            args_schema=GetEmailCampaignReportSchema
        ),
        StructuredTool(
            name="get_sms_campaigns",
            description="Get all SMS campaigns.",
            func=lambda limit: integration.get_sms_campaigns(limit=limit),
            args_schema=GetSmsCampaignsSchema
        ),
        StructuredTool(
            name="get_sms_campaign_report",
            description="Get report for an SMS campaign.",
            func=lambda campaign_id: integration.get_sms_campaign(campaign_id),
            args_schema=GetSmsCampaignReportSchema
        ),
        StructuredTool(
            name="get_whatsapp_campaigns",
            description="Get all WhatsApp campaigns.",
            func=lambda limit: integration.get_whatsapp_campaigns(limit=limit),
            args_schema=GetWhatsappCampaignsSchema
        ),
        StructuredTool(
            name="get_whatsapp_campaign_report",
            description="Get report for a WhatsApp campaign.",
            func=lambda campaign_id: integration.get_whatsapp_campaign(campaign_id),
            args_schema=GetWhatsappCampaignReportSchema
        ),
        StructuredTool(
            name="get_whatsapp_configuration",
            description="Get WhatsApp configuration.",
            func=integration.get_whatsapp_config,
            args_schema=GetWhatsappConfigurationSchema
        ),
        StructuredTool(
            name="get_whatsapp_templates",
            description="Get WhatsApp templates.",
            func=integration.get_whatsapp_templates,
            args_schema=GetWhatsappTemplatesSchema
        ),
        StructuredTool(
            name="get_senders",
            description="Get all senders.",
            func=integration.get_senders,
            args_schema=GetSendersSchema
        ),
        StructuredTool(
            name="get_domains",
            description="Get all domains.",
            func=integration.get_domains,
            args_schema=GetDomainsSchema
        ),
        StructuredTool(
            name="get_webhooks",
            description="Get all webhooks.",
            func=integration.get_webhooks,
            args_schema=GetWebhooksSchema
        ),
        StructuredTool(
            name="get_account",
            description="Get account details.",
            func=integration.get_account,
            args_schema=GetAccountSchema
        ),
        StructuredTool(
            name="get_user_activity_logs",
            description="Get user activity logs.",
            func=lambda start_date, end_date, limit, offset: integration.get_organization_activities(start_date, end_date, limit, offset),
            args_schema=GetUserActivityLogsSchema
        ),
        StructuredTool(
            name="get_users",
            description="Get all users in the organization.",
            func=integration.get_organization_users,
            args_schema=GetUsersSchema
        ),
        StructuredTool(
            name="check_user",
            description="Check if a user exists.",
            func=lambda email: integration.get_user_permissions(email),
            args_schema=CheckUserSchema
        ),
        StructuredTool(
            name="revoke_user",
            description="Revoke a user.",
            func=lambda email: integration.revoke_user_invitation(email),
            args_schema=RevokeUserSchema
        ),
        StructuredTool(
            name="resend_cancel_user_invite",
            description="Resend or cancel a user invite.",
            func=lambda email, action: integration.resend_user_invitation(email) if action == "resend" else integration.cancel_user_invitation(email),
            args_schema=ResendCancelUserInviteSchema
        ),
        StructuredTool(
            name="send_user_invite",
            description="Send a user invite.",
            func=lambda email: integration.resend_user_invitation(email),
            args_schema=SendUserInviteSchema
        ),
        StructuredTool(
            name="update_user_permissions",
            description="Update user permissions.",
            func=lambda email, permissions: integration.update_user_permissions(email, permissions),
            args_schema=UpdateUserPermissionsSchema
        ),
        StructuredTool(
            name="get_all_companies",
            description="Get all companies.",
            func=lambda limit: integration.get_companies(limit=limit),
            args_schema=GetAllCompaniesSchema
        ),
        StructuredTool(
            name="get_company",
            description="Get a company.",
            func=lambda company_id: integration.get_company(company_id),
            args_schema=GetCompanySchema
        ),
        StructuredTool(
            name="get_all_pipelines",
            description="Get all pipelines.",
            func=lambda limit: integration.get_all_pipelines(limit=limit),
            args_schema=GetAllPipelinesSchema
        ),
        StructuredTool(
            name="get_pipeline",
            description="Get a pipeline.",
            func=lambda pipeline_id: integration.get_pipeline(pipeline_id),
            args_schema=GetPipelineSchema
        ),
        StructuredTool(
            name="get_all_deals",
            description="Get all deals.",
            func=lambda limit: integration.get_all_deals(limit=limit),
            args_schema=GetAllDealsSchema
        ),
        StructuredTool(
            name="get_deal",
            description="Get a deal.",
            func=lambda deal_id: integration.get_deal(deal_id),
            args_schema=GetDealSchema
        ),
        StructuredTool(
            name="get_all_tasks",
            description="Get all tasks.",
            func=lambda limit: integration.get_all_tasks(limit=limit),
            args_schema=GetAllTasksSchema
        ),
        StructuredTool(
            name="get_task",
            description="Get a task.",
            func=lambda task_id: integration.get_task(task_id),
            args_schema=GetTaskSchema
        ),
        StructuredTool(
            name="create_task",
            description="Create a new task.",
            func=lambda task_name, task_type, task_due_date, task_status, task_priority, task_description: integration.create_task(task_name, task_type, task_due_date, task_status, task_priority, task_description),
            args_schema=CreateTaskSchema
        ),
        StructuredTool(
            name="update_task",
            description="Update an existing task.",
            func=lambda task_id, data: integration.update_task(task_id, data),
            args_schema=UpdateTaskSchema
        ),
        StructuredTool(
            name="delete_task",
            description="Delete a task.",
            func=lambda task_id: integration.delete_task(task_id),
            args_schema=DeleteTaskSchema
        ),
        StructuredTool(
            name="get_all_notes",
            description="Get all notes.",
            func=lambda limit: integration.get_all_notes(limit=limit),
            args_schema=GetAllNotesSchema
        ),
        StructuredTool(
            name="get_note",
            description="Get a note.",
            func=lambda note_id: integration.get_note(note_id),
            args_schema=GetNoteSchema
        ),
        StructuredTool(
            name="create_note",
            description="Create a new note.",
            func=lambda text, contact_ids, deal_ids, company_ids: integration.create_note(text, contact_ids, deal_ids, company_ids),
            args_schema=CreateNoteSchema
        ),
        StructuredTool(
            name="update_note",
            description="Update an existing note.",
            func=lambda note_id, data: integration.update_note(note_id, data),
            args_schema=UpdateNoteSchema
        ),
        StructuredTool(
            name="delete_note",
            description="Delete a note.",
            func=lambda note_id: integration.delete_note(note_id),
            args_schema=DeleteNoteSchema
        )
    ]