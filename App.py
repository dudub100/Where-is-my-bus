import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
st.set_page_config(page_title="Kefar Sava Bus Tracker - UTC Fix", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Live Bus Tracker (Timezone Corrected)")

# 1. TIME DIAGNOSTIC
now_utc = datetime.now(timezone.utc)
with st.sidebar:
    st.header("Time Sync")
    st.write(f"Local Time: `{datetime.now().strftime('%H:%M:%S')}`")
    st.write(f"Server (UTC): `{now_utc.strftime('%H:%M:%S')}`")
    
    st.header("Search")
    bus_num = st.text_input("Bus Line:", value="149")
    radius_km = st.slider("Radius (km)", 1, 10, 5)
    
    if st.button("🔄 Force Refresh"):
        st.rerun()

# 2. GPS (Fallback to Kefar Sava)
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# --- 3. THE "NO-JOIN" RELIABLE ENGINE ---
def get_buses_atomic(target_line, lat, lon, radius):
    try:
        # We ask for the latest 200 buses in the entire country from the last 15 minutes
        # This is the most "raw" query possible to avoid JOIN errors
        since_utc = (now_utc - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            "recorded_at_time__gte": since_utc,
            "limit": 250
        }
        
        # Pull the most recent 250 pulses from the whole network
        r = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", params=params, timeout=15)
        raw_data = r.json()

        if not isinstance(raw_data, list):
            return [], f"API returned non-list data: {str(raw_data)[:50]}"

        # Now, we do ALL the heavy filtering inside Python
        # This prevents the API from ignoring our filters
        filtered = []
        for b in raw_data:
            # 1. Filter by Line Number (Searching multiple meta fields)
            try:
                # Path 1: The standard short name
                line = b.get('siri_ride', {}).get('siri_route', {}).get('gtfs_route', {}).get('route_short_name')
                # Path 2: The line reference
                line_ref = b.get('siri_ride', {}).get('siri_route', {}).get('line_ref')
                
                match = (str(line) == str(target_line)) or (target_line in str(line_ref))
                
                if not match: continue
                
                # 2. Filter by Distance (Simple bounding box for speed)
                offset = radius / 111.0
                if not (lat - offset <= b['lat'] <= lat + offset): continue
                if not (lon - offset <= b['lon'] <= lon + offset): continue
                
                filtered.append(b)
            except:
                continue

        return filtered, f"Found {len(filtered)} matches after local processing."

    except Exception as e:
        return [], f"Request Failed: {str(e)}"

# --- 4. DISPLAY ---
buses, status = get_buses_atomic(bus_num, u_lat, u_lon, radius_km)

col1, col2 = st.columns([3, 1])

with col1:
    st.info(status)
    m = folium.Map(location=[u_lat, u_lon], zoom_start=14)
    folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)

    for b in buses:
        folium.Marker(
            [b['lat'], b['lon']],
            popup=f"Line {bus_num}",
            icon=folium.Icon(color='green', icon='bus', prefix='fa')
        ).add_to(m)
        
    st_folium(m, width=800, height=550, key="israel_final_map")

with col2:
    st.subheader("Results")
    if buses:
        for b in buses:
            st.write(f"✅ **Bus ID {b['id']}**")
            st.write(f"Last Seen: {b['recorded_at_time'].split('T')[-1][:8]}")
            st.divider()
    else:
        st.write("No matching buses within your parameters.")
        if st.checkbox("Show raw pool (DEBUG)"):
            st.write("First 3 items from API (before filtering):")
            st.json(requests.get(f"{BASE_URL}/siri_vehicle_locations/list", params={"limit": 3}).json())
