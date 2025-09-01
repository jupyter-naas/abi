"""
Scheduling & Calendar Interface
Multi-use: Project Manager, HR Manager, Sales Rep, Account Executive, Community Manager
Tools: Meeting scheduling, resource booking, deadline tracking, availability management
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import calendar

st.set_page_config(page_title="Scheduling Center", page_icon="📅", layout="wide")

# Configure port for this interface
if __name__ == "__main__":
    import os
    os.environ["STREAMLIT_SERVER_PORT"] = "8504"

# Sidebar controls
st.sidebar.header("🔧 Calendar Controls")
view_type = st.sidebar.selectbox(
    "Calendar View",
    ["Week View", "Month View", "Day View", "Agenda View"]
)

calendar_filter = st.sidebar.multiselect(
    "Calendar Types",
    ["Meetings", "Deadlines", "Events", "Bookings", "Interviews"],
    default=["Meetings", "Deadlines"]
)

user_role = st.sidebar.selectbox(
    "Your Role",
    ["Project Manager", "HR Manager", "Sales Rep", "Account Executive", "Community Manager"]
)

# SOP Section in Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("📖 View SOP", use_container_width=True):
    st.session_state.page = "sop"
    st.rerun()

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = "main"

# Page routing
if st.session_state.page == "sop":
    # SOP Page
    st.title("📖 Standard Operating Procedure")
    
    if st.button("← Back to Dashboard"):
        st.session_state.page = "main"
        st.rerun()
    
    st.markdown("---")
    
    # Read and display the SOP.md file
    try:
        import os
        sop_path = os.path.join(os.path.dirname(__file__), "SOP.md")
        with open(sop_path, 'r', encoding='utf-8') as f:
            sop_content = f.read()
        st.markdown(sop_content)
    except FileNotFoundError:
        st.error("SOP.md file not found. Please ensure the SOP file exists in the same directory as this interface.")
    except Exception as e:
        st.error(f"Error loading SOP: {str(e)}")
    
    st.stop()  # Stop execution here for SOP page

# Main Dashboard Page
st.title("📅 Scheduling & Calendar Interface")
st.markdown("**Multi-Role Scheduling, Meetings & Resource Management**")



# Sample calendar data
@st.cache_data
def load_calendar_data():
    # Generate events for the next 30 days
    base_date = datetime.now()
    events = []
    
    event_types = {
        "Meetings": ["Team Standup", "Client Call", "Project Review", "Strategy Session"],
        "Deadlines": ["Project Delivery", "Report Due", "Proposal Submission", "Review Deadline"],
        "Events": ["Company All-Hands", "Training Session", "Webinar", "Conference"],
        "Bookings": ["Conference Room A", "Equipment Checkout", "Studio Booking", "Vehicle Reservation"],
        "Interviews": ["Technical Interview", "HR Screening", "Final Interview", "Reference Check"]
    }
    
    for i in range(50):
        event_type = np.random.choice(list(event_types.keys()))
        event_title = np.random.choice(event_types[event_type])
        
        event_date = base_date + timedelta(days=np.random.randint(0, 30))
        event_time = np.random.randint(8, 18)  # 8 AM to 6 PM
        duration = np.random.choice([30, 60, 90, 120])  # minutes
        
        events.append({
            'Title': event_title,
            'Type': event_type,
            'Date': event_date,  # Keep as datetime for .dt accessor
            'Start_Time': f"{event_time:02d}:00",
            'Duration': duration,
            'Attendees': np.random.randint(2, 8),
            'Location': np.random.choice(['Conference Room A', 'Conference Room B', 'Zoom', 'Client Office', 'Remote']),
            'Priority': np.random.choice(['Low', 'Medium', 'High', 'Critical']),
            'Status': np.random.choice(['Scheduled', 'Confirmed', 'Tentative', 'Cancelled'])
        })
    
    return pd.DataFrame(events)

events_data = load_calendar_data()

# Filter events based on selection
if calendar_filter:
    filtered_events = events_data[events_data['Type'].isin(calendar_filter)]
else:
    filtered_events = events_data

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

today_events = len(filtered_events[filtered_events['Date'].dt.date == datetime.now().date()])
this_week_events = len(filtered_events[
    (filtered_events['Date'].dt.date >= datetime.now().date()) & 
    (filtered_events['Date'].dt.date <= datetime.now().date() + timedelta(days=7))
])
high_priority = len(filtered_events[filtered_events['Priority'].isin(['High', 'Critical'])])
conflicts = np.random.randint(0, 3)  # Mock conflicts

with col1:
    st.metric("Today's Events", today_events, f"{np.random.randint(-2, 5)}")

with col2:
    st.metric("This Week", this_week_events, f"{np.random.randint(-5, 10)}")

with col3:
    st.metric("High Priority", high_priority, "🚨" if high_priority > 5 else "✅")

with col4:
    st.metric("Schedule Conflicts", conflicts, "⚠️" if conflicts > 0 else "✅")

# Main calendar view
if view_type == "Week View":
    st.subheader("📅 Weekly Schedule")
    
    # Get current week
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # Create week view
    cols = st.columns(7)
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for i, (col, date, day_name) in enumerate(zip(cols, week_dates, day_names)):
        with col:
            st.markdown(f"**{day_name}**")
            st.markdown(f"{date.strftime('%m/%d')}")
            
            # Get events for this day
            day_events = filtered_events[filtered_events['Date'].dt.date == date.date()]
            
            for _, event in day_events.iterrows():
                priority_color = {
                    'Low': 'lightblue',
                    'Medium': 'lightyellow',
                    'High': 'lightorange', 
                    'Critical': 'lightcoral'
                }.get(event['Priority'], 'lightgray')
                
                st.markdown(f"""
                <div style='background-color: {priority_color}; padding: 5px; margin: 2px 0; border-radius: 3px; font-size: 12px;'>
                    <strong>{event['Start_Time']}</strong><br>
                    {event['Title']}<br>
                    <small>{event['Duration']}min | {event['Location']}</small>
                </div>
                """, unsafe_allow_html=True)

elif view_type == "Month View":
    st.subheader("📅 Monthly Overview")
    
    # Monthly calendar visualization
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Events by day of month
    month_events = filtered_events[
        (filtered_events['Date'].dt.month == current_month) &
        (filtered_events['Date'].dt.year == current_year)
    ]
    
    daily_counts = month_events.groupby(month_events['Date'].dt.day).size()
    
    # Create calendar heatmap
    cal = calendar.monthcalendar(current_year, current_month)
    calendar_data = []
    
    for week in cal:
        for day in week:
            if day == 0:
                calendar_data.append({'Day': '', 'Events': 0})
            else:
                event_count = daily_counts.get(day, 0)
                calendar_data.append({'Day': str(day), 'Events': event_count})
    
    # Display as grid
    st.markdown("**Event Density This Month**")
    
    # Create 7 columns for days of week
    cols = st.columns(7)
    headers = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    for i, header in enumerate(headers):
        cols[i].markdown(f"**{header}**")
    
    # Display calendar grid
    for week_idx in range(len(cal)):
        cols = st.columns(7)
        for day_idx in range(7):
            day = cal[week_idx][day_idx]
            if day == 0:
                cols[day_idx].markdown("")
            else:
                event_count = daily_counts.get(day, 0)
                color = 'lightcoral' if event_count > 3 else 'lightyellow' if event_count > 1 else 'lightgreen'
                cols[day_idx].markdown(f"""
                <div style='background-color: {color}; padding: 10px; text-align: center; border-radius: 5px;'>
                    <strong>{day}</strong><br>
                    <small>{event_count} events</small>
                </div>
                """, unsafe_allow_html=True)

elif view_type == "Day View":
    st.subheader("📅 Today's Schedule")
    
    selected_date = st.date_input("Select Date", datetime.now().date())
    day_events = filtered_events[filtered_events['Date'].dt.date == selected_date].sort_values('Start_Time')
    
    if len(day_events) == 0:
        st.info("No events scheduled for this day")
    else:
        # Timeline view
        for _, event in day_events.iterrows():
            priority_color = {
                'Low': 'lightblue',
                'Medium': 'lightyellow',
                'High': 'lightorange',
                'Critical': 'lightcoral'
            }.get(event['Priority'], 'lightgray')
            
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                st.markdown(f"**{event['Start_Time']}**")
                st.markdown(f"{event['Duration']} min")
            
            with col2:
                st.markdown(f"""
                <div style='background-color: {priority_color}; padding: 10px; border-radius: 5px;'>
                    <strong>{event['Title']}</strong><br>
                    Type: {event['Type']} | Priority: {event['Priority']}<br>
                    Location: {event['Location']} | Attendees: {event['Attendees']}
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                status_color = {
                    'Scheduled': 'blue',
                    'Confirmed': 'green',
                    'Tentative': 'orange',
                    'Cancelled': 'red'
                }.get(event['Status'], 'gray')
                st.markdown(f"<span style='color: {status_color}'>{event['Status']}</span>", unsafe_allow_html=True)

