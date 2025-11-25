#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import time
import urllib.request
import shutil

ADDON_ID = 'service.cooler.autosetup'
REPO_URL = 'https://debe2025.github.io/cooler-repo/'
AURAMOD_URL = 'https://github.com/skyfsza/skin.auramod/archive/refs/heads/omega.zip'  # Fixed to lowercase 'omega'
CASTAGNAIT_REPO = 'https://castagnait.github.io/repo/repository.castagnait-2.0.1.zip'

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}]: {msg}', level=level)

def download(url, local_path):
    try:
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

def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f'Notification(Cooler Build, {msg}, {time_ms})')

log('Starting Cooler Auto Setup...')
notify('Setting up your perfect TV build... (2 min)', 10000)

# 1. Enable unknown sources
xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

# 2. Install CastagnaIT repo (for Netflix)
log('Installing CastagnaIT repo...')
xbmc.executebuiltin(f'InstallFromZip({CASTAGNAIT_REPO})')
if wait_for_addon('repository.castagnait', 20):
    xbmc.executebuiltin('InstallFromRepository(repository.castagnait, plugin.video.netflix)')
    wait_for_addon('plugin.video.netflix', 15)

# 3. Install common addons from official Kodi repo
log('Installing official addons...')
common = ['plugin.video.youtube', 'plugin.video.tubi', 'plugin.video.crackle', 'pvr.plutotv', 'plugin.video.popcornflix', 'plugin.video.internetarchive']
for addon in common:
    xbmc.executebuiltin(f'InstallAddon({addon})')
    wait_for_addon(addon, 10)

# 4. Install AuraMOD (try GitHub first, fallback to Kodi repo)
log('Installing AuraMOD...')
auramod_zip = 'special://temp/auramod.zip'
if download(AURAMOD_URL, auramod_zip):
    xbmc.executebuiltin(f'InstallFromZip(special://temp/, auramod.zip)')
    if wait_for_addon('skin.auramod', 20):
        log('AuraMOD installed from GitHub!')
    else:
        log('Fallback to official repo...')
        xbmc.executebuiltin('InstallFromRepository(Kodi Add-on Repository, skin.auramod)')
else:
    log('AuraMOD GitHub download failed, using official repo...')
    xbmc.executebuiltin('InstallFromRepository(Kodi Add-on Repository, skin.auramod)')
wait_for_addon('skin.auramod', 20)

# 5. Switch to AuraMOD and configure widgets
log('Switching to AuraMOD...')
xbmc.executebuiltin('ActivateWindow(Home)')
time.sleep(5)
xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
time.sleep(10)

# Configure basic widgets (AuraMOD supports these)
xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV, true)')
xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies, true)')
xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows, true)')

# 6. Enable PVR/EPG/Library
xbmc.executebuiltin('PVR.SetSetting(epg, true)')
xbmc.executebuiltin('PVR.SetSetting(channelmanager, true)')
xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

# Activate live addons for EPG
for addon in ['samsung.tv.plus', 'pvr.plutotv']:
    xbmc.executebuiltin(f'RunAddon({addon})')
    time.sleep(3)
    xbmc.executebuiltin('ActivateWindow(Home)')

# 7. Drop self-start files to userdata
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

# 8. FINAL CLEANUP – Delete this service
addon_path = xbmcvfs.translatePath(f'special://home/addons/{ADDON_ID}')
if os.path.exists(addon_path):
    shutil.rmtree(addon_path)
xbmc.executebuiltin(f'UninstallAddon({ADDON_ID})')

# Clean temp files
xbmcvfs.delete(xbmcvfs.translatePath(auramod_zip))

notify('Setup complete! Restarting into Live TV...', 5000)
log('Cooler Build fully automated – done!')
time.sleep(3)
xbmc.executebuiltin('RestartApp')