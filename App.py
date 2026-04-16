import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime
import pandas as pd

# --- APP CONFIG ---
st.set_page_config(page_title="Israel Bus Live", layout="wide", page_icon="🚌")
STRIDE_API = "https://open-bus-stride-api.hasadna.org.il"

st.title("🇮🇱 Israel Live Bus Tracker")

# --- STEP 1: GET USER GPS ---
# This triggers the browser permission popup
loc = get_geolocation()

if not loc:
    st.info("📍 Waiting for your location... Please allow GPS access in your browser.")
    # Fallback to a central point if GPS is slow/blocked
    u_lat, u_lon = 32.0853, 34.7818 
else:
    u_lat = loc['coords']['latitude']
    u_lon = loc['coords']['longitude']

# --- STEP 2: USER INPUT ---
with st.sidebar:
    st.header("Search")
    bus_line = st.text_input("Enter Bus Number:", value="189", help="e.g. 189, 149, 1")
    refresh = st.button("🔄 Refresh Now")

# --- DATA FETCHING (WITH CACHING) ---
@st.cache_data(ttl=300) # Cache line IDs for 5 mins
def get_route_ids(line_num):
    """Finds all internal Route IDs for a given bus number."""
    url = f"{STRIDE_API}/gtfs_routes/list"
    params = {"route_short_name": line_num, "limit": 20}
    try:
        r = requests.get(url, params=params)
        return [item['id'] for item in r.json()] if r.status_code == 200 else []
    except: return []

def get_live_locations(route_ids):
    """Gets real-time GPS of buses for specific Route IDs."""
    if not route_ids: return []
    ids_str = ",".join(map(str, route_ids))
    url = f"{STRIDE_API}/siri_vehicle_locations/list"
    params = {"siri_route__gtfs_route_id__in": ids_str, "limit": 50}
    try:
        r = requests.get(url, params=params)
        return r.json() if r.status_code == 200 else []
    except: return []

def get_nearby_etas(lat, lon, route_ids):
    """Finds the nearest stops and their predicted arrival times."""
    # 1. Find stops within 800m
    stop_url = f"{STRIDE_API}/gtfs_stops/list"
    stop_params = {"lat": lat, "lon": lon, "distance_m": 800}
    try:
        stops = requests.get(stop_url, params=stop_params).json()
        codes = [s['code'] for s in stops if s.get('code')]
        if not codes: return []
        
        # 2. Get arrival estimations for those stops
        est_url = f"{STRIDE_API}/siri_stop_estimations/list"
        est_params = {"monitoring_ref__in": ",".join(map(str, codes)), "limit": 50}
        all_ests = requests.get(est_url, params=est_params).json()
        
        # 3. Filter only for our specific bus routes
        return [e for e in all_ests if e.get('gtfs_route_id') in route_ids]
    except: return []

# --- STEP 3: LOGIC & MAPPING ---
if bus_line:
    routes = get_route_ids(bus_line)
    if not routes:
        st.error(f"Could not find any data for Line {bus_line}. Please check the number.")
    else:
        buses = get_live_locations(routes)
        etas = get_nearby_etas(u_lat, u_lon, routes)

        # Create Folium Map
        m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
        
        # User Marker
        folium.Marker(
            [u_lat, u_lon], popup="You", 
            icon=folium.Icon(color='blue', icon='user', prefix='fa')
        ).add_to(m)

        # Bus Markers
        for b in buses:
            if b.get('lat') and b.get('lon'):
                folium.Marker(
                    [b['lat'], b['lon']],
                    popup=f"Line {bus_line} (updated: {b.get('recorded_at_time')})",
                    icon=folium.Icon(color='green', icon='bus', prefix='fa')
                ).add_to(m)

        # DISPLAY LAYOUT
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st_folium(m, width=800, height=550, key="bus_map")
        
        with col2:
            st.subheader("Arrivals Near You")
            if not etas:
                st.write("No upcoming arrivals found within 800m.")
            else:
                for e in etas:
                    time_raw = e.get('estimated_arrival_time')
                    if time_raw:
                        # Simple string slice to get HH:MM from ISO format
                        time_display = time_raw.split('T')[1][:5]
                        st.metric(f"Stop {e.get('monitoring_ref')}", time_display)
