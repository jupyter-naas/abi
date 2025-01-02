from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime

LOGO_URL = "https://logo.clearbit.com/qonto.com"

@dataclass
class QontoIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Qonto integration.
    
    Attributes:
        organization_slug (str): Qonto organization identifier
        secret_key (str): Qonto API secret key
        base_url (str): Base URL for Qonto API. Defaults to "https://thirdparty.qonto.com/v2"
    """
    organization_slug: str
    secret_key: str
    base_url: str = "https://thirdparty.qonto.com/v2"

class QontoIntegration(Integration):
    """Qonto API integration client.
    
    This integration provides methods to interact with Qonto's API endpoints
    for banking and financial operations.
    """

    __configuration: QontoIntegrationConfiguration

    def __init__(self, configuration: QontoIntegrationConfiguration):
        """Initialize Qonto client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"{self.__configuration.organization_slug}:{self.__configuration.secret_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict:
        """Make HTTP request to Qonto API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Qonto API request failed: {str(e)}")
        
    def _get_all(self, endpoint: str, params: Dict = None, limit: int = 100) -> List[Dict]:
        """Get all records from a paginated endpoint.
        
        Args:
            endpoint (str): API endpoint path
            params (Dict, optional): Query parameters
            limit (int, optional): Maximum number of records to return. Defaults to 100
            
        Returns:
            List[Dict]: All records from the endpoint
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        all_records = []
        has_more = True
        current_page = 1
        params = params or {}
        
        while has_more and len(all_records) < limit:
            params["current_page"] = current_page
            response = self._make_request(endpoint, params=params)
            
            # Get records key from endpoint path (e.g. "transactions" from "/transactions")
            record_key = endpoint.strip("/").split("/")[-1]
            records = response.get(record_key, [])
            all_records.extend(records[:limit - len(all_records)])
            
            # Check if next page exists
            meta = response.get("meta", {})
            next_page = meta.get("next_page")
            
            if next_page is None:
                has_more = False
            else:
                current_page = int(next_page)

        return all_records

    def get_organization_details(self) -> Dict:
        """Get organization and its bank accounts
        
        Returns:
            Dict: Organization information
        """
        return self._make_request("/organization")

    def list_transactions(
        self,
        iban: Optional[str] = None,
        bank_account_id: Optional[str] = None,
        status: Optional[List[str]] = None,
        settled_at_from: Optional[str] = None,
        settled_at_to: Optional[str] = None,
        emitted_at_from: Optional[str] = None,
        emitted_at_to: Optional[str] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None,
        operation_type: Optional[List[str]] = None,
        side: Optional[str] = None,
        includes: Optional[List[str]] = None,
        with_attachments: Optional[bool] = None,
        sort_by: str = "settled_at:desc",
        limit: Optional[int] = 100
    ) -> List[Dict]:
        """Get list of transactions for an account.
        
        Args:
            iban (str, optional): Account IBAN. Use /v2/organization to get this parameter.
            bank_account_id (str, optional): The id of the bank account. Takes precedence over iban if both specified.
            status (List[str], optional): Filter by transaction status ("pending", "declined", "completed"). Defaults to ["completed"].
            settled_at_from (str, optional): Filter by settlement date from (ISO 8601 format)
            settled_at_to (str, optional): Filter by settlement date to (ISO 8601 format)
            emitted_at_from (str, optional): Filter by emission date from (ISO 8601 format)
            emitted_at_to (str, optional): Filter by emission date to (ISO 8601 format)
            updated_at_from (str, optional): Filter by update date from (ISO 8601 format)
            updated_at_to (str, optional): Filter by update date to (ISO 8601 format)
            operation_type (List[str], optional): Filter by operation types (e.g. ["card", "transfer", "income"])
            side (str, optional): Filter by transaction side ("credit" or "debit")
            includes (List[str], optional): Embed associated resources ("vat_details", "labels", "attachments")
            with_attachments (bool, optional): Filter transactions with attachments
            sort_by (str, optional): Sort field and order ("updated_at", "settled_at", "emitted_at" with ":asc" or ":desc")
            
        Returns:
            List[Dict]: List of transactions
            
        Raises:
            ValueError: If neither iban nor bank_account_id is provided
        """
        if not iban and not bank_account_id:
            raise ValueError("Either iban or bank_account_id must be provided")
            
        params = {}
        if iban:
            params["iban"] = iban
        if bank_account_id:
            params["bank_account_id"] = bank_account_id
        if status:
            params["status[]"] = status
        if settled_at_from:
            params["settled_at_from"] = settled_at_from
        if settled_at_to:
            params["settled_at_to"] = settled_at_to
        if emitted_at_from:
            params["emitted_at_from"] = emitted_at_from
        if emitted_at_to:
            params["emitted_at_to"] = emitted_at_to
        if updated_at_from:
            params["updated_at_from"] = updated_at_from
        if updated_at_to:
            params["updated_at_to"] = updated_at_to
        if operation_type:
            params["operation_type[]"] = operation_type
        if side:
            params["side"] = side
        if includes:
            params["includes[]"] = includes
        if with_attachments is not None:
            params["with_attachments"] = str(with_attachments).lower()
        params["sort_by"] = sort_by            
        return self._get_all("/transactions", params, limit)
    
    def get_transaction(self, transaction_id: str, includes: Optional[List[str]] = None) -> Dict:
        """Retrieve a single transaction by ID.
        
        Args:
            transaction_id (str): UUID of the transaction to retrieve
            includes (List[str], optional): Embed associated resources ("vat_details", "labels", "attachments")
            
        Returns:
            Dict: Transaction details
        """
        params = {}
        if includes:
            params["includes[]"] = includes
            
        response = self._make_request(f"/transactions/{transaction_id}", params=params)
        return response.get("transaction", {})
    
    def get_supplier_invoices(
        self,
        status: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        sort_by: str = "created_at:desc",
        limit: Optional[int] = 100
    ) -> Dict:
        """Retrieve supplier invoices for the organization.
        
        Args:
            status (str, optional): Filter by invoice status ('to_review', 'pending', 'scheduled', 'paid')
            created_at_from (str, optional): Filter by min created date (ISO 8601 format)
            created_at_to (str, optional): Filter by max created date (ISO 8601 format)
            sort_by (str, optional): Sort field and order (e.g. 'created_at:desc', 'payment_date:asc')
                Available fields: created_at, file_name, supplier_name, payment_date, due_date, 
                scheduled_date, total_amount
            limit (int, optional): Maximum number of records to return. Defaults to 100
        Returns:
            Dict: List of supplier invoices and pagination metadata
        """
        params = {
            "sort_by": sort_by
        }
        
        if status:
            params["status"] = status
        if created_at_from:
            params["created_at_from"] = created_at_from
        if created_at_to:
            params["created_at_to"] = created_at_to
            
        return self._get_all("/supplier_invoices", params, limit)
    
    def get_client_invoices(
        self,
        status: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        sort_by: str = "created_at:desc",
        limit: Optional[int] = 100
    ) -> Dict:
        """Retrieve client invoices for the organization.
        
        Args:
            status (str, optional): Filter by invoice status ('draft', 'unpaid', 'canceled', 'paid')
            created_at_from (str, optional): Filter by min created date (ISO 8601 format)
            created_at_to (str, optional): Filter by max created date (ISO 8601 format)
            sort_by (str, optional): Sort field and order (e.g. 'created_at:desc', 'created_at:asc')
            limit (int, optional): Maximum number of records to return. Defaults to 100
            
        Returns:
            Dict: List of client invoices and pagination metadata
        """
        params = {
            "sort_by": sort_by
        }
        
        if status:
            params["status"] = status
        if created_at_from:
            params["created_at_from"] = created_at_from
        if created_at_to:
            params["created_at_to"] = created_at_to
            
        return self._get_all("/client_invoices", params, limit)
    
    def list_clients(
        self,
        tax_identification_number: Optional[str] = None,
        vat_number: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None,
        sort_by: str = "name:asc",
        limit: Optional[int] = 100
    ) -> Dict:
        """Get list of clients for the organization.
        
        Args:
            tax_identification_number (str, optional): Filter by tax identification number
            vat_number (str, optional): Filter by VAT number
            email (str, optional): Filter by email address
            name (str, optional): Filter by client name (min 2 chars)
            sort_by (str, optional): Sort field and order ("name" or "created_at" with ":asc" or ":desc")
            limit (int, optional): Maximum number of records to return. Defaults to 100
            
        Returns:
            Dict: List of clients and pagination metadata
            
        Raises:
            ValueError: If name filter is less than 2 characters
        """
        if name and len(name) < 2:
            raise ValueError("Name filter must be at least 2 characters long")
            
        params = {
            "sort_by": sort_by
        }
        
        if tax_identification_number:
            params["tax_identification_number"] = tax_identification_number
        if vat_number:
            params["vat_number"] = vat_number
        if email:
            params["email"] = email
        if name:
            params["name"] = name
            
        return self._get_all("/clients", params, limit)
    
    def get_client(self, client_id: str) -> Dict:
        """Get details of a specific client by ID.
        
        Args:
            client_id (str): ID of the client to retrieve
            
        Returns:
            Dict: Client details including computed fields from Qonto
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._make_request(f"/clients/{client_id}")
    
    def list_cards(
        self,
        bank_account_ids: Optional[List[str]] = None,
        card_levels: Optional[List[str]] = None,
        holder_ids: Optional[List[str]] = None,
        ids: Optional[List[str]] = None,
        query: Optional[str] = None,
        sort_by: str = "status:asc",
        statuses: Optional[List[str]] = None,
        limit: Optional[int] = 100
    ) -> List[Dict]:
        """Get list of cards for the organization.
        
        This endpoint retrieves all cards that can be viewed by the authenticated membership.
        Note: This API is in beta.
        
        Args:
            bank_account_ids (List[str], optional): Filter by bank account IDs
            card_levels (List[str], optional): Filter by card levels ("standard", "plus", "metal", "virtual", "flash", "advertising")
            holder_ids (List[str], optional): Filter by cardholder membership IDs
            ids (List[str], optional): Filter by card IDs
            query (str, optional): Text search on fields (first_name, last_name, card id/nickname/last_digits/status/pre_expires_at/exp_year/exp_month)
            sort_by (str, optional): Sort field and order ("status", "nickname", "last_activity_at", "created_at" with ":asc" or ":desc")
            statuses (List[str], optional): Filter by statuses ("pending", "live", "paused", "stolen", "lost", "pin_blocked")
            
        Returns:
            List[Dict]: List of card details
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        params = {
            "page": 1,
            "per_page": 100,
            "sort_by": sort_by
        }
        
        if bank_account_ids:
            params["bank_account_ids[]"] = bank_account_ids
        if card_levels:
            params["card_levels[]"] = card_levels
        if holder_ids:
            params["holder_ids[]"] = holder_ids
        if ids:
            params["ids[]"] = ids
        if query:
            params["query"] = query
        if statuses:
            params["statuses[]"] = statuses
            
        return self._get_all("/cards", params, limit)
    
    def get_card_data_view(self, card_id: str) -> Dict:
        """Get URL for card data view iframe.
        
        This endpoint retrieves a URL that can be displayed in an iframe to view
        the card preview with its details.
        Note: This API is in beta.
        
        Args:
            card_id (str): ID of the card to view
            
        Returns:
            Dict: Response containing the URL for the card data view
            
        Raises:
            IntegrationConnectionError: If request fails
            
        Example:
            Recommended iframe size:
            - Height: 460px
            - Width: 504px
        """
        return self._make_request(f"/cards/{card_id}/data_view")
    
    def list_beneficiaries(
        self,
        iban: Optional[List[str]] = None,
        status: Optional[List[str]] = None,
        trusted: Optional[bool] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None,
        sort_by: str = "updated_at:desc",
        limit: Optional[int] = 100
    ) -> List[Dict]:
        """Get list of beneficiaries.
        
        Args:
            iban (List[str], optional): Filter by list of IBANs
            status (List[str], optional): Filter by status ("pending", "validated", "declined")
            trusted (bool, optional): Filter by trusted status
            updated_at_from (str, optional): Filter by min updated date (ISO 8601 format)
            updated_at_to (str, optional): Filter by max updated date (ISO 8601 format)
            sort_by (str, optional): Sort field and order ("updated_at:asc" or "updated_at:desc")
            
        Returns:
            List[Dict]: List of beneficiaries. Each beneficiary contains:
                - trusted (bool): Whether automated transfers are allowed
                - created_at (str): UTC timestamp of creation
                - updated_at (str): UTC timestamp of last update
                - status (str): Status of beneficiary (pending/validated/declined)
                - bank_account (Dict): Bank account details depending on type:
                    - SEPA/Swift BIC: iban, currency, bic
                    - Swift code: account_number, swift_sort_code, intermediary_bank_bic, currency
                    - Swift routing: account_number, routing_number, intermediary_bank_bic, currency
        """
        params = {
            "sort_by": sort_by
        }
        
        if iban:
            params["iban[]"] = iban
        if status:
            params["status[]"] = status
        if trusted is not None:
            params["trusted"] = str(trusted).lower()
        if updated_at_from:
            params["updated_at_from"] = updated_at_from
        if updated_at_to:
            params["updated_at_to"] = updated_at_to
            
        return self._get_all("/beneficiaries", params, limit)
    
    def get_beneficiary(self, beneficiary_id: str) -> Dict:
        """Get details of a single beneficiary.
        
        Args:
            beneficiary_id (str): UUID of the beneficiary to retrieve
            
        Returns:
            Dict: Beneficiary details containing:
                - trusted (bool): Whether automated transfers are allowed
                - created_at (str): UTC timestamp of creation
                - updated_at (str): UTC timestamp of last update
                - status (str): Status of beneficiary (pending/validated/declined)
                - bank_account (Dict): Bank account details depending on type:
                    - SEPA/Swift BIC: iban, currency, bic
                    - Swift code: account_number, swift_sort_code, intermediary_bank_bic, currency
                    - Swift routing: account_number, routing_number, intermediary_bank_bic, currency
        """
        return self._make_request(f"/beneficiaries/{beneficiary_id}")
    
    def list_external_transfers(
        self,
        status: Optional[List[str]] = None,
        beneficiary_ids: Optional[List[str]] = None,
        updated_at_from: Optional[str] = None,
        updated_at_to: Optional[str] = None,
        scheduled_date_from: Optional[str] = None,
        scheduled_date_to: Optional[str] = None,
        sort_by: str = "updated_at:desc",
        limit: Optional[int] = 100
    ) -> List[Dict]:
        """Get list of external transfers.
        
        Args:
            status (List[str], optional): Filter by transfer status ("pending", "processing", 
                "canceled", "declined", "settled")
            beneficiary_ids (List[str], optional): Filter by list of beneficiary IDs
            updated_at_from (str, optional): Filter by min update date (ISO 8601 format)
            updated_at_to (str, optional): Filter by max update date (ISO 8601 format)
            scheduled_date_from (str, optional): Filter by min scheduled date (YYYY-MM-DD)
            scheduled_date_to (str, optional): Filter by max scheduled date (YYYY-MM-DD)
            sort_by (str, optional): Sort field and order ("updated_at" or "scheduled_date" 
                with ":asc" or ":desc"). Defaults to "updated_at:desc"
            
        Returns:
            List[Dict]: List of external transfers containing:
                - initiator_id (str): ID of membership that initiated the transfer
                - debit_iban (str): IBAN of source account
                - debit_amount (str): Amount debited from Qonto account
                - debit_amount_cents (int): Debit amount in cents
                - debit_currency (str): Currency code (EUR)
                - credit_amount (str): Amount credited to beneficiary
                - credit_amount_cents (int): Credit amount in cents
                - credit_currency (str): Currency code for credit
                - rate_applied (str): FX rate if applicable
                - created_at (str): UTC timestamp of creation
                - processed_at (str): UTC timestamp of processing start
                - completed_at (str): UTC timestamp of completion
                - scheduled_date (str): Scheduled execution date (YYYY-MM-DD)
                - status (str): Current status
        """
        params = {
            "sort_by": sort_by
        }
        
        if status:
            params["status[]"] = status
        if beneficiary_ids:
            params["beneficiary_ids[]"] = beneficiary_ids
        if updated_at_from:
            params["updated_at_from"] = updated_at_from
        if updated_at_to:
            params["updated_at_to"] = updated_at_to
        if scheduled_date_from:
            params["scheduled_date_from"] = scheduled_date_from
        if scheduled_date_to:
            params["scheduled_date_to"] = scheduled_date_to
            
        return self._get_all("/external_transfers", params, limit)
    
    def get_external_transfer(self, transfer_id: str) -> Dict:
        """Get details of a specific external transfer.
        
        Args:
            transfer_id (str): UUID of the external transfer to retrieve
            
        Returns:
            Dict: External transfer details containing:
                - initiator_id (str): ID of membership that initiated the transfer
                - debit_iban (str): IBAN of source account
                - debit_amount (str): Amount debited from Qonto account
                - debit_amount_cents (int): Debit amount in cents
                - debit_currency (str): Currency code (EUR)
                - credit_amount (str): Amount credited to beneficiary
                - credit_amount_cents (int): Credit amount in cents
                - credit_currency (str): Currency code for credit
                - rate_applied (str): FX rate if applicable
                - created_at (str): UTC timestamp of creation
                - processed_at (str): UTC timestamp of processing start
                - completed_at (str): UTC timestamp of completion
                - scheduled_date (str): Scheduled execution date (YYYY-MM-DD)
                - status (str): Current status ("pending", "processing", "canceled", 
                    "declined", "settled")
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._make_request(f"/external_transfers/{transfer_id}")
    

    def get_attachment(self, attachment_id: str) -> Dict:
        """Get details of a specific attachment.
        
        Args:
            attachment_id (str): UUID of the attachment to retrieve
            
        Returns:
            Dict: Attachment details containing:
                - id (str): Unique identifier of the attachment
                - created_at (str): UTC timestamp of creation
                - file_name (str): Original file name
                - file_size (int): File size in bytes
                - file_content_type (str): MIME type of the file
                - url (str): Temporary download URL (valid for 30 minutes)
                - probative_url (str): Temporary download URL for probative version
                
        Raises:
            IntegrationConnectionError: If request fails
            
        Note:
            The download URLs are only valid for 30 minutes. To download after that,
            you need to make another call to get fresh URLs.
        """
        return self._make_request(f"/attachments/{attachment_id}")
    
    def list_labels(self, limit: Optional[int] = 100) -> List[Dict]:
        """Get all labels within the organization.
        
        Returns:
            List[Dict]: List of labels containing:
                - id (str): Unique identifier of the label
                - name (str): Label name
                - parent_id (str): ID of parent label if nested
                - created_at (str): UTC timestamp of creation
                - updated_at (str): UTC timestamp of last update
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._get_all("/labels", limit=limit)
    
    def get_label(self, label_id: str) -> Dict:
        """Get details of a specific label.
        
        Args:
            label_id (str): Unique identifier of the label to retrieve
            
        Returns:
            Dict: Label details containing:
                - id (str): Unique identifier of the label
                - name (str): Label name
                - parent_id (str): ID of parent label if nested
                - created_at (str): UTC timestamp of creation
                - updated_at (str): UTC timestamp of last update
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._make_request(f"/labels/{label_id}")

    def list_memberships(self, limit: Optional[int] = 100) -> List[Dict]:
        """Get all memberships within the organization.
        
        Returns:
            List[Dict]: List of memberships containing:
                - id (str): Unique identifier of the membership
                - first_name (str): First name of the member
                - last_name (str): Last name of the member 
                - role (str): Role of the member (owner, admin, manager, reporting, employee)
                - residence_country (str, optional): Residential country (Spain companies only)
                - birthdate (str, optional): Date of birth (Spain companies only)
                - nationality (str, optional): Nationality (Spain companies only)
                - ubo (bool, optional): Ultimate Beneficiary Owner status (Spain companies only)
                - birth_country (str, optional): Birth country (Spain companies only)
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._get_all("/memberships", limit=limit)
    
    def get_membership(self) -> Dict:
        """Get details of the authenticated membership.
        
        Returns:
            Dict: Membership details containing:
                - id (str): The membership's id
                - first_name (str): First name of the member
                - last_name (str): Last name of the member
                - email (str): Email address
                - phone_number (str): Phone number
                - position (str): Professional position (e.g. CEO)
                - status (str): Status of the membership (e.g. active)
                - role (str): Permissions role (owner, admin, etc)
                - locale (str): Language preference
                - team_id (str): ID of team membership belongs to
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._make_request("/membership")

    def list_transaction_attachments(self, transaction_id: str, limit: Optional[int] = 100) -> List[Dict]:
        """Get list of attachments for a transaction.
        
        Args:
            transaction_id (str): UUID of the transaction
            
        Returns:
            List[Dict]: List of attachments containing:
                - id (str): Unique identifier of the attachment
                - created_at (str): Creation date (ISO 8601)
                - file_name (str): Original file name
                - file_size (int): File size in bytes
                - file_content_type (str): MIME type of the file
                - url (str): Temporary download URL (valid for 30 minutes)
                - probative_url (str, optional): Temporary download URL for PAdES compliant version
                
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._get_all(f"/transactions/{transaction_id}/attachments", limit=limit)
    
    def list_teams(self, limit: Optional[int] = 25) -> Dict:
        """Get list of teams within the organization.
        
        Args:
            page (int, optional): Page number for pagination. Defaults to 1
            per_page (int, optional): Number of items per page (max 100). Defaults to 25
            
        Returns:
            Dict: Response containing:
                - teams (List[Dict]): List of teams with:
                    - id (str): Team identifier
                    - name (str): Team name
                - meta (Dict): Pagination metadata
                
        Raises:
            IntegrationConnectionError: If request fails
        """       
        return self._get_all("/teams", limit=limit)
    
    def list_statements(
        self,
        bank_account_ids: Optional[List[str]] = None,
        ibans: Optional[List[str]] = None,
        period_from: Optional[str] = None,
        period_to: Optional[str] = None,
        sort_by: str = "period:desc",
        limit: Optional[int] = 100
    ) -> Dict:
        """Get list of statements for the organization.
        
        Args:
            bank_account_ids (List[str], optional): Filter by bank account IDs.
                Mutually exclusive with ibans parameter.
            ibans (List[str], optional): Filter by account IBANs.
                Mutually exclusive with bank_account_ids parameter.
            period_from (str, optional): Start of statement period (format: MM-YYYY)
            period_to (str, optional): End of statement period (format: MM-YYYY)
            sort_by (str, optional): Sort field and order ("period:asc" or "period:desc").
                Defaults to "period:desc"
            limit (int, optional): Maximum number of records to return. Defaults to 100
        Returns:
            Dict: Response containing list of statements and pagination metadata
            
        Raises:
            ValueError: If both bank_account_ids and ibans are provided
            IntegrationConnectionError: If request fails
        """
        if bank_account_ids and ibans:
            raise ValueError("bank_account_ids and ibans parameters are mutually exclusive")
            
        params = {
            "sort_by": sort_by
        }
        
        if bank_account_ids:
            params["bank_account_ids[]"] = bank_account_ids
        if ibans:
            params["ibans[]"] = ibans
        if period_from:
            params["period_from"] = period_from
        if period_to:
            params["period_to"] = period_to
            
        return self._get_all("/statements", params, limit)
    
    def get_statement(self, statement_id: str) -> Dict:
        """Get details of a specific statement by ID.
        
        Args:
            statement_id (str): ID of the statement to retrieve
            
        Returns:
            Dict: Statement details
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        return self._make_request(f"/statements/{statement_id}")
    
def as_tools(configuration: QontoIntegrationConfiguration):
    """Convert Qonto integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional, List
    
    integration = QontoIntegration(configuration)

    class GetOrganizationSchema(BaseModel):
        pass

    class ListTransactionsSchema(BaseModel):
        iban: Optional[str] = Field(None, description="Account IBAN")
        bank_account_id: Optional[str] = Field(None, description="Bank account ID")
        status: Optional[List[str]] = Field(None, description="Transaction status (pending, declined, completed)")
        settled_at_from: Optional[str] = Field(None, description="Filter by settlement date from (ISO 8601)")
        settled_at_to: Optional[str] = Field(None, description="Filter by settlement date to (ISO 8601)")
        emitted_at_from: Optional[str] = Field(None, description="Filter by emission date from (ISO 8601)")
        emitted_at_to: Optional[str] = Field(None, description="Filter by emission date to (ISO 8601)")
        updated_at_from: Optional[str] = Field(None, description="Filter by update date from (ISO 8601)")
        updated_at_to: Optional[str] = Field(None, description="Filter by update date to (ISO 8601)")
        operation_type: Optional[List[str]] = Field(None, description="Filter by operation types (card, transfer, income)")
        side: Optional[str] = Field(None, description="Filter by transaction side (credit or debit)")
        includes: Optional[List[str]] = Field(None, description="Embed associated resources (vat_details, labels, attachments)")
        with_attachments: Optional[bool] = Field(None, description="Filter transactions with attachments")
        sort_by: str = Field("settled_at:desc", description="Sort field and order")
        limit: Optional[int] = 100

    class GetTransactionSchema(BaseModel):
        transaction_id: str = Field(..., description="UUID of the transaction to retrieve")
        includes: Optional[List[str]] = Field(None, description="Embed associated resources (vat_details, labels, attachments)")

    class GetSupplierInvoicesSchema(BaseModel):
        status: Optional[str] = Field(None, description="Filter by invoice status (to_review, pending, scheduled, paid)")
        created_at_from: Optional[str] = Field(None, description="Filter by min created date (ISO 8601)")
        created_at_to: Optional[str] = Field(None, description="Filter by max created date (ISO 8601)")
        sort_by: str = Field("created_at:desc", description="Sort field and order")
        limit: Optional[int] = 100

    class GetClientInvoicesSchema(BaseModel):
        status: Optional[str] = Field(None, description="Filter by invoice status (draft, unpaid, canceled, paid)")
        created_at_from: Optional[str] = Field(None, description="Filter by min created date (ISO 8601)")
        created_at_to: Optional[str] = Field(None, description="Filter by max created date (ISO 8601)")
        sort_by: str = Field("created_at:desc", description="Sort field and order")
        limit: Optional[int] = 100

    class ListClientsSchema(BaseModel):
        tax_identification_number: Optional[str] = Field(None, description="Filter by tax identification number")
        vat_number: Optional[str] = Field(None, description="Filter by VAT number")
        email: Optional[str] = Field(None, description="Filter by email address")
        name: Optional[str] = Field(None, description="Filter by client name (min 2 chars)")
        sort_by: str = Field("name:asc", description="Sort field and order")
        limit: Optional[int] = 100

    class GetClientSchema(BaseModel):
        client_id: str = Field(..., description="ID of the client to retrieve")

    class ListCardsSchema(BaseModel):
        bank_account_ids: Optional[List[str]] = Field(None, description="Filter by bank account IDs")
        card_levels: Optional[List[str]] = Field(None, description="Filter by card levels")
        holder_ids: Optional[List[str]] = Field(None, description="Filter by cardholder membership IDs")
        ids: Optional[List[str]] = Field(None, description="Filter by card IDs")
        query: Optional[str] = Field(None, description="Text search on fields")
        sort_by: str = Field("status:asc", description="Sort field and order")
        statuses: Optional[List[str]] = Field(None, description="Filter by card statuses")
        limit: Optional[int] = 100
    class GetCardDataViewSchema(BaseModel):
        card_id: str = Field(..., description="ID of the card to view")

    class ListBeneficiariesSchema(BaseModel):
        iban: Optional[List[str]] = Field(None, description="Filter by list of IBANs")
        status: Optional[List[str]] = Field(None, description="Filter by status (pending, validated, declined)")
        trusted: Optional[bool] = Field(None, description="Filter by trusted status")
        updated_at_from: Optional[str] = Field(None, description="Filter by min updated date (ISO 8601)")
        updated_at_to: Optional[str] = Field(None, description="Filter by max updated date (ISO 8601)")
        sort_by: str = Field("updated_at:desc", description="Sort field and order")
        limit: Optional[int] = 100
    class GetBeneficiarySchema(BaseModel):
        beneficiary_id: str = Field(..., description="UUID of the beneficiary to retrieve")

    class GetAttachmentSchema(BaseModel):
        attachment_id: str = Field(..., description="UUID of the attachment to retrieve")

    class ListLabelsSchema(BaseModel):
        pass

    class GetLabelSchema(BaseModel):
        label_id: str = Field(..., description="Unique identifier of the label to retrieve")

    class ListMembershipsSchema(BaseModel):
        limit: Optional[int] = 100

    class GetMembershipSchema(BaseModel):
        pass

    class ListTransactionAttachmentsSchema(BaseModel):
        transaction_id: str = Field(..., description="UUID of the transaction")
        limit: Optional[int] = 100

    class ListTeamsSchema(BaseModel):
        limit: Optional[int] = 25

    class ListStatementsSchema(BaseModel):
        bank_account_ids: Optional[List[str]] = Field(None, description="Filter by bank account IDs")
        ibans: Optional[List[str]] = Field(None, description="Filter by account IBANs")
        period_from: Optional[str] = Field(None, description="Start of statement period (MM-YYYY)")
        period_to: Optional[str] = Field(None, description="End of statement period (MM-YYYY)")
        sort_by: str = Field("period:desc", description="Sort field and order")
        limit: Optional[int] = 100

    class GetStatementSchema(BaseModel):
        statement_id: str = Field(..., description="ID of the statement to retrieve")

    return [
        StructuredTool(
            name="get_organization_details",
            description="Get organization and its bank accounts details and balances. Always use this tool to get the bank accounts details.",
            func=lambda: integration.get_organization_details(),
            args_schema=GetOrganizationSchema
        ),
        StructuredTool(
            name="list_transactions",
            description="Get list of transactions for an account.",
            func=lambda **kwargs: integration.list_transactions(**kwargs),
            args_schema=ListTransactionsSchema
        ),
        StructuredTool(
            name="get_transaction",
            description="Retrieve a single transaction by ID.",
            func=lambda **kwargs: integration.get_transaction(**kwargs),
            args_schema=GetTransactionSchema
        ),
        StructuredTool(
            name="get_supplier_invoices",
            description="Retrieve supplier invoices for the organization.",
            func=lambda **kwargs: integration.get_supplier_invoices(**kwargs),
            args_schema=GetSupplierInvoicesSchema
        ),
        StructuredTool(
            name="get_client_invoices",
            description="Retrieve client invoices for the organization.",
            func=lambda **kwargs: integration.get_client_invoices(**kwargs),
            args_schema=GetClientInvoicesSchema
        ),
        StructuredTool(
            name="list_clients",
            description="Get list of clients for the organization.",
            func=lambda **kwargs: integration.list_clients(**kwargs),
            args_schema=ListClientsSchema
        ),
        StructuredTool(
            name="get_client",
            description="Get details of a specific client by ID.",
            func=lambda **kwargs: integration.get_client(**kwargs),
            args_schema=GetClientSchema
        ),
        StructuredTool(
            name="list_cards",
            description="Get list of cards for the organization.",
            func=lambda **kwargs: integration.list_cards(**kwargs),
            args_schema=ListCardsSchema
        ),
        StructuredTool(
            name="get_card_data_view",
            description="Get URL for card data view iframe.",
            func=lambda **kwargs: integration.get_card_data_view(**kwargs),
            args_schema=GetCardDataViewSchema
        ),
        StructuredTool(
            name="list_beneficiaries",
            description="Get list of beneficiaries.",
            func=lambda **kwargs: integration.list_beneficiaries(**kwargs),
            args_schema=ListBeneficiariesSchema
        ),
        StructuredTool(
            name="get_beneficiary",
            description="Get details of a single beneficiary.",
            func=lambda **kwargs: integration.get_beneficiary(**kwargs),
            args_schema=GetBeneficiarySchema
        ),
        StructuredTool(
            name="get_attachment",
            description="Get details of a specific attachment.",
            func=lambda **kwargs: integration.get_attachment(**kwargs),
            args_schema=GetAttachmentSchema
        ),
        StructuredTool(
            name="list_labels",
            description="Get all labels within the organization.",
            func=lambda: integration.list_labels(),
            args_schema=ListLabelsSchema
        ),
        StructuredTool(
            name="get_label",
            description="Get details of a specific label.",
            func=lambda **kwargs: integration.get_label(**kwargs),
            args_schema=GetLabelSchema
        ),
        StructuredTool(
            name="list_memberships",
            description="Get all memberships within the organization.",
            func=lambda: integration.list_memberships(),
            args_schema=ListMembershipsSchema
        ),
        StructuredTool(
            name="get_membership",
            description="Get details of the authenticated membership.",
            func=lambda: integration.get_membership(),
            args_schema=GetMembershipSchema
        ),
        StructuredTool(
            name="list_transaction_attachments",
            description="Get list of attachments for a transaction.",
            func=lambda **kwargs: integration.list_transaction_attachments(**kwargs),
            args_schema=ListTransactionAttachmentsSchema
        ),
        StructuredTool(
            name="list_teams",
            description="Get list of teams within the organization.",
            func=lambda **kwargs: integration.list_teams(**kwargs),
            args_schema=ListTeamsSchema
        ),
        StructuredTool(
            name="list_statements",
            description="Get list of statements for the organization.",
            func=lambda **kwargs: integration.list_statements(**kwargs),
            args_schema=ListStatementsSchema
        ),
        StructuredTool(
            name="get_statement",
            description="Get details of a specific statement by ID.",
            func=lambda **kwargs: integration.get_statement(**kwargs),
            args_schema=GetStatementSchema
        )
    ]