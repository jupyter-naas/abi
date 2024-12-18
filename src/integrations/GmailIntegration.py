from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

LOGO_URL = "https://logo.clearbit.com/gmail.com"
@dataclass
class GmailIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Gmail integration.
    
    Attributes:
        credentials (Credentials): Google OAuth2 credentials
        user_id (str): User's email address. Defaults to "me"
    """
    credentials: Credentials
    user_id: str = "me"

class GmailIntegration(Integration):
    """Gmail API integration client.
    
    This integration provides methods to interact with Gmail's API endpoints
    for email operations.
    """

    __configuration: GmailIntegrationConfiguration

    def __init__(self, configuration: GmailIntegrationConfiguration):
        """Initialize Gmail client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__service = build('gmail', 'v1', credentials=self.__configuration.credentials)

    def list_messages(self, 
                     query: Optional[str] = None, 
                     max_results: int = 10) -> List[Dict]:
        """List email messages.
        
        Args:
            query (str, optional): Gmail search query
            max_results (int, optional): Maximum number of results. Defaults to 10.
            
        Returns:
            List[Dict]: List of messages
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            results = self.__service.users().messages().list(
                userId=self.__configuration.user_id,
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = []
            for msg in results.get('messages', []):
                message = self.__service.users().messages().get(
                    userId=self.__configuration.user_id,
                    id=msg['id'],
                    format='full'
                ).execute()
                messages.append(message)
                
            return messages
        except HttpError as e:
            raise IntegrationConnectionError(f"Gmail API request failed: {str(e)}")

    def get_message(self, message_id: str) -> Dict:
        """Get a specific email message.
        
        Args:
            message_id (str): Message ID
            
        Returns:
            Dict: Message data
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            return self.__service.users().messages().get(
                userId=self.__configuration.user_id,
                id=message_id,
                format='full'
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Gmail API request failed: {str(e)}")

    def send_message(self,
                    to: Union[str, List[str]],
                    subject: str,
                    body: str,
                    html: Optional[str] = None,
                    cc: Optional[Union[str, List[str]]] = None,
                    bcc: Optional[Union[str, List[str]]] = None,
                    attachments: Optional[List[Dict]] = None) -> Dict:
        """Send an email message.
        
        Args:
            to (Union[str, List[str]]): Recipient email(s)
            subject (str): Email subject
            body (str): Plain text body
            html (str, optional): HTML body
            cc (Union[str, List[str]], optional): CC recipient(s)
            bcc (Union[str, List[str]], optional): BCC recipient(s)
            attachments (List[Dict], optional): List of attachments with 'filename' and 'content'
            
        Returns:
            Dict: Sent message data
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            message = MIMEMultipart('alternative')
            message['To'] = isinstance(to, list) and ', '.join(to) or to
            message['Subject'] = subject
            
            if cc:
                message['Cc'] = isinstance(cc, list) and ', '.join(cc) or cc
            if bcc:
                message['Bcc'] = isinstance(bcc, list) and ', '.join(bcc) or bcc
                
            message.attach(MIMEText(body, 'plain'))
            if html:
                message.attach(MIMEText(html, 'html'))
                
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    message.attach(part)
                    
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            return self.__service.users().messages().send(
                userId=self.__configuration.user_id,
                body={'raw': raw_message}
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Gmail API request failed: {str(e)}")

    def create_draft(self,
                    to: Union[str, List[str]],
                    subject: str,
                    body: str,
                    html: Optional[str] = None,
                    cc: Optional[Union[str, List[str]]] = None,
                    bcc: Optional[Union[str, List[str]]] = None,
                    attachments: Optional[List[Dict]] = None) -> Dict:
        """Create an email draft.
        
        Args:
            to (Union[str, List[str]]): Recipient email(s)
            subject (str): Email subject
            body (str): Plain text body
            html (str, optional): HTML body
            cc (Union[str, List[str]], optional): CC recipient(s)
            bcc (Union[str, List[str]], optional): BCC recipient(s)
            attachments (List[Dict], optional): List of attachments with 'filename' and 'content'
            
        Returns:
            Dict: Created draft data
            
        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            message = MIMEMultipart('alternative')
            message['To'] = isinstance(to, list) and ', '.join(to) or to
            message['Subject'] = subject
            
            if cc:
                message['Cc'] = isinstance(cc, list) and ', '.join(cc) or cc
            if bcc:
                message['Bcc'] = isinstance(bcc, list) and ', '.join(bcc) or bcc
                
            message.attach(MIMEText(body, 'plain'))
            if html:
                message.attach(MIMEText(html, 'html'))
                
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    message.attach(part)
                    
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            return self.__service.users().drafts().create(
                userId=self.__configuration.user_id,
                body={'message': {'raw': raw_message}}
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(f"Gmail API request failed: {str(e)}")

def as_tools(configuration: GmailIntegrationConfiguration):
    """Convert Gmail integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = GmailIntegration(configuration)
    
    class ListMessagesSchema(BaseModel):
        query: Optional[str] = Field(None, description="Gmail search query")
        max_results: int = Field(default=10, description="Maximum number of results")

    class GetMessageSchema(BaseModel):
        message_id: str = Field(..., description="Message ID")

    class SendMessageSchema(BaseModel):
        to: Union[str, List[str]] = Field(..., description="Recipient email(s)")
        subject: str = Field(..., description="Email subject")
        body: str = Field(..., description="Plain text body")
        html: Optional[str] = Field(None, description="HTML body")
        cc: Optional[Union[str, List[str]]] = Field(None, description="CC recipient(s)")
        bcc: Optional[Union[str, List[str]]] = Field(None, description="BCC recipient(s)")
        attachments: Optional[List[Dict]] = Field(None, description="List of attachments")
    
    return [
        StructuredTool(
            name="list_gmail_messages",
            description="List email messages with optional search query",
            func=lambda query, max_results: integration.list_messages(query, max_results),
            args_schema=ListMessagesSchema
        ),
        StructuredTool(
            name="get_gmail_message",
            description="Get a specific email message",
            func=lambda message_id: integration.get_message(message_id),
            args_schema=GetMessageSchema
        ),
        StructuredTool(
            name="send_gmail_message",
            description="Send an email message",
            func=lambda to, subject, body, html, cc, bcc, attachments: integration.send_message(
                to, subject, body, html, cc, bcc, attachments
            ),
            args_schema=SendMessageSchema
        ),
        StructuredTool(
            name="create_gmail_draft",
            description="Create an email draft",
            func=lambda to, subject, body, html, cc, bcc, attachments: integration.create_draft(
                to, subject, body, html, cc, bcc, attachments
            ),
            args_schema=SendMessageSchema
        )
    ] 