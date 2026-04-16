import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta

# --- CONFIG ---
st.set_page_config(page_title="Israel Bus Tracker PRO", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Israel Live Bus Tracker (Fixed)")

# 1. GPS LOCATION
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# 2. SIDEBAR
with st.sidebar:
    st.header("Search")
    bus_num = st.text_input("Bus Number:", value="149")
    st.info("Try '149' or '1' for best testing.")
    if st.button("Force Refresh"):
        st.rerun()

# --- 3. THE THREE-STEP DATA FETCH ---
def get_verified_bus_locations(line_number):
    """
    Step 1: Get GTFS Route IDs for the line number
    Step 2: Get active Siri Ride IDs for those Route IDs
    Step 3: Get Vehicle Locations for those Ride IDs
    """
    try:
        # STEP 1: Get Route IDs (Static Data)
        # ----------------------------------
        r1 = requests.get(f"{BASE_URL}/gtfs_routes/list", params={"route_short_name": line_number, "limit": 20})
        gtfs_ids = [r['id'] for r in r1.json()]
        if not gtfs_ids:
            return [], "No Route IDs found."

        # STEP 2: Get Active Rides (Real-time Meta)
        # ----------------------------------------
        # Look for rides started in the last 4 hours
        start_time = (datetime.utcnow() - timedelta(hours=4)).isoformat()
        r2 = requests.get(
            f"{BASE_URL}/siri_rides/list", 
            params={
                "siri_route__gtfs_route_id__in": ",".join(map(str, gtfs_ids)),
                "scheduled_start_time__gte": start_time,
                "limit": 100
            }
        )
        ride_ids = [r['id'] for r in r2.json()]
        if not ride_ids:
            return [], f"Found routes ({len(gtfs_ids)}), but no active rides in the last 4h."

        # STEP 3: Get Vehicle Locations (Live GPS)
        # ---------------------------------------
        # Look for locations reported in the last 15 mins
        loc_time = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        r3 = requests.get(
            f"{BASE_URL}/siri_vehicle_locations/list",
            params={
                "siri_ride_id__in": ",".join(map(str, ride_ids)),
                "recorded_at_time__gte": loc_time,
                "limit": 50
            }
        )
        buses = r3.json()
        return buses, f"Success! Found {len(buses)} buses for {len(ride_ids)} active rides."

    except Exception as e:
        return [], f"Error: {str(e)}"

# --- 4. MAP & DISPLAY ---
if bus_num:
    buses, status_msg = get_verified_bus_locations(bus_num)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.write(f"**Status:** {status_msg}")
        m = folium.Map(location=[u_lat, u_lon], zoom_start=13)
        
        # User Marker
        folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
        
        # Filtered Bus Markers
        for b in buses:
            folium.Marker(
                [b['lat'], b['lon']],
                popup=f"Line {bus_num} - Updated {b['recorded_at_time'].split('T')[1][:5]}",
                icon=folium.Icon(color='green', icon='bus', prefix='fa')
            ).add_to(m)
            
        st_folium(m, width=800, height=500, key="israel_map")

    with col2:
        st.subheader("Diagnostic Log")
        if buses:
            st.json({
                "Sample Bus ID": buses[0]['id'],
                "Ride ID": buses[0]['siri_ride_id'],
                "Line Number": bus_num
            })
        else:
            st.write("No live data to display.")
