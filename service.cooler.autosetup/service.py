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
CASTAGNAIT_REPO = 'https://castagnait.github.io/repository.castagnait/repository.castagnait-1.0.0.zip'
AURAMOD_GITHUB_API = 'https://api.github.com/repos/SerpentDrago/skin.auramod/releases/latest'
TEMP_DIR = xbmcvfs.translatePath('special://temp/')
UPDATE_INTERVAL_HOURS = 6  # Check for updates every 6 hours

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

def get_latest_auramod_release():
    try:
        with urllib.request.urlopen(AURAMOD_GITHUB_API) as response:
            data = json.load(response)
            latest_version = data.get('tag_name')
            download_url = None
            for asset in data.get('assets', []):
                if asset['name'].endswith('.zip'):
                    download_url = asset['browser_download_url']
                    break
            return latest_version, download_url
    except Exception as e:
        log(f'Failed to fetch latest AuraMOD release: {e}', xbmc.LOGERROR)
        return None, None

def get_installed_auramod_version():
    try:
        addon = xbmcaddon.Addon('skin.auramod')
        return addon.getAddonInfo('version')
    except:
        return None

def install_zip(zip_path):
    if os.path.exists(zip_path):
        xbmc.executebuiltin(f'InstallFromZip({zip_path})')
        return True
    return False

def switch_to_auramod():
    xbmc.executebuiltin('ActivateWindow(Home)')
    time.sleep(2)
    xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
    time.sleep(5)
    xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV, true)')
    xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies, true)')
    xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows, true)')
    log('AuraMOD activated and widgets configured!')

def auto_update_auramod():
    latest_version, download_url = get_latest_auramod_release()
    installed_version = get_installed_auramod_version()
    log(f'Installed AuraMOD: {installed_version}, Latest: {latest_version}')

    if latest_version is None or download_url is None:
        log('Could not get latest AuraMOD release, skipping update...')
        return False

    if installed_version != latest_version:
        notify(f'Updating AuraMOD to {latest_version}...', 5000)
        auramod_zip = os.path.join(TEMP_DIR, 'auramod.zip')
        if download(download_url, auramod_zip):
            if install_zip(auramod_zip):
                log(f'AuraMOD updated successfully to {latest_version}!')
                xbmcvfs.delete(auramod_zip)
                switch_to_auramod()  # Auto-restart skin
                notify(f'AuraMOD updated to {latest_version} and activated!', 7000)
                return True
            else:
                log('Failed to install AuraMOD from zip.', xbmc.LOGERROR)
        else:
            log('Failed to download AuraMOD zip.', xbmc.LOGERROR)
    else:
        log('AuraMOD is already up-to-date.')
    return False

def periodic_update_check():
    while True:
        try:
            log('Checking for AuraMOD updates...')
            auto_update_auramod()
        except Exception as e:
            log(f'Error during periodic update: {e}', xbmc.LOGERROR)
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)

def main_setup():
    log('Starting Cooler Auto Setup...')
    notify('Setting up your perfect TV build... (2 min)', 10000)

    xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

    # Install CastagnaIT repo
    log('Installing CastagnaIT repo...')
    castagna_zip = os.path.join(TEMP_DIR, 'repository.castagnait.zip')
    if download(CASTAGNAIT_REPO, castagna_zip):
        install_zip(castagna_zip)
        if wait_for_addon('repository.castagnait', 20):
            xbmc.executebuiltin('InstallFromRepository(repository.castagnait, plugin.video.netflix)')
            wait_for_addon('plugin.video.netflix', 15)

    # Install common addons
    log('Installing official addons...')
    common_addons = [
        'plugin.video.youtube',
        'plugin.video.tubi',
        'plugin.video.crackle',
        'pvr.plutotv',
        'plugin.video.popcornflix',
        'plugin.video.internetarchive'
    ]
    for addon in common_addons:
        xbmc.executebuiltin(f'InstallAddon({addon})')
        wait_for_addon(addon, 10)

    # Initial AuraMOD install/update
    auto_update_auramod()

    # Enable PVR/EPG/Library
    xbmc.executebuiltin('PVR.SetSetting(epg, true)')
    xbmc.executebuiltin('PVR.SetSetting(channelmanager, true)')
    xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

    # Activate live addons for EPG
    for addon in ['samsung.tv.plus', 'pvr.plutotv']:
        xbmc.executebuiltin(f'RunAddon({addon})')
        time.sleep(3)
        xbmc.executebuiltin('ActivateWindow(Home)')

    # Drop self-start files to userdata
    userdata = xbmcvfs.translatePath('special://profile/')
    autoexec_content = '''import xbmc
import time
time.sleep(10)
xbmc.executebuiltin('ActivateWindow(TVChannels)')'''
    advanced_content = '''<advancedsettings>
    <lookandfeel>
        <startupwindow>tvchannels</startupwindow>
    </lookandfeel>
    <epg>
        <epgupdate>5</epgupdate>
    </epg>
    <video>
        <libraryautoupdate>true</libraryautoupdate>
    </video>
    <pvr>
        <continueonstartup>true</continueonstartup>
    </pvr>
</advancedsettings>'''
    with open(os.path.join(userdata, 'autoexec.py'), 'w') as f:
        f.write(autoexec_content)
    with open(os.path.join(userdata, 'advancedsettings.xml'), 'w') as f:
        f.write(advanced_content)
    log('Self-start files placed!')

    # Clean temp files
    for f in ['repository.castagnait.zip', 'auramod.zip']:
        temp_file = os.path.join(TEMP_DIR, f)
        if xbmcvfs.exists(temp_file):
            xbmcvfs.delete(temp_file)

def cleanup_service():
    addon_path = xbmcvfs.translatePath(f'special://home/addons/{ADDON_ID}')
    if os.path.exists(addon_path):
        shutil.rmtree(addon_path)
    xbmc.executebuiltin(f'UninstallAddon({ADDON_ID})')
    log('Service cleanup done!')

def run_service():
    main_setup()
    updater_thread = threading.Thread(target=periodic_update_check, daemon=True)
    updater_thread.start()
    while True:
        time.sleep(60)

if __name__ == '__main__':
    run_service()
