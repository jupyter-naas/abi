from abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

LOGO_URL = "https://cdn-icons-png.flaticon.com/512/5968/5968499.png"


@dataclass
class GoogleCalendarIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Google Calendar integration.

    Attributes:
        service_account_path (str): Path to service account JSON file
        subject_email (str): Email of the user to impersonate
        scopes (List[str]): List of required API scopes
    """

    service_account_path: str
    subject_email: str
    scopes: List[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarIntegration(Integration):
    """Google Calendar API integration client using service account.

    This integration provides methods to interact with Google Calendar's API endpoints
    for calendar and event operations.
    """

    __configuration: GoogleCalendarIntegrationConfiguration

    def __init__(self, configuration: GoogleCalendarIntegrationConfiguration):
        """Initialize Calendar client with service account credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.__configuration.service_account_path,
                scopes=self.__configuration.scopes,
            )

            # Create delegated credentials for impersonation
            delegated_credentials = credentials.with_subject(
                self.__configuration.subject_email
            )

            # Build the service
            self.__service = build("calendar", "v3", credentials=delegated_credentials)
        except Exception:
            pass
            # logger.debug(f"Failed to initialize Calendar API client: {str(e)}")

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 250,
        order_by: str = "startTime",
        single_events: bool = True,
    ) -> List[Dict]:
        """List calendar events.

        Args:
            calendar_id (str, optional): Calendar ID. Defaults to 'primary'
            time_min (str, optional): Start time (RFC3339 timestamp)
            time_max (str, optional): End time (RFC3339 timestamp)
            max_results (int, optional): Maximum number of events. Defaults to 250
            order_by (str, optional): Order of events. Defaults to 'startTime'
            single_events (bool, optional): Whether to expand recurring events. Defaults to True

        Returns:
            List[Dict]: List of events

        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            events_result = (
                self.__service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    orderBy=order_by,
                    singleEvents=single_events,
                )
                .execute()
            )
            return events_result.get("items", [])
        except HttpError as e:
            raise IntegrationConnectionError(
                f"Google Calendar API request failed: {str(e)}"
            )

    def get_event(self, event_id: str, calendar_id: str = "primary") -> Dict:
        """Get a specific event.

        Args:
            event_id (str): Event ID
            calendar_id (str, optional): Calendar ID. Defaults to 'primary'

        Returns:
            Dict: Event data

        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            return (
                self.__service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
        except HttpError as e:
            raise IntegrationConnectionError(
                f"Google Calendar API request failed: {str(e)}"
            )

    def create_event(
        self,
        summary: str,
        start: Dict[str, str],
        end: Dict[str, str],
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, str]]] = None,
        calendar_id: str = "primary",
    ) -> Dict:
        """Create a new calendar event.

        Args:
            summary (str): Event title
            start (Dict[str, str]): Start time (dateTime or date)
            end (Dict[str, str]): End time (dateTime or date)
            description (str, optional): Event description
            location (str, optional): Event location
            attendees (List[Dict[str, str]], optional): List of attendees
            calendar_id (str, optional): Calendar ID. Defaults to 'primary'

        Returns:
            Dict: Created event data

        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            event = {"summary": summary, "start": start, "end": end}

            if description:
                event["description"] = description
            if location:
                event["location"] = location
            if attendees:
                event["attendees"] = attendees

            return (
                self.__service.events()
                .insert(calendarId=calendar_id, body=event, sendUpdates="all")
                .execute()
            )
        except HttpError as e:
            raise IntegrationConnectionError(
                f"Google Calendar API request failed: {str(e)}"
            )

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start: Optional[Dict[str, str]] = None,
        end: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, str]]] = None,
        calendar_id: str = "primary",
    ) -> Dict:
        """Update an existing calendar event.

        Args:
            event_id (str): Event ID
            summary (str, optional): Event title
            start (Dict[str, str], optional): Start time (dateTime or date)
            end (Dict[str, str], optional): End time (dateTime or date)
            description (str, optional): Event description
            location (str, optional): Event location
            attendees (List[Dict[str, str]], optional): List of attendees
            calendar_id (str, optional): Calendar ID. Defaults to 'primary'

        Returns:
            Dict: Updated event data

        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            # Get existing event
            event = self.get_event(event_id, calendar_id)

            # Update fields if provided
            if summary:
                event["summary"] = summary
            if start:
                event["start"] = start
            if end:
                event["end"] = end
            if description:
                event["description"] = description
            if location:
                event["location"] = location
            if attendees:
                event["attendees"] = attendees

            return (
                self.__service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates="all",
                )
                .execute()
            )
        except HttpError as e:
            raise IntegrationConnectionError(
                f"Google Calendar API request failed: {str(e)}"
            )

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        """Delete a calendar event.

        Args:
            event_id (str): Event ID
            calendar_id (str, optional): Calendar ID. Defaults to 'primary'

        Raises:
            IntegrationConnectionError: If the request fails
        """
        try:
            self.__service.events().delete(
                calendarId=calendar_id, eventId=event_id, sendUpdates="all"
            ).execute()
        except HttpError as e:
            raise IntegrationConnectionError(
                f"Google Calendar API request failed: {str(e)}"
            )


