import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Israel Bus Tracker", layout="wide")
STRIDE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Israel Live Bus Tracker")

# 1. GET LOCATION
loc = get_geolocation()
if not loc:
    st.warning("📍 Waiting for GPS... (Make sure location is enabled in your browser)")
    u_lat, u_lon = 32.1782, 34.9076 # Default to Kefar Sava center
else:
    u_lat, u_lon = loc['coords']['latitude'], loc['coords']['longitude']

# 2. SIDEBAR CONTROLS
with st.sidebar:
    st.header("Search Settings")
    bus_num = st.text_input("Bus Number (e.g. 149, 189, 2)", value="149")
    minutes_back = st.slider("Look back (minutes)", 1, 30, 10)
    st.info("Buses are shown if they reported their location in the last X minutes.")

# 3. DATA FETCHING
def fetch_live_buses(line_number, minutes):
    # Calculate UTC time (Stride uses UTC)
    since_time = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    
    # We query the vehicle locations directly filtering by the line number
    params = {
        "recorded_at_time__gte": since_time,
        "siri_ride__siri_route__gtfs_route__route_short_name": line_number,
        "limit": 100
    }
    
    try:
        response = requests.get(f"{STRIDE_URL}/siri_vehicle_locations/list", params=params, timeout=10)
        return response.json() if response.status_code == 200 else []
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

# 4. MAP & DISPLAY
if bus_num:
    with st.spinner(f"Searching for Line {bus_num}..."):
        buses = fetch_live_buses(bus_num, minutes_back)
        
        # UI Columns
        col1, col2 = st.columns([3, 1])
        
        with col1:
            m = folium.Map(location=[u_lat, u_lon], zoom_start=13)
            
            # Your Marker
            folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
            
            # Plot Buses
            if buses:
                for b in buses:
                    folium.Marker(
                        [b['lat'], b['lon']],
                        popup=f"Line {bus_num} (ID: {b['id']})",
                        icon=folium.Icon(color='green', icon='bus', prefix='fa')
                    ).add_to(m)
                st.success(f"Found {len(buses)} active reports for line {bus_num}!")
            else:
                st.error(f"No active buses found for line {bus_num} in the last {minutes_back} mins.")
            
            st_folium(m, width=800, height=500, key="israel_map")

        with col2:
            st.subheader("Data Inspector")
            if buses:
                # Show the most recent reporting bus
                latest = buses[0]
                st.write(f"**Last Update:** {latest['recorded_at_time']}")
                st.write(f"**Lat:** {latest['lat']}")
                st.write(f"**Lon:** {latest['lon']}")
            else:
                st.write("No data to inspect.")

# --- DEBUG EXPANDER ---
with st.expander("🛠️ Debug Raw API Response"):
    if bus_num:
        st.json(fetch_live_buses(bus_num, minutes_back))
