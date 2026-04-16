import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from datetime import datetime, timedelta, timezone

# --- CONFIG ---
st.set_page_config(page_title="Kefar Sava Bus Tracker 2026", layout="wide")
BASE_URL = "https://open-bus-stride-api.hasadna.org.il"

st.title("🚌 Israel Live Bus Tracker (2026 Fix)")

# 1. TIME & GPS SYNC
now_utc = datetime.now(timezone.utc)
with st.sidebar:
    st.header("Status")
    # Clarifying the UTC offset for you
    st.write(f"🇮🇱 Local: `{datetime.now().strftime('%H:%M')}`")
    st.write(f"🌍 UTC: `{now_utc.strftime('%H:%M')}` (Server Time)")
    
    bus_num = st.text_input("Bus Number:", value="149")
    if st.button("🔄 Refresh Data"):
        st.rerun()

# Get GPS (Default to Kefar Sava)
loc = get_geolocation()
u_lat, u_lon = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (32.1782, 34.9076)

# --- 2. THE 2026 DATA ENGINE ---
def get_2026_buses(line_number):
    # We look back 30 minutes in UTC
    # Format: 2026-04-16T14:31:00Z
    since_utc = (now_utc - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # CRITICAL: order_by=-recorded_at_time forces the LATEST data first
    params = {
        "siri_ride__siri_route__gtfs_route__route_short_name": line_number,
        "recorded_at_time__gte": since_utc,
        "order_by": "-recorded_at_time", 
        "limit": 50
    }
    
    try:
        r = requests.get(f"{BASE_URL}/siri_vehicle_locations/list", params=params, timeout=15)
        data = r.json()
        
        if not isinstance(data, list):
            return [], f"API Info: {data.get('detail', 'No buses active right now.')}"
            
        # Extra safety: filter out any leftover historical data
        current_year = now_utc.year
        valid_buses = [b for b in data if str(current_year) in b.get('recorded_at_time', '')]
        
        return valid_buses, f"Found {len(valid_buses)} active buses for line {line_number}."
    except Exception as e:
        return [], f"Connection Error: {str(e)}"

# --- 3. RENDER MAP ---
if bus_num:
    buses, status = get_2026_buses(bus_num)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.info(status)
        m = folium.Map(location=[u_lat, u_lon], zoom_start=14)
        
        # You
        folium.Marker([u_lat, u_lon], popup="You", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
        
        # The Buses
        for b in buses:
            # Convert UTC recorded time to local display (add 3 hours)
            utc_time = datetime.fromisoformat(b['recorded_at_time'].replace('Z', '+00:00'))
            local_time = utc_time + timedelta(hours=3)
            
            folium.Marker(
                [b['lat'], b['lon']],
                popup=f"Line {bus_num} | Last seen: {local_time.strftime('%H:%M')}",
                icon=folium.Icon(color='green', icon='bus', prefix='fa')
            ).add_to(m)
            
        st_folium(m, width=850, height=550, key="bus_map_2026")

    with col2:
        st.subheader("Latest Pings")
        if buses:
            for b in buses[:5]: # Show top 5 latest
                st.write(f"🆔 **Bus {b['id']}**")
                st.write(f"📍 Lat: {b['lat']:.4f}")
                st.write(f"🕒 Time: {b['recorded_at_time'].split('T')[1][:5]} UTC")
                st.divider()
        else:
            st.write("No live vehicles found in your area.")
