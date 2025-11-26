#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import time
import urllib.request
import json
import shutil
import threading

ADDON_ID = 'service.cooler.autosetup'
AURAMOD_GITHUB_API = 'https://api.github.com/repos/SerpentDrago/skin.auramod/releases/latest'
NETFLIX_GITHUB_API = 'https://api.github.com/repos/CastagnaIT/plugin.video.netflix/releases/latest'
TEMP_DIR = xbmcvfs.translatePath('special://temp/')
UPDATE_INTERVAL_HOURS = 6
restart_required = False

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}]: {msg}', level=level)

def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f'Notification(Cooler Build, {msg}, {time_ms})')

def download(url, local_path):
    try:
        log(f'Downloading {url} -> {local_path}')
        urllib.request.urlretrieve(url, xbmcvfs.translatePath(local_path))
        return True
    except Exception as e:
        log(f'Download failed: {e}', xbmc.LOGERROR)
        return False

def wait_for_addon(addon_id, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            return True
        time.sleep(1)
    return False

def install_zip(zip_path):
    if os.path.exists(zip_path):
        xbmc.executebuiltin(f'InstallFromZip({zip_path})')
        return True
    return False

# ────── AuraMOD ──────
def get_latest_auramod_release():
    try:
        with urllib.request.urlopen(AURAMOD_GITHUB_API) as response:
            data = json.load(response)
            tag = data.get('tag_name')
            for asset in data.get('assets', []):
                if asset['name'].endswith('.zip'):
                    return tag, asset['browser_download_url']
            return None, None
    except Exception as e:
        log(f'AuraMOD API failed: {e}', xbmc.LOGERROR)
        return None, None

def get_installed_auramod_version():
    try:
        return xbmcaddon.Addon('skin.auramod').getAddonInfo('version')
    except:
        return None

def auto_update_auramod():
    global restart_required
    tag, url = get_latest_auramod_release()
    current = get_installed_auramod_version()
    if not tag or not url or current == tag:
        return False
    notify(f'Updating AuraMOD to {tag}...', 6000)
    path = os.path.join(TEMP_DIR, 'auramod.zip')
    if download(url, path) and install_zip(path):
        xbmcvfs.delete(path)
        restart_required = True
        return True
    return False

# ────── Netflix ──────
def install_or_update_netflix():
    try:
        with urllib.request.urlopen(NETFLIX_GITHUB_API) as r:
            data = json.load(r)
            tag = data.get('tag_name')
            zip_url = next((a['browser_download_url'] for a in data.get('assets', []) if a['name'].endswith('.zip')), None)
            if not tag or not zip_url:
                raise Exception("No ZIP found")
    except Exception as e:
        log(f'Netflix API failed: {e}')
        notify('Install Netflix manually from GitHub releases.', 8000)
        return False

    current = None
    try:
        current = xbmcaddon.Addon('plugin.video.netflix').getAddonInfo('version')
    except: pass

    if current == tag:
        return False

    notify(f'Installing/Updating Netflix to {tag}...', 6000)
    path = os.path.join(TEMP_DIR, 'plugin.video.netflix.zip')
    if download(zip_url, path) and install_zip(path):
        wait_for_addon('plugin.video.netflix', 30)
        xbmcvfs.delete(path)
        return True
    return False

# ────── Periodic updater ──────
def periodic_update_check():
    while True:
        try:
            auto_update_auramod()
        except: pass
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)

# ────── Main setup ──────
def main_setup():
    log('Starting Cooler Auto Setup...')
    notify('Setting up your perfect TV build... (2-3 min)', 10000)

    xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

    # 1. Install bundled addons FIRST (fixes "unknown addon" errors)
    bundled = ['plugin.video.dstv.now', 'samsung.tv.plus', 'script.module.slyguy', 'slyguy.dependencies', 'script.module.inputstreamhelper']
    for a in bundled:
        xbmc.executebuiltin(f'InstallFromRepository(repository.myrepo, {a})')
        wait_for_addon(a, 15)

    # 2. Netflix (latest from GitHub)
    install_or_update_netflix()

    # 3. Official addons
    for a in ['plugin.video.youtube', 'plugin.video.tubi', 'plugin.video.crackle', 'pvr.plutotv', 'plugin.video.popcornflix', 'plugin.video.internetarchive']:
        xbmc.executebuiltin(f'InstallAddon({a})')
        wait_for_addon(a, 10)

    # 4. AuraMOD
    auto_update_auramod()

    # 5. Skin switch + widgets
    if wait_for_addon('skin.auramod', 20):
        xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
        time.sleep(8)
        for s in ['HomeWidgetLiveTV', 'HomeWidgetMovies', 'HomeWidgetTVShows']:
            xbmc.executebuiltin(f'Skin.SetBool({s}, true)')

    # 6. PVR & startup
    xbmc.executebuiltin('PVR.SetSetting(epg, true)')
    xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

    # 7. Activate live addons for EPG (now they exist)
    for a in ['samsung.tv.plus', 'pvr.plutotv']:
        xbmc.executebuiltin(f'RunAddon({a})')
        time.sleep(3)

    # 8. Self-start to TV Channels
    userdata = xbmcvfs.translatePath('special://profile/')
    with open(os.path.join(userdata, 'autoexec.py'), 'w') as f:
        f.write('import xbmc, time\ntime.sleep(10)\nxbmc.executebuiltin("ActivateWindow(TVChannels)")')
    with open(os.path.join(userdata, 'advancedsettings.xml'), 'w') as f:
        f.write('<advancedsettings><lookandfeel><startupwindow>tvchannels</startupwindow></lookandfeel><epg><epgupdate>5</epgupdate></epg><video><libraryautoupdate>true</libraryautoupdate></video></advancedsettings>')

    log('Cooler Build complete!')

# ────── Run ──────
def run_service():
    main_setup()
    threading.Thread(target=periodic_update_check, daemon=True).start()
    global restart_required
    if restart_required:
        notify('Restarting Kodi to apply AuraMOD update...', 5000)
        time.sleep(4)
        xbmc.executebuiltin('RestartApp')
    while True:
        time.sleep(60)

if __name__ == '__main__':
    run_service()