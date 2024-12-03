import streamlit as st

# In the main() function, update the logo section:

# Header with logo and dropdowns
col1, col2, col3 = st.columns([1, 2, 2])

with col1:
    st.image("https://avatars.githubusercontent.com/u/71603764?s=400&u=a06d20058028b89181e084f2e5f750d3ea271925&v=4", 
             width=50)

with col2:
    st.selectbox(
        "Entity",
        ["Process:NaasPlatefromTesting", "Other Entities..."],
        index=0
    )

with col3:
    st.selectbox(
        "Scenario",
        ["2024-11-11", "Other dates..."],
        index=0
    )
