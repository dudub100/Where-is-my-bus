import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timezone

# --- CONFIG ---
st.set_page_config(page_title="Kefar Sava Bus Tracker", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Kefar Sava Live Bus Tracker")

# 1. GET GPS (Fallback to Kefar Sava Center)
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# 2. UI
with st.sidebar:
    st.header("Search")
    target_bus = st.text_input("Bus Number (e.g. 149, 567, 1):", value="149")
    st.write(f"📍 Searching within 1km of: `{u_lat:.4f}, {u_lon:.4f}`")
    if st.button("Refresh Now"):
        st.rerun()

# --- 3. DATA ENGINE (STATION-CENTRIC) ---
def get_arrivals_near_me(lat, lon, line_filter):
    try:
        # STEP 1: Find 5 closest stops
        # This uses the GTFS stops table which is very fast
        stop_params = {"lat": lat, "lon": lon, "distance_m": 1000, "limit": 5}
        stops_res = requests.get(f"{BASE_URL}/gtfs_stops/list", params=stop_params, timeout=10).json()
        
        if not stops_res:
            return [], "No bus stops found within 1km of your location."

        stop_codes = [s['code'] for s in stops_res if s.get('code')]
        
        # STEP 2: Get live estimations for these stops
        # This returns buses actually heading towards you right now
        est_params = {
            "monitoring_ref__in": ",".join(map(str, stop_codes)),
            "limit": 100
        }
        all_arrivals = requests.get(f"{BASE_URL}/siri_stop_estimations/list", params=est_params, timeout=10).json()
        
        # STEP 3: Filter for the user's specific bus line
        my_buses = []
        for arr in all_arrivals:
            # Check the line number (route_short_name)
            line = arr.get('siri_ride', {}).get('siri_route', {}).get('gtfs_route', {}).get('route_short_name')
            if str(line) == str(line_filter):
                # Get the bus coordinates from the latest vehicle location record
                ride_id = arr.get('siri_ride_id')
                # We fetch the specific location for this ride
                loc_res = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", 
                                       params={"siri_ride_id": ride_id, "limit": 1}, timeout=5).json()
                if loc_res:
                    bus_data = loc_res[0]
                    bus_data['eta'] = arr.get('estimated_arrival_time')
                    bus_data['stop_name'] = arr.get('monitoring_ref')
                    my_buses.append(bus_data)
        
        return my_buses, f"Success: Found {len(my_buses)} active buses for line {line_filter}."

    except Exception as e:
        return [], f"Connection Error: {str(e)}"

# --- 4. RENDER ---
buses, message = get_arrivals_near_me(u_lat, u_lon, target_bus)

col1, col2 = st.columns([3, 1])

with col1:
    st.info(message)
    m = folium.Map(location=[u_lat, u_lon], zoom_start=15)
    
    # You
    folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
    
    # Buses
    for b in buses:
        eta_time = b['eta'].split('T')[1][:5] if 'eta' in b else "Unknown"
        folium.Marker(
            [b['lat'], b['lon']],
            popup=f"Line {target_bus} | Arriving: {eta_time}",
            icon=folium.Icon(color='green', icon='bus', prefix='fa')
        ).add_to(m)
        
    st_folium(m, width=800, height=550, key="ks_bus_map")

with col2:
    st.subheader("Upcoming ETAs")
    if not buses:
        st.write("No imminent arrivals.")
    else:
        for b in buses:
            eta = b['eta'].split('T')[1][:5]
            st.metric(label=f"To Stop {b['stop_name']}", value=eta)
