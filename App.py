import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timezone

# --- CONFIG ---
st.set_page_config(page_title="Kefar Sava Bus Tracker", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Live Bus Tracker (Robust 2026)")

# 1. GPS LOCATION (Fallback to Kefar Sava)
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# 2. SIDEBAR
with st.sidebar:
    st.header("Search")
    target_bus = st.text_input("Bus Line (e.g. 149, 1, 567):", value="149")
    distance_m = st.slider("Search Radius (meters)", 500, 5000, 1500)
    if st.button("Refresh Map"):
        st.rerun()

# --- 3. THE DEFENSIVE ENGINE ---
def get_verified_data(lat, lon, dist, line_filter):
    try:
        # Step 1: Find Local Stops
        stop_params = {"lat": lat, "lon": lon, "distance_m": dist, "limit": 8}
        r1 = requests.get(f"{BASE_URL}/gtfs_stops/list", params=stop_params, timeout=10)
        stops_data = r1.json()

        # DEFENSIVE CHECK 1: Is it a list?
        if not isinstance(stops_data, list):
            return [], f"API Error (Stops): {stops_data.get('detail', 'Unknown error')}"
        
        stop_codes = [s['code'] for s in stops_data if isinstance(s, dict) and s.get('code')]
        if not stop_codes:
            return [], "No bus stops found in this radius."

        # Step 2: Get Live Estimations (Arrivals)
        est_params = {"monitoring_ref__in": ",".join(map(str, stop_codes)), "limit": 100}
        r2 = requests.get(f"{BASE_URL}/siri_stop_estimations/list", params=est_params, timeout=10)
        arrivals_data = r2.json()

        # DEFENSIVE CHECK 2: Is it a list?
        if not isinstance(arrivals_data, list):
            return [], f"API Error (Arrivals): {arrivals_data.get('detail', 'No arrivals currently')}"

        # Step 3: Filter and Match
        my_buses = []
        for arr in arrivals_data:
            # Skip if arr is not a dictionary (prevents the 'str' attribute error)
            if not isinstance(arr, dict): continue
            
            # Navigate the nested JSON safely
            siri_ride = arr.get('siri_ride') or {}
            siri_route = siri_ride.get('siri_route') or {}
            gtfs_route = siri_route.get('gtfs_route') or {}
            line_found = gtfs_route.get('route_short_name')

            if str(line_found) == str(line_filter):
                ride_id = arr.get('siri_ride_id')
                # Get specific location for this ride
                loc_res = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", 
                                       params={"siri_ride_id": ride_id, "limit": 1}).json()
                
                if isinstance(loc_res, list) and len(loc_res) > 0:
                    bus = loc_res[0]
                    bus['eta'] = arr.get('estimated_arrival_time')
                    bus['stop_id'] = arr.get('monitoring_ref')
                    my_buses.append(bus)
        
        return my_buses, f"Success! Found {len(my_buses)} buses for line {line_filter}."

    except Exception as e:
        return [], f"Engine Error: {str(e)}"

# --- 4. RENDER ---
buses, log_msg = get_verified_data(u_lat, u_lon, distance_m, target_bus)

col1, col2 = st.columns([3, 1])

with col1:
    st.info(log_msg)
    m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
    folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    for b in buses:
        # Standard time slice for 2026 ISO format
        time_str = b.get('eta', '').split('T')[-1][:5] if b.get('eta') else "??:??"
        folium.Marker(
            [b['lat'], b['lon']],
            popup=f"Line {target_bus} | ETA: {time_str}",
            icon=folium.Icon(color='green', icon='bus', prefix='fa')
        ).add_to(m)

    st_folium(m, width=850, height=550, key="israel_map_final")

with col2:
    st.subheader("Live Arrivals")
    if buses:
        for b in buses:
            st.metric(f"Stop {b['stop_id']}", b.get('eta', '').split('T')[-1][:5])
    else:
        st.write("No imminent arrivals.")

# --- DEBUG CONSOLE ---
with st.expander("🛠️ Developer API Inspector"):
    st.write("Raw data sample from last request:")
    st.json(buses[:2] if buses else {"status": "No buses matched your filter"})
