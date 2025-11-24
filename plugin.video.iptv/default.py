import xbmcaddon
import xbmcgui
import xbmcplugin
import sys
import urllib.request
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Kodi handle and addon instance
handle = int(sys.argv[1])
addon = xbmcaddon.Addon()

# Collect up to 5 M3U playlist URLs and one EPG URL from settings
playlist_urls = [
    addon.getSetting(f"iptv_url_{i}") for i in range(1, 6)
    if addon.getSetting(f"iptv_url_{i}")
]
epg_url = addon.getSetting("epg_url")

# ============ Helper Functions ============

def fetch_url(url):
    """Fetch and return data from a URL (UTF-8 decoded)"""
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        xbmcgui.Dialog().notification("IPTV Addon", f"Error fetching: {e}", xbmcgui.NOTIFICATION_ERROR, 6000)
        return ""

def parse_m3u(data):
    """Parse an M3U file into a list of (channel_name, stream_url, logo, tvg_id)"""
    channels = []
    if not data:
        return channels

    name, logo, url, tvg_id = None, None, None, None
    lines = data.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            name_match = re.search(r'tvg-name="([^"]+)"', line)
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            id_match = re.search(r'tvg-id="([^"]+)"', line)
            title_match = re.search(r',(.+)', line)

            name = name_match.group(1) if name_match else (title_match.group(1).strip() if title_match else "Unknown")
            logo = logo_match.group(1) if logo_match else ""
            tvg_id = id_match.group(1) if id_match else ""
        elif line.startswith("http"):
            url = line
            if name and url:
                channels.append((name, url, logo, tvg_id))
            name, logo, url, tvg_id = None, None, None, None
    return channels

def load_epg(epg_url):
    """Download and parse XMLTV EPG data"""
    epg_data = {}
    if not epg_url:
        return epg_data
    xml_text = fetch_url(epg_url)
    if not xml_text:
        return epg_data
    try:
        root = ET.fromstring(xml_text)
        for prog in root.findall("programme"):
            channel = prog.attrib.get("channel", "")
            title = prog.findtext("title", "No Title")
            start = prog.attrib.get("start", "")[:12]
            stop = prog.attrib.get("stop", "")[:12]
            epg_data.setdefault(channel, []).append({
                "title": title,
                "start": start,
                "stop": stop
            })
    except Exception as e:
        xbmcgui.Dialog().notification("IPTV Addon", f"EPG Parse Error: {e}", xbmcgui.NOTIFICATION_ERROR, 6000)
    return epg_data

def find_current_show(epg, tvg_id):
    """Find current show title for a given channel ID"""
    if not tvg_id or tvg_id not in epg:
        return None
    now = datetime.utcnow().strftime("%Y%m%d%H%M")
    for show in epg[tvg_id]:
        start, stop = show["start"], show["stop"]
        if start <= now <= stop:
            return show["title"]
    return None

# ============ Main ============

def main():
    if not playlist_urls:
        xbmcgui.Dialog().notification("IPTV Addon", "Please set at least one M3U Playlist URL in Settings.", xbmcgui.NOTIFICATION_INFO, 5000)
        return

    xbmcgui.Dialog().notification("IPTV Addon", "Loading playlists...", xbmcgui.NOTIFICATION_INFO, 3000)

    all_channels = []
    for url in playlist_urls:
        data = fetch_url(url)
        channels = parse_m3u(data)
        all_channels.extend(channels)

    epg_data = load_epg(epg_url) if epg_url else {}

    if not all_channels:
        xbmcgui.Dialog().notification("IPTV Addon", "No channels found.", xbmcgui.NOTIFICATION_INFO, 4000)
        return

    # Display merged channel list
    for name, stream, logo, tvg_id in all_channels:
        now_showing = find_current_show(epg_data, tvg_id)
        label = f"{name}"
        if now_showing:
            label += f"  ▶ {now_showing}"

        li = xbmcgui.ListItem(label=label)
        li.setInfo('video', {'title': name})
        li.setProperty('IsPlayable', 'true')
        if logo:
            li.setArt({'icon': logo, 'thumb': logo})
        xbmcplugin.addDirectoryItem(handle, stream, li, False)

    xbmcplugin.endOfDirectory(handle)

if __name__ == "__main__":
    main()

