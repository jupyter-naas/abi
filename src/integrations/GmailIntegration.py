from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import email
import base64

LOGO_URL = "https://static.dezeen.com/uploads/2020/10/gmail-google-logo-rebrand-workspace-design_dezeen_2364_sq.jpg"
GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_IMAP_SERVER = "imap.gmail.com"

@dataclass
class GmailIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Gmail integration.
    
    Attributes:
        email (str): Gmail email address
        app_password (str): Gmail app password
    """
    email: str
    app_password: str

class GmailIntegration(Integration):
    """Gmail IMAP/SMTP integration client.
    
    This integration provides methods to interact with Gmail using IMAP for reading
    and SMTP for sending emails.
    """

    __configuration: GmailIntegrationConfiguration

    def __init__(self, configuration: GmailIntegrationConfiguration):
        """Initialize Gmail client with app password."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.__imap = None
        self.__smtp = None

    def __connect_imap(self):
        """Establish IMAP connection."""
        if not self.__imap:
            try:
                self.__imap = imaplib.IMAP4_SSL(GMAIL_IMAP_SERVER)
                self.__imap.login(self.__configuration.email, self.__configuration.app_password)
            except Exception as e:
                raise IntegrationConnectionError(f"IMAP connection failed: {str(e)}")

    def __connect_smtp(self):
        """Establish SMTP connection."""
        if not self.__smtp:
            try:
                self.__smtp = smtplib.SMTP(GMAIL_SMTP_SERVER, 587)
                self.__smtp.starttls()
                self.__smtp.login(self.__configuration.email, self.__configuration.app_password)
            except Exception as e:
                raise IntegrationConnectionError(f"SMTP connection failed: {str(e)}")

    def list_messages(self, 
                     query: Optional[str] = None, 
                     max_results: int = 10) -> List[Dict]:
        """List email messages using IMAP.
        
        Args:
            query (str, optional): Gmail search query
            max_results (int, optional): Maximum number of results. Defaults to 10.
            
        Returns:
            List[Dict]: List of messages
        """
        try:
            self.__connect_imap()
            self.__imap.select('INBOX')
            
            search_criteria = 'ALL' if not query else f'SUBJECT "{query}"'
            _, message_numbers = self.__imap.search(None, search_criteria)
            
            messages = []
            for num in message_numbers[0].split()[-max_results:]:
                _, msg_data = self.__imap.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                message = email.message_from_bytes(email_body)
                
                messages.append({
                    'id': num.decode(),
                    'payload': {
                        'headers': [
                            {'name': k, 'value': v} 
                            for k, v in message.items()
                        ],
                        'body': {
                            'data': message.get_payload()
                        }
                    }
                })
            
            return messages
        except Exception as e:
            raise IntegrationConnectionError(f"IMAP operation failed: {str(e)}")

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
            self.__connect_imap()
            self.__imap.select('INBOX')
            
            _, msg_data = self.__imap.fetch(message_id, '(RFC822)')
            email_body = msg_data[0][1]
            message = email.message_from_bytes(email_body)
            
            return {
                'id': message_id,
                'payload': {
                    'headers': [
                        {'name': k, 'value': v} 
                        for k, v in message.items()
                    ],
                    'body': {
                        'data': message.get_payload()
                    }
                }
            }
        except Exception as e:
            raise IntegrationConnectionError(f"IMAP operation failed: {str(e)}")

    def send_message(self,
                    to: Union[str, List[str]],
                    subject: str,
                    body: str,
                    html: Optional[str] = None,
                    cc: Optional[Union[str, List[str]]] = None,
                    bcc: Optional[Union[str, List[str]]] = None,
                    attachments: Optional[List[Dict]] = None) -> Dict:
        """Send an email message using SMTP."""
        try:
            self.__connect_smtp()
            
            message = MIMEMultipart('alternative')
            message['From'] = self.__configuration.email
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
                    
            self.__smtp.send_message(message)
            return {'status': 'sent'}
        except Exception as e:
            raise IntegrationConnectionError(f"SMTP operation failed: {str(e)}")

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
            self.__connect_imap()
            
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
            
            self.__imap.append('INBOX', '', '', raw_message)
            return {'status': 'draft created'}
        except Exception as e:
            raise IntegrationConnectionError(f"IMAP operation failed: {str(e)}")

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