import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
st.set_page_config(page_title="Israel Bus Tracker 2026", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Israel Live Bus Tracker")

# 1. GPS LOCATION (With Error Handling)
loc = get_geolocation()
if loc and 'coords' in loc:
    u_lat, u_lon = loc['coords']['latitude'], loc['coords']['longitude']
else:
    st.info("📍 Waiting for GPS... (Using default location: Kefar Sava)")
    u_lat, u_lon = 32.1782, 34.9076 

# 2. SIDEBAR
with st.sidebar:
    st.header("Bus Search")
    bus_num = st.text_input("Line Number:", value="149")
    st.caption("Try 149 (Kefar Sava) or 189 (Tel Aviv)")
    if st.button("Refresh Map"):
        st.rerun()

# --- 3. THE ROBUST DATA ENGINE ---
def get_bus_data(line_number):
    try:
        # Step 1: Find Route IDs
        r1 = requests.get(f"{BASE_URL}/gtfs_routes/list", params={"route_short_name": line_number, "limit": 10}, timeout=10)
        route_data = r1.json()
        
        # Check if the response is a list (API success)
        if not isinstance(route_data, list) or not route_data:
            return [], "No active route records found for this line."
        
        gtfs_ids = [r['id'] for r in route_data]

        # Step 2: Get Recent Rides
        # Using 2026-compliant timezone-aware datetime
        now = datetime.now(timezone.utc)
        start_limit = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        r2 = requests.get(
            f"{BASE_URL}/siri_rides/list", 
            params={
                "siri_route__gtfs_route_id__in": ",".join(map(str, gtfs_ids)),
                "scheduled_start_time__gte": start_limit,
                "limit": 50
            }, timeout=10
        )
        ride_data = r2.json()
        if not isinstance(ride_data, list) or not ride_data:
            return [], "Route found, but no buses are currently scheduled or active."

        ride_ids = [r['id'] for r in ride_data]

        # Step 3: Get Live GPS Positions
        # Stride API expects ISO format or YYYY-MM-DD
        loc_limit = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        r3 = requests.get(
            f"{BASE_URL}/siri_vehicle_locations/list",
            params={
                "siri_ride_id__in": ",".join(map(str, ride_ids)),
                "recorded_at_time__gte": loc_limit,
                "limit": 50
            }, timeout=10
        )
        buses = r3.json()
        
        if not isinstance(buses, list):
            return [], "API busy or returned unexpected data format."
            
        return buses, f"Success! Tracking {len(buses)} active buses."

    except Exception as e:
        return [], f"Connection error: {str(e)}"

# --- 4. RENDER MAP ---
if bus_num:
    buses, message = get_bus_data(bus_num)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"**Status:** {message}")
        m = folium.Map(location=[u_lat, u_lon], zoom_start=13)
        
        # User
        folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
        
        # Buses
        for b in buses:
            # Add small delay offset for smoother visuals
            folium.Marker(
                [b['lat'], b['lon']],
                popup=f"Line {bus_num} | ID: {b['id']}",
                icon=folium.Icon(color='green', icon='bus', prefix='fa')
            ).add_to(m)
            
        st_folium(m, width=800, height=500, key="israel_map_2026")

    with col2:
        st.subheader("Details")
        if buses:
            st.metric("Buses Found", len(buses))
            st.info("Green markers show reported positions from the last 20 mins.")
        else:
            st.write("No live vehicles detected.")