def as_tools(configuration: GoogleCalendarIntegrationConfiguration):
    """Convert Google Calendar integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = GoogleCalendarIntegration(configuration)

    class ListEventsSchema(BaseModel):
        calendar_id: str = Field(default="primary", description="Calendar ID")
        time_min: Optional[str] = Field(
            None, description="Start time (RFC3339 timestamp)"
        )
        time_max: Optional[str] = Field(
            None, description="End time (RFC3339 timestamp)"
        )
        max_results: int = Field(default=250, description="Maximum number of events")
        order_by: str = Field(default="startTime", description="Order of events")
        single_events: bool = Field(
            default=True, description="Whether to expand recurring events"
        )

    class GetEventSchema(BaseModel):
        event_id: str = Field(..., description="Event ID")
        calendar_id: str = Field(default="primary", description="Calendar ID")

    class CreateEventSchema(BaseModel):
        summary: str = Field(..., description="Event title")
        start: Dict[str, str] = Field(..., description="Start time (dateTime or date)")
        end: Dict[str, str] = Field(..., description="End time (dateTime or date)")
        description: Optional[str] = Field(None, description="Event description")
        location: Optional[str] = Field(None, description="Event location")
        attendees: Optional[List[Dict[str, str]]] = Field(
            None, description="List of attendees"
        )
        calendar_id: str = Field(default="primary", description="Calendar ID")

    class UpdateEventSchema(BaseModel):
        event_id: str = Field(..., description="Event ID")
        summary: Optional[str] = Field(None, description="Event title")
        start: Optional[Dict[str, str]] = Field(
            None, description="Start time (dateTime or date)"
        )
        end: Optional[Dict[str, str]] = Field(
            None, description="End time (dateTime or date)"
        )
        description: Optional[str] = Field(None, description="Event description")
        location: Optional[str] = Field(None, description="Event location")
        attendees: Optional[List[Dict[str, str]]] = Field(
            None, description="List of attendees"
        )
        calendar_id: str = Field(default="primary", description="Calendar ID")

    return [
        StructuredTool(
            name="list_calendar_events",
            description="List Google Calendar events",
            func=lambda calendar_id,
            time_min,
            time_max,
            max_results,
            order_by,
            single_events: integration.list_events(
                calendar_id, time_min, time_max, max_results, order_by, single_events
            ),
            args_schema=ListEventsSchema,
        ),
        StructuredTool(
            name="googlecalendar_get_event",
            description="Get a specific Google Calendar event",
            func=lambda event_id, calendar_id: integration.get_event(
                event_id, calendar_id
            ),
            args_schema=GetEventSchema,
        ),
        StructuredTool(
            name="googlecalendar_create_event",
            description="Create a new Google Calendar event",
            func=lambda summary,
            start,
            end,
            description,
            location,
            attendees,
            calendar_id: integration.create_event(
                summary, start, end, description, location, attendees, calendar_id
            ),
            args_schema=CreateEventSchema,
        ),
        StructuredTool(
            name="googlecalendar_update_event",
            description="Update an existing Google Calendar event",
            func=lambda event_id,
            summary,
            start,
            end,
            description,
            location,
            attendees,
            calendar_id: integration.update_event(
                event_id,
                summary,
                start,
                end,
                description,
                location,
                attendees,
                calendar_id,
            ),
            args_schema=UpdateEventSchema,
        ),
        StructuredTool(
            name="googlecalendar_delete_event",
            description="Delete a Google Calendar event",
            func=lambda event_id, calendar_id: integration.delete_event(
                event_id, calendar_id
            ),
            args_schema=GetEventSchema,
        ),
    ]