elif view_type == "Agenda View":
    st.subheader("📋 Upcoming Agenda")
    
    # Next 7 days agenda
    upcoming_events = filtered_events[
        (filtered_events['Date'].dt.date >= datetime.now().date()) &
        (filtered_events['Date'].dt.date <= datetime.now().date() + timedelta(days=7))
    ].sort_values(['Date', 'Start_Time'])
    
    current_date = None
    for _, event in upcoming_events.iterrows():
        if event['Date'].date() != current_date:
            current_date = event['Date'].date()
            st.markdown(f"### {current_date.strftime('%A, %B %d, %Y')}")
        
        priority_icon = {
            'Low': '🟢',
            'Medium': '🟡', 
            'High': '🟠',
            'Critical': '🔴'
        }.get(event['Priority'], '⚪')
        
        st.markdown(f"""
        **{event['Start_Time']}** {priority_icon} **{event['Title']}**  
        📍 {event['Location']} | 👥 {event['Attendees']} attendees | ⏱️ {event['Duration']} min  
        Status: {event['Status']}
        """)
        st.markdown("---")

# Resource booking section
st.subheader("🏢 Resource Booking")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📍 Room Availability**")
    
    rooms = ['Conference Room A', 'Conference Room B', 'Meeting Room 1', 'Meeting Room 2', 'Board Room']
    room_status: list[dict[str, str | int]] = []
    
    for room in rooms:
        # Mock availability
        is_available = np.random.choice([True, False], p=[0.7, 0.3])
        next_available = "Now" if is_available else f"{np.random.randint(1, 4)}:00 PM"
        
        room_status.append({
            'Room': room,
            'Status': 'Available' if is_available else 'Occupied',
            'Next_Available': next_available,
            'Capacity': np.random.randint(4, 20)
        })
    
    for room_info in room_status:
        status_color = 'green' if room_info['Status'] == 'Available' else 'red'
        st.markdown(f"**{room_info['Room']}** (Cap: {room_info['Capacity']})")
        st.markdown(f"<span style='color: {status_color}'>{room_info['Status']}</span> | Next: {room_info['Next_Available']}", unsafe_allow_html=True)
        st.markdown("---")

