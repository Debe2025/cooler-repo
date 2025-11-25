#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xbmc, xbmcgui, xbmcvfs, xbmcaddon
import os, time, urllib.request, shutil

ADDON = xbmcaddon.Addon()
log = lambda msg: xbmc.log(f'[Cooler AutoSetup]: {msg}', xbmc.LOGINFO)
notify = lambda msg: xbmc.executebuiltin(f'Notification(Cooler Build,{msg},8000)')

# URLs
AURAMOD_URL = 'https://github.com/skyfsza/skin.auramod/archive/refs/heads/omega.zip'
CASTAGNAIT_REPO = 'https://castagnait.github.io/repo/repository.castagnait-2.0.1.zip'

def download(url, dest):
    urllib.request.urlretrieve(url, xbmcvfs.translatePath(dest))

notify('Setting up your perfect TV build...')

# 1. Install official + CastagnaIT repos (Netflix, YouTube, Tubi, etc.)
xbmc.executebuiltin('InstallFromZi[](https://castagnait.github.io/repo/,repository.castagnait-2.0.1.zip)')
time.sleep(15)

# 2. Install common addons from official repos
common = ['plugin.video.youtube', 'plugin.video.tubi', 'plugin.video.crackle', 'pvr.plutotv']
for a in common:
    xbmc.executebuiltin(f'InstallAddon({a})')
    time.sleep(8)

# 3. Install AuraMOD
download(AURAMOD_URL, 'special://temp/auramod.zip')
xbmc.executebuiltin('InstallFromZip(special://temp/,auramod.zip)')
time.sleep(20)
xbmc.executebuiltin('UpdateLocalAddons')  # refresh

# 4. Switch skin
xbmc.executebuiltin('Skin.SetString(Skin.Current,skin.auramod)')

# 5. Configure home + startup
xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV,true)')
xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies,true)')
xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows,true)')

# 6. Self-start into Live TV
userdata = xbmcvfs.translatePath('special://profile/')
open(os.path.join(userdata, 'autoexec.py'), 'w').write(
    'import xbmc, time\ntime.sleep(10)\nxbmc.executebuiltin("ActivateWindow(TVChannels)")\n'
)
open(os.path.join(userdata, 'advancedsettings.xml'), 'w').write(
    '<advancedsettings><lookandfeel><startupwindow>tvchannels</startupwindow></lookandfeel></advancedsettings>'
)

# 7. Self-delete this service
shutil.rmtree(xbmcvfs.translatePath('special://home/addons/service.cooler.autosetup'))
notify('Done! Restarting into Live TV...')
time.sleep(3)
xbmc.executebuiltin('RestartApp')