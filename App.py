import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timezone

# --- CONFIG ---
st.set_page_config(page_title="Israel Bus Tracker - Diagnostic", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Live Bus Tracker (Total Visibility)")

# 1. GPS LOCATION
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# 2. SIDEBAR
with st.sidebar:
    st.header("Settings")
    distance_m = st.slider("Search Radius (meters)", 500, 3000, 1200)
    st.info("I will show ALL buses within this range of your GPS.")
    if st.button("Refresh Map"):
        st.rerun()

# --- 3. DATA ENGINE ---
def get_all_nearby_buses(lat, lon, dist):
    try:
        # Step 1: Find Local Stops
        stop_params = {"lat": lat, "lon": lon, "distance_m": dist, "limit": 10}
        stops_res = requests.get(f"{BASE_URL}/gtfs_stops/list", params=stop_params, timeout=10).json()

        if not isinstance(stops_res, list) or not stops_res:
            return [], "No stops found in your immediate area."
        
        stop_codes = [s['code'] for s in stops_res if s.get('code')]

        # Step 2: Get ALL Estimations for these stops
        est_params = {"monitoring_ref__in": ",".join(map(str, stop_codes)), "limit": 50}
        arrivals_data = requests.get(f"{BASE_URL}/siri_stop_estimations/list", params=est_params, timeout=10).json()

        if not isinstance(arrivals_data, list):
            return [], "API busy. Please wait a moment and refresh."

        # Step 3: Get locations for these rides
        found_buses = []
        for arr in arrivals_data:
            ride_id = arr.get('siri_ride_id')
            # Attempt to find the line name from any available field
            line_name = (
                arr.get('siri_ride', {}).get('siri_route', {}).get('gtfs_route', {}).get('route_short_name') or 
                arr.get('siri_ride', {}).get('siri_route', {}).get('line_ref') or 
                "Unknown"
            )

            # Get location
            loc_res = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", 
                                   params={"siri_ride_id": ride_id, "limit": 1}).json()
            
            if isinstance(loc_res, list) and loc_res:
                bus = loc_res[0]
                bus['line'] = line_name
                bus['eta'] = arr.get('estimated_arrival_time', '')
                found_buses.append(bus)
        
        return found_buses, f"Showing {len(found_buses)} buses near you."

    except Exception as e:
        return [], f"Engine Error: {str(e)}"

# --- 4. RENDER ---
buses, log_msg = get_all_nearby_buses(u_lat, u_lon, distance_m)

col1, col2 = st.columns([3, 1])

with col1:
    st.success(log_msg)
    m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
    folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    for b in buses:
        label = f"Line {b['line']}"
        folium.Marker(
            [b['lat'], b['lon']],
            popup=label,
            tooltip=label,
            icon=folium.Icon(color='green', icon='bus', prefix='fa')
        ).add_to(m)

    st_folium(m, width=800, height=550, key="israel_map_diag")

with col2:
    st.subheader("Buses Found")
    if buses:
        for b in buses:
            st.write(f"🚌 **Line {b['line']}**")
            st.write(f"ETA: {b['eta'].split('T')[-1][:5]}")
            st.divider()
    else:
        st.write("No buses are currently heading to stops near you.")

with st.expander("🛠️ Debug: Raw Data From Stride"):
    st.json(buses if buses else {"status": "Zero results from the MOT feed"})
