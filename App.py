import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime

# --- CONFIGURATION ---
STRIDE_BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.set_page_config(page_title="Israel Live Bus Tracker", layout="wide")

st.title("🚌 Israel Live Bus Tracker")
st.markdown("Real-time data via MOT & Hasadna Stride API")

# --- 1. GET USER LOCATION ---
# Using streamlit-js-eval to get browser GPS
location = get_geolocation()

if not location:
    st.info("Please allow location access to find the nearest station. Defaulting to Central Israel.")
    user_lat, user_lon = 32.0853, 34.7818 # Default Tel Aviv
else:
    user_lat = location['coords']['latitude']
    user_lon = location['coords']['longitude']

# --- 2. BUS SELECTION ---
bus_line = st.sidebar.text_input("Enter Bus Line Number (e.g., 189, 1, 42)", value="189")

# --- DATA FETCHING FUNCTIONS ---
@st.cache_data(ttl=60) # Cache for 1 minute
def get_route_ids(line_number):
    """Maps a line number (short_name) to internal Route IDs."""
    params = {"route_short_name": line_number, "limit": 10}
    res = requests.get(f"{STRIDE_BASE_URL}/gtfs_routes/list", params=params)
    return [r['id'] for r in res.json()] if res.status_code == 200 else []

def get_live_buses(route_ids):
    """Fetches real-time vehicle positions for specific route IDs."""
    # We join route IDs into a comma-separated string
    route_ids_str = ",".join(map(str, route_ids))
    params = {"siri_route__gtfs_route_id__in": route_ids_str, "limit": 50}
    res = requests.get(f"{STRIDE_BASE_URL}/siri_vehicle_locations/list", params=params)
    return res.json() if res.status_code == 200 else []

def get_closest_stop_eta(user_lat, user_lon, route_ids):
    """Finds the nearest stop for this line and gets ETAs."""
    # For a production app, you'd use a KDTree here. 
    # For this script, we'll query the Stride API for stop estimations near the user.
    params = {
        "lat": user_lat,
        "lon": user_lon,
        "distance_m": 1000, # Search within 1km
        "limit": 5
    }
    # Simplified logic: fetch estimations and filter by our routes
    res = requests.get(f"{STRIDE_BASE_URL}/siri_stop_estimations/list", params=params)
    if res.status_code == 200:
        return res.json()
    return []

# --- 3. MAIN LOGIC ---
if bus_line:
    with st.spinner(f"Tracking Line {bus_line}..."):
        # A. Find the internal Route IDs for the line number
        routes = get_route_ids(bus_line)
        
        if not routes:
            st.error(f"Could not find Route IDs for line {bus_line}.")
        else:
            # B. Get Live Positions
            buses = get_live_buses(routes)
            
            # C. Create Map
            m = folium.Map(location=[user_lat, user_lon], zoom_start=14)
            
            # User Marker
            folium.Marker(
                [user_lat, user_lon], 
                popup="You", 
                icon=folium.Icon(color="blue", icon="user", prefix='fa')
            ).addTo(m)
            
            # Bus Markers
            for bus in buses:
                if bus.get('lat') and bus.get('lon'):
                    folium.Marker(
                        [bus['lat'], bus['lon']],
                        popup=f"Line {bus_line} to {bus.get('recorded_at_time')}",
                        icon=folium.Icon(color="green", icon="bus", prefix='fa')
                    ).addTo(m)
            
            # D. Display Map and Data
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st_folium(m, width=700, height=500)
            
            with col2:
                st.subheader("Upcoming Arrivals")
                etas = get_closest_stop_eta(user_lat, user_lon, routes)
                if etas:
                    for eta in etas:
                        # Check if this ETA belongs to our selected line
                        arrival = eta.get('estimated_arrival_time')
                        if arrival:
                            time_obj = datetime.fromisoformat(arrival.replace('Z', '+00:00'))
                            st.write(f"⏱ **{time_obj.strftime('%H:%M')}**")
                else:
                    st.write("No arrivals found in the next 30 mins.")

st.sidebar.button("🔄 Refresh Data")
