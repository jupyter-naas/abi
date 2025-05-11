from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from imapclient import IMAPClient
import email
import smtplib

LOGO_URL = "https://static.dezeen.com/uploads/2020/10/gmail-google-logo-rebrand-workspace-design_dezeen_2364_sq.jpg"


@dataclass
class GmailIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Gmail integration.

    Attributes:
        username (str): Gmail email address
        app_password (str): Gmail app password
        smtp_type (str): SMTP type (SSL or STARTTLS)
        smtp_server (str): SMTP server
        smtp_port (int): SMTP port
    """

    username: str
    app_password: str
    smtp_type: str = "SSL"
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 465


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

    def login(self):
        server = IMAPClient("imap.gmail.com")
        server.login(self.__configuration.username, self.__configuration.app_password)
        self.__server = server
        return self

    def list_folders(self, directory: str = "", pattern: str = "*") -> List[Dict]:
        """List folders in Gmail account.

        Args:
            directory (str, optional): Base directory to list folders from. Defaults to ''.
            pattern (str, optional): Pattern to filter folder names. Defaults to '*'.
                Supports wildcards:
                * - matches zero or more of any character
                % - matches 0 or more characters except folder delimiter

        Returns:
            List[Dict]: List of folder information dictionaries containing:
                - flags: List of folder flags
                - delimiter: Folder hierarchy delimiter
                - name: Folder name

        Raises:
            IntegrationConnectionError: If connection to Gmail fails
        """
        try:
            self.login()
            folders = self.__server.list_folders(directory, pattern)
            return [
                {
                    "flags": [f.decode() for f in flags],
                    "delimiter": delimiter.decode(),
                    "name": name.decode(),
                }
                for flags, delimiter, name in folders
            ]
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to list folders: {str(e)}")

    def list_subscribed_folders(
        self, directory: str = "", pattern: str = "*"
    ) -> List[Dict]:
        """List subscribed folders in Gmail account.

        Args:
            directory (str, optional): Base directory to list folders from. Defaults to ''.
            pattern (str, optional): Pattern to filter folder names. Defaults to '*'.
                Supports wildcards:
                * - matches zero or more of any character
                % - matches 0 or more characters except folder delimiter

        Returns:
            List[Dict]: List of folder information dictionaries containing:
                - flags: List of folder flags
                - delimiter: Folder hierarchy delimiter
                - name: Folder name

        Raises:
            IntegrationConnectionError: If connection to Gmail fails
        """
        try:
            self.login()
            folders = self.__server.list_sub_folders(directory, pattern)
            return [
                {
                    "flags": [f.decode() for f in flags],
                    "delimiter": delimiter.decode(),
                    "name": name.decode(),
                }
                for flags, delimiter, name in folders
            ]
        except Exception as e:
            raise IntegrationConnectionError(
                f"Failed to list subscribed folders: {str(e)}"
            )

    def move_messages(self, messages: List[int], folder: str) -> bool:
        """Move messages to another folder.

        Args:
            messages (List[int]): List of message UIDs to move
            folder (str): Destination folder name

        Returns:
            bool: True if messages were moved successfully

        Raises:
            IntegrationConnectionError: If connection to Gmail fails or if MOVE capability is not supported
        """
        try:
            self.login()
            self.__server.move(messages, folder)
            return True

        except Exception as e:
            raise IntegrationConnectionError(f"Failed to move messages: {str(e)}")

    def get_inbox_details(self):
        try:
            self.login()
            return self.__server.select_folder("INBOX")
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get inbox details: {str(e)}")

    def get_inbox_count(self) -> int:
        """Get the total number of messages in the inbox."""
        return self.get_inbox_details()[b"EXISTS"]

    def get_inbox_flags(self) -> List[str]:
        """Get the flags of the inbox."""
        return self.get_inbox_details()[b"FLAGS"]

    def get_inbox_permanent_flags(self) -> List[str]:
        """Get the permanent flags of the inbox."""
        return self.get_inbox_details()[b"PERMANENTFLAGS"]

    def get_inbox_recent(self) -> int:
        """Get the number of recent messages in the inbox."""
        return self.get_inbox_details()[b"RECENT"]

    def get_messages(self, criteria: List[str] = ["ALL"]) -> List[Dict]:
        """Get messages in the inbox.

        Args:
            criteria (List[str]): Gmail search criteria

        Returns:
            List[Dict]: List of messages
        """
        self.login()
        self.__server.select_folder("INBOX")
        messages_ids = self.__server.search(criteria)
        messages = self.__server.fetch(
            messages_ids, ["RFC822.SIZE", "FLAGS", "INTERNALDATE", "ENVELOPE"]
        )

        parsed_messages = []
        for msg_id, msg_data in messages.items():
            envelope = msg_data[b"ENVELOPE"]

            # Helper function to parse email addresses
            def parse_addresses(addresses):
                if not addresses:
                    return []
                return [
                    {
                        "name": addr.name.decode() if addr.name else None,
                        "email": f"{addr.mailbox.decode() if addr.mailbox else ''}@{addr.host.decode() if addr.host else ''}",
                    }
                    for addr in addresses
                ]

            parsed_msg = {
                "id": msg_id,
                "size": msg_data[b"RFC822.SIZE"],
                "date": msg_data[b"INTERNALDATE"].isoformat(),
                "flags": [f.decode() for f in msg_data[b"FLAGS"]],
                "subject": envelope.subject.decode() if envelope.subject else None,
                "from": parse_addresses(envelope.from_)[0] if envelope.from_ else None,
                # 'sender': parse_addresses(envelope.sender)[0] if envelope.sender else None,
                "reply_to": parse_addresses(envelope.reply_to),
                "to": parse_addresses(envelope.to),
                "cc": parse_addresses(envelope.cc),
                "bcc": parse_addresses(envelope.bcc),
                "in_reply_to": envelope.in_reply_to.decode()
                if envelope.in_reply_to
                else None,
                "message_id": envelope.message_id.decode()
                if envelope.message_id
                else None,
            }
            parsed_messages.append(parsed_msg)
        return parsed_messages

    def get_all_messages(self) -> List[Dict]:
        """List all messages in the inbox."""
        return self.get_messages(["ALL"])

    def get_unseen_messages(self) -> List[Dict]:
        """List all unseen messages in the inbox."""
        return self.get_messages(["UNSEEN"])

    def get_seen_messages(self) -> List[Dict]:
        """List all seen messages in the inbox."""
        return self.get_messages(["SEEN"])

    def get_inbox_messages_by_date(self, date: str) -> List[Dict]:
        """Get all messages in the inbox by date.

        Args:
            date (date): Date to search for messages

        Returns:
            List[Dict]: List of messages
        """
        return self.get_messages(["SINCE", date])

    def get_inbox_messages_by_sender(
        self, email: str, criteria: str = "ALL", date: str = None
    ) -> List[Dict]:
        """Get all messages in the inbox from a specific sender.

        Args:
            email (str): Email address of the sender to search for
            criteria (str, optional): Gmail search criteria (e.g. 'ALL', 'UNSEEN', 'SEEN')
            date (str, optional): Date to search for messages (format: %d-%b-%Y)
        Returns:
            List[Dict]: List of messages from the specified sender
        """
        if date:
            return self.get_messages([criteria, "FROM", email, "SINCE", date])
        else:
            return self.get_messages([criteria, "FROM", email])

    def get_email_content(self, message_id: int) -> Dict:
        """Get the full content of a specific email message.

        Args:
            message_id (int): ID of the message to retrieve

        Returns:
            Dict: Message content including body text, HTML, and attachments

        Raises:
            IntegrationConnectionError: If connection to Gmail fails
        """
        try:
            self.login()
            self.__server.select_folder("INBOX")

            # Fetch the full message data
            message_data = self.__server.fetch([int(message_id)], ["RFC822"])[
                int(message_id)
            ][b"RFC822"]
            email_message = email.message_from_bytes(message_data)

            content = {
                "subject": email_message["subject"],
                "from": email_message["from"],
                "to": email_message["to"],
                "date": email_message["date"],
                "body_text": "",
                "attachments": [],
            }

            # Process each part of the message
            for part in email_message.walk():
                if part.get_content_maintype() == "multipart":
                    continue

                if part.get_content_maintype() == "text":
                    if part.get_content_subtype() == "plain":
                        content["body_text"] = part.get_payload(decode=True).decode()
                else:
                    # Handle attachments
                    if part.get_filename():
                        attachment = {
                            "filename": part.get_filename(),
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True)),
                            "payload": part.get_payload(decode=True),
                        }
                        content["attachments"].append(attachment)

            return content

        except Exception as e:
            raise IntegrationConnectionError(f"Failed to get message content: {str(e)}")

    def create_draft(
        self,
        email_to: str,
        subject: str,
        content: str = "",
        files: Dict[str, Any] = None,
    ) -> None:
        """Create a draft email in Gmail.

        Args:
            email_to (str): Email address of the recipient
            subject (str): Subject line of the email
            content (str, optional): Body text of the email
            files (Dict[str, Any], optional): Dictionary of attachments where key is filename and value is file path
        """
        try:
            # Create the email message
            contents = email.mime.multipart.MIMEMultipart()
            contents.attach(email.mime.text.MIMEText(content, "plain"))

            contents["Subject"] = email.header.Header(subject, "UTF-8")
            contents["From"] = self.__configuration.username
            contents["To"] = email_to

            # Add attachments if any
            if files:
                for filename, filepath in files.items():
                    part = email.mime.base.MIMEBase("application", "octet-stream")
                    with open(filepath, "rb") as f:
                        part.set_payload(f.read())
                    email.encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", f"attachment; filename= {filename}"
                    )
                    contents.attach(part)

            # Save as draft
            if self.__configuration.smtp_type == "SSL":
                server = smtplib.SMTP_SSL(
                    self.__configuration.smtp_server, self.__configuration.smtp_port
                )
            elif self.__configuration.smtp_type == "STARTTLS":
                server = smtplib.SMTP(
                    self.__configuration.smtp_server, self.__configuration.smtp_port
                )
                server.starttls()
            else:
                raise ValueError("Please set smtp_type to SSL or STARTTLS")

            server.login(
                self.__configuration.username, self.__configuration.app_password
            )

            # Convert the message to string format
            draft = contents.as_string()

            # Save the draft
            self.login()
            self.__server.append("[Gmail]/Drafts", draft.encode(), ["\\Draft"])

        except Exception as e:
            raise IntegrationConnectionError(f"Failed to create draft: {str(e)}")

    def send_email(
        self,
        email_to: str,
        subject: str,
        content: str = "",
        files: Dict[str, Any] = None,
    ) -> None:
        """Send an email using Gmail.

        Args:
            email_to (str): Email address of the recipient
            subject (str): Subject line of the email
            content (str, optional): Body text of the email
            files (Dict[str, Any], optional): Dictionary of attachments where key is filename and value is file path

        Returns:
            None

        Raises:
            IntegrationConnectionError: If connection to Gmail fails
        """
        try:
            self.login()

            # Create the email message
            contents = email.mime.multipart.MIMEMultipart()
            contents.attach(email.mime.text.MIMEText(content, "plain"))

            contents["Subject"] = email.header.Header(subject, "UTF-8")
            contents["From"] = self.__configuration.username
            contents["To"] = email_to

            # Add attachments if any
            if files:
                for filename, filepath in files.items():
                    part = email.mime.base.MIMEBase("application", "octet-stream")
                    with open(filepath, "rb") as f:
                        part.set_payload(f.read())
                    email.encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", f"attachment; filename= {filename}"
                    )
                    contents.attach(part)

            # Send the email
            if self.__configuration.smtp_type == "SSL":
                server = smtplib.SMTP_SSL(
                    self.__configuration.smtp_server, self.__configuration.smtp_port
                )
            elif self.__configuration.smtp_type == "STARTTLS":
                server = smtplib.SMTP(
                    self.__configuration.smtp_server, self.__configuration.smtp_port
                )
                server.starttls()
            else:
                raise ValueError("Please set smtp_type to SSL or STARTTLS")

            server.login(
                self.__configuration.username, self.__configuration.app_password
            )
            try:
                server.sendmail(
                    self.__configuration.username, email_to, contents.as_string()
                )
            finally:
                server.quit()

        except Exception as e:
            raise IntegrationConnectionError(f"Failed to send email: {str(e)}")


def as_tools(configuration: GmailIntegrationConfiguration):
    """Convert Gmail integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GmailIntegration(configuration)

    class ListFoldersSchema(BaseModel):
        directory: str = Field(..., description="Base directory to list folders from")
        pattern: str = Field(..., description="Pattern to filter folder names")

    class ListSubscribedFoldersSchema(BaseModel):
        directory: str = Field(..., description="Base directory to list folders from")
        pattern: str = Field(..., description="Pattern to filter folder names")

    class MoveMessagesSchema(BaseModel):
        messages: List[int] = Field(..., description="List of message UIDs to move")
        folder: str = Field(..., description="Destination folder name")

    class GetInboxDetailsSchema(BaseModel):
        pass

    class GetInboxMessageSchema(BaseModel):
        pass

    class GetInboxMessagesByDateSchema(BaseModel):
        date: str = Field(
            ..., description="Date to search for messages (format: %d-%b-%Y)"
        )

    class GetInboxMessagesBySenderSchema(BaseModel):
        email: str = Field(..., description="Email address of the sender to search for")
        criteria: str = Field(
            ..., description="Gmail search criteria must be 'ALL', 'UNSEEN', 'SEEN'"
        )
        date: str = Field(
            ...,
            description="Date to search for messages must be transformed to format: %d-%b-%Y)",
        )

    class GetMessageContentSchema(BaseModel):
        message_id: str = Field(..., description="ID of the message to retrieve")

    class CreateDraftSchema(BaseModel):
        email_to: str = Field(..., description="Email address of the recipient")
        subject: str = Field(..., description="Subject line of the email")
        content: str = Field(..., description="Body text of the email")
        files: Optional[Dict[str, Any]] = Field(
            ...,
            description="Dictionary of attachments where key is filename and value is file path",
        )

    class SendEmailSchema(BaseModel):
        email_to: str = Field(..., description="Email address of the recipient")
        subject: str = Field(..., description="Subject line of the email")
        content: str = Field(..., description="Body text of the email")
        files: Optional[Dict[str, Any]] = Field(
            ...,
            description="Dictionary of attachments where key is filename and value is file path",
        )

    return [
        StructuredTool(
            name="gmail_list_folders",
            description="List folders in Gmail account",
            func=lambda directory, pattern: integration.list_folders(
                directory, pattern
            ),
            args_schema=ListFoldersSchema,
        ),
        StructuredTool(
            name="gmail_list_subscribed_folders",
            description="List subscribed folders in Gmail account",
            func=lambda directory, pattern: integration.list_subscribed_folders(
                directory, pattern
            ),
            args_schema=ListSubscribedFoldersSchema,
        ),
        StructuredTool(
            name="gmail_move_messages",
            description="Move messages to another folder",
            func=lambda messages, folder: integration.move_messages(messages, folder),
            args_schema=MoveMessagesSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_details",
            description="Get the total number of messages in the inbox",
            func=lambda: integration.get_inbox_details(),
            args_schema=GetInboxDetailsSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_count",
            description="Get the total number of messages in the inbox",
            func=lambda: integration.get_inbox_count(),
            args_schema=GetInboxDetailsSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_flags",
            description="Get the flags of the inbox",
            func=lambda: integration.get_inbox_flags(),
            args_schema=GetInboxDetailsSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_permanent_flags",
            description="Get the permanent flags of the inbox",
            func=lambda: integration.get_inbox_permanent_flags(),
            args_schema=GetInboxDetailsSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_recent",
            description="Get the number of recent messages in the inbox",
            func=lambda: integration.get_inbox_recent(),
            args_schema=GetInboxDetailsSchema,
        ),
        StructuredTool(
            name="gmail_get_all_messages",
            description="Get all email messages in the inbox",
            func=lambda: integration.get_all_messages(),
            args_schema=GetInboxMessageSchema,
        ),
        StructuredTool(
            name="gmail_get_unseen_messages",
            description="Get all unseen/unread email messages in the inbox",
            func=lambda: integration.get_unseen_messages(),
            args_schema=GetInboxMessageSchema,
        ),
        StructuredTool(
            name="gmail_get_seen_messages",
            description="Get all seen/read email messages in the inbox",
            func=lambda: integration.get_seen_messages(),
            args_schema=GetInboxMessageSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_messages_by_date",
            description="Get email messages in the inbox by date",
            func=lambda date: integration.get_inbox_messages_by_date(date),
            args_schema=GetInboxMessagesByDateSchema,
        ),
        StructuredTool(
            name="gmail_get_inbox_messages_by_sender",
            description="Get email messages in the inbox by sender",
            func=lambda email, criteria, date: integration.get_inbox_messages_by_sender(
                email, criteria, date
            ),
            args_schema=GetInboxMessagesBySenderSchema,
        ),
        StructuredTool(
            name="gmail_get_email_content",
            description="Get the content of a specific email message",
            func=lambda message_id: integration.get_email_content(message_id),
            args_schema=GetMessageContentSchema,
        ),
        StructuredTool(
            name="gmail_create_draft",
            description="Create a draft email in Gmail",
            func=lambda email_to, subject, content, files: integration.create_draft(
                email_to, subject, content, files
            ),
            args_schema=CreateDraftSchema,
        ),
        StructuredTool(
            name="gmail_send_email",
            description="Send an email using Gmail",
            func=lambda email_to, subject, content, files: integration.send_email(
                email_to, subject, content, files
            ),
            args_schema=SendEmailSchema,
        ),
    ]
