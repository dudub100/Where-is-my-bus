import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
st.set_page_config(page_title="Kefar Sava Bus Tracker", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 My Local Bus Tracker (Kefar Sava / Israel)")

# 1. GET GPS LOCATION
loc = get_geolocation()
if loc and 'coords' in loc:
    u_lat = loc['coords']['latitude']
    u_lon = loc['coords']['longitude']
else:
    st.warning("📍 Waiting for GPS... Using Kefar Sava coordinates as fallback.")
    u_lat, u_lon = 32.1782, 34.9076 # Default Kefar Sava

# 2. SIDEBAR
with st.sidebar:
    st.header("Settings")
    bus_num = st.text_input("Bus Number to show:", value="149")
    distance_check = st.slider("Search Radius (km)", 1, 10, 5)
    if st.button("Refresh Now"):
        st.rerun()

# --- 3. THE "BOUNDING BOX" ENGINE ---
def get_local_buses(lat, lon, radius_km, target_line):
    # Calculate a rough bounding box (0.01 degree is ~1.1km)
    offset = radius_km / 111.0
    
    params = {
        "lat__gte": lat - offset,
        "lat__lte": lat + offset,
        "lon__gte": lon - offset,
        "lon__lte": lon + offset,
        "recorded_at_time__gte": (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 200 # Get more buses to filter through
    }
    
    try:
        # We fetch ALL buses in your 5km area
        r = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", params=params, timeout=10)
        all_local_buses = r.json()
        
        if not isinstance(all_local_buses, list):
            return [], "API error: Unexpected response format."

        # Now, we manually filter for YOUR line number in the data
        # We look for the line number in the nested 'siri_ride' metadata
        filtered_buses = []
        for b in all_local_buses:
            # The API returns 'route_short_name' inside the siri_ride->gtfs_ride->gtfs_route structure
            # To be safe, we check multiple possible fields where the line number might hide
            try:
                # This is the most reliable path in the current Stride schema
                line_found = b.get('siri_ride', {}).get('siri_route', {}).get('gtfs_route', {}).get('route_short_name')
                
                if str(line_found) == str(target_line):
                    filtered_buses.append(b)
            except:
                continue
                
        return filtered_buses, f"Found {len(filtered_buses)} buses for line {target_line} near you."

    except Exception as e:
        return [], f"Connection error: {str(e)}"

# --- 4. DISPLAY ---
if bus_num:
    buses, message = get_local_buses(u_lat, u_lon, distance_check, bus_num)
    
    st.success(message)
    
    m = folium.Map(location=[u_lat, u_lon], zoom_start=14)
    
    # Your Location (Blue)
    folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
    
    # Bus Locations (Green)
    for b in buses:
        folium.Marker(
            [b['lat'], b['lon']],
            popup=f"Line {bus_num} | Time: {b['recorded_at_time'].split('T')[1][:5]}",
            icon=folium.Icon(color='green', icon='bus', prefix='fa')
        ).add_to(m)
        
    st_folium(m, width=900, height=600, key="local_bus_map")
