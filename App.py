import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Israel Bus Live", layout="wide", page_icon="🚌")
STRIDE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Israel Live Bus Tracker")

# 1. GET USER LOCATION
loc = get_geolocation()
if not loc:
    st.info("📍 Fetching your GPS... Please allow access. (Default: Tel Aviv)")
    u_lat, u_lon = 32.0853, 34.7818 
else:
    u_lat, u_lon = loc['coords']['latitude'], loc['coords']['longitude']

# 2. SEARCH INTERFACE
with st.sidebar:
    st.header("Search")
    bus_num = st.text_input("Enter Bus Number:", value="149")
    st.caption("Common lines: 149, 189, 1, 42")
    refresh = st.button("🔄 Refresh Data")

# --- DATA FETCHING (TWO-STEP PROCESS) ---

def get_live_data(line_number):
    """
    Step 1: Get the internal GTFS Route IDs for the line number.
    Step 2: Use those IDs to fetch the Real-Time (SIRI) locations.
    """
    try:
        # STEP 1: Find Route IDs
        route_res = requests.get(
            f"{STRIDE_URL}/gtfs_routes/list", 
            params={"route_short_name": line_number, "limit": 50}
        )
        if route_res.status_code != 200: return [], []
        
        route_ids = [r['id'] for r in route_res.json()]
        if not route_ids: return [], []

        # STEP 2: Find Live Locations for these Route IDs
        # We look back 15 minutes to find active buses
        since_time = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        
        # We filter vehicle locations by siri_ride__gtfs_ride__gtfs_route_id
        ids_str = ",".join(map(str, route_ids))
        loc_params = {
            "siri_ride__gtfs_ride__gtfs_route_id__in": ids_str,
            "recorded_at_time__gte": since_time,
            "limit": 100
        }
        
        loc_res = requests.get(f"{STRIDE_URL}/siri_vehicle_locations/list", params=loc_params)
        buses = loc_res.json() if loc_res.status_code == 200 else []

        return buses, route_ids
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return [], []

# --- 3. LOGIC & MAPPING ---
if bus_num:
    with st.spinner(f"Filtering Line {bus_num}..."):
        buses, route_ids = get_live_data(bus_num)
        
        # Display Summary
        if not buses:
            st.warning(f"No active buses found for line {bus_num}. (Check if it's currently running)")
        else:
            st.success(f"Tracking {len(buses)} vehicles for line {bus_num}")

        # Create Map
        m = folium.Map(location=[u_lat, u_lon], zoom_start=14)
        
        # User Marker
        folium.Marker(
            [u_lat, u_lon], popup="You", 
            icon=folium.Icon(color='blue', icon='user', prefix='fa')
        ).add_to(m)

        # Bus Markers (Filtered by your specific line)
        for b in buses:
            folium.Marker(
                [b['lat'], b['lon']],
                popup=f"Line {bus_num} - Updated {b['recorded_at_time'].split('T')[1][:5]}",
                icon=folium.Icon(color='green', icon='bus', prefix='fa')
            ).add_to(m)

        # UI Layout
        col1, col2 = st.columns([3, 1])
        with col1:
            st_folium(m, width=800, height=500, key="israel_bus_map")
        
        with col2:
            st.subheader("Live Status")
            if buses:
                st.write(f"**Route IDs found:** {len(route_ids)}")
                st.write("**Latest Data Point:**")
                st.json({
                    "ID": buses[0]['id'],
                    "Time": buses[0]['recorded_at_time'],
                    "Lat": buses[0]['lat']
                })

