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
# Fetches browser GPS coordinates
location = get_geolocation()

if not location:
    st.info("Waiting for GPS... Please allow location access. (Defaulting to Tel Aviv)")
    user_lat, user_lon = 32.0853, 34.7818 
else:
    user_lat = location['coords']['latitude']
    user_lon = location['coords']['longitude']

# --- 2. BUS SELECTION ---
bus_line = st.sidebar.text_input("Enter Bus Line Number (e.g., 189, 1, 42)", value="189")

# --- DATA FETCHING FUNCTIONS ---
@st.cache_data(ttl=300) 
def get_route_ids(line_number):
    """Maps a line number to internal GTFS Route IDs."""
    params = {"route_short_name": line_number, "limit": 20}
    res = requests.get(f"{STRIDE_BASE_URL}/gtfs_routes/list", params=params)
    if res.status_code == 200:
        return [r['id'] for r in res.json()]
    return []

def get_live_buses(route_ids):
    """Fetches real-time vehicle positions for specific route IDs."""
    route_ids_str = ",".join(map(str, route_ids))
    params = {"siri_route__gtfs_route_id__in": route_ids_str, "limit": 50}
    res = requests.get(f"{STRIDE_BASE_URL}/siri_vehicle_locations/list", params=params)
    return res.json() if res.status_code == 200 else []

def get_nearby_arrivals(user_lat, user_lon, route_ids):
    """Finds nearby stops and returns current arrival estimations."""
    # Find stops within 800m of user
    stop_params = {"lat": user_lat, "lon": user_lon, "distance_m": 800}
    stop_res = requests.get(f"{STRIDE_BASE_URL}/gtfs_stops/list", params=stop_params)
    
    if stop_res.status_code == 200:
        stop_codes = [s['code'] for s in stop_res.json() if s.get('code')]
        if stop_codes:
            # Query estimations for these stops
            est_params = {"monitoring_ref__in": ",".join(map(str, stop_codes)), "limit": 30}
            est_res = requests.get(f"{STRIDE_BASE_URL}/siri_stop_estimations/list", params=est_params)
            return est_res.json() if est_res.status_code == 200 else []
    return []

# --- 3. MAIN LOGIC ---
if bus_line:
    with st.spinner(f"Updating Line {bus_line}..."):
        routes = get_route_ids(bus_line)
        
        if not routes:
            st.error(f"No active data found for line {bus_line}.")
        else:
            # Get data
            buses = get_live_buses(routes)
            arrivals = get_nearby_arrivals(user_lat, user_lon, routes)
            
            # Initialize Map
            m = folium.Map(location=[user_lat, user_lon], zoom_start=14)
            
            # FIXED: .add_to(m) instead of .addTo(m)
            folium.Marker(
                [user_lat, user_lon], 
                popup="Your Location", 
                icon=folium.Icon(color="blue", icon="user", prefix='fa')
            ).add_to(m)
            
            # Add Bus Locations
            for bus in buses:
                if bus.get('lat') and bus.get('lon'):
                    folium.Marker(
                        [bus['lat'], bus['lon']],
                        popup=f"Line {bus_line}",
                        icon=folium.Icon(color="green", icon="bus", prefix='fa')
                    ).add_to(m)
            
            # UI Layout
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st_folium(m, width=800, height=500, key="bus_map")
            
            with col2:
                st.subheader("Nearest ETAs")
                found_eta = False
                for arr in arrivals:
                    if arr.get('gtfs_route_id') in routes:
                        eta_raw = arr.get('estimated_arrival_time')
                        if eta_raw:
                            found_eta = True
                            # Convert UTC to local display
                            eta_dt = datetime.fromisoformat(eta_raw.replace('Z', '+00:00'))
                            st.metric(label=f"Stop {arr.get('monitoring_ref')}", value=eta_dt.strftime('%H:%M'))
                
                if not found_eta:
                    st.write("No imminent arrivals near you.")

st.sidebar.button("🔄 Refresh Map")