with col2:
    st.markdown("**🛠️ Equipment Booking**")
    
    equipment = ['Projector A', 'Projector B', 'Laptop Cart', 'Video Camera', 'Audio System']
    
    for item in equipment:
        is_available = np.random.choice([True, False], p=[0.8, 0.2])
        status_color = 'green' if is_available else 'red'
        status_text = 'Available' if is_available else 'In Use'
        
        st.markdown(f"**{item}**")
        st.markdown(f"<span style='color: {status_color}'>{status_text}</span>", unsafe_allow_html=True)
        st.markdown("---")

# Quick actions
st.subheader("⚡ Quick Actions")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("📅 Schedule Meeting", use_container_width=True):
        st.success("Meeting scheduler opened")

with col2:
    if st.button("🏢 Book Room", use_container_width=True):
        st.info("Room booking interface opened")

with col3:
    if st.button("📧 Send Invites", use_container_width=True):
        st.success("Calendar invites sent")

with col4:
    if st.button("📊 Generate Report", use_container_width=True):
        st.success("Calendar utilization report generated")

# Analytics section
st.subheader("📊 Calendar Analytics")

col1, col2 = st.columns(2)

with col1:
    # Event type distribution
    type_counts = filtered_events['Type'].value_counts()
    fig_types = px.pie(values=type_counts.values, names=type_counts.index,
                      title="Events by Type")
    st.plotly_chart(fig_types, use_container_width=True)

with col2:
    # Weekly meeting load
    weekly_load = filtered_events.groupby(filtered_events['Date'].dt.dayofweek).size()
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    fig_weekly = px.bar(x=day_names, y=weekly_load.values,
                       title="Meeting Load by Day of Week",
                       color=weekly_load.values,
                       color_continuous_scale='Viridis')
    st.plotly_chart(fig_weekly, use_container_width=True)

# Recent scheduling activity
st.subheader("📈 Recent Activity")

activities = [
    {"time": "5 min ago", "user": "Sarah", "action": "Scheduled client call for tomorrow 2 PM"},
    {"time": "15 min ago", "user": "Mike", "action": "Booked Conference Room A for team meeting"},
    {"time": "30 min ago", "user": "Lisa", "action": "Cancelled project review meeting"},
    {"time": "1 hour ago", "user": "John", "action": "Moved interview to next week"},
    {"time": "2 hours ago", "user": "Emma", "action": "Created recurring standup meetings"}
]

for activity in activities:
    st.markdown(f"**{activity['time']}** - {activity['user']}: {activity['action']}")

# Footer
st.markdown("---")
st.markdown(f"**Scheduling Center** | Role: {user_role} | Last Updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
