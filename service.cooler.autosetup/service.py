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
NETFLIX_GITHUB_API = 'https://api.github.com/repos/CastagnaIT/plugin.video.netflix/releases/latest'
AURAMOD_GITHUB_API = 'https://api.github.com/repos/SerpentDrago/skin.auramod/releases/latest'
TEMP_DIR = xbmcvfs.translatePath('special://temp/')
UPDATE_INTERVAL_HOURS = 6
restart_required = False


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}]: {msg}', level=level)


def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f'Notification(Cooler Build, {msg}, {time_ms})')


def download(url, local_path):
    """
    Download URL to local_path (Kodi can handle special://).
    """
    try:
        translated = xbmcvfs.translatePath(local_path)
        log(f'Downloading {url} -> {translated}')
        urllib.request.urlretrieve(url, translated)
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
    """
    Wrapper for InstallFromZip with safe path.
    """
    translated = xbmcvfs.translatePath(zip_path)
    if xbmcvfs.exists(translated) or os.path.exists(translated):
        xbmc.executebuiltin(f'InstallFromZip({translated})')
        return True
    log(f'Zip not found: {translated}', xbmc.LOGWARNING)
    return False


def force_refresh_addons():
    xbmc.executebuiltin('UpdateLocalAddons')
    time.sleep(3)  # Let Kodi scan


# ---------- AuraMOD helpers ----------
def get_latest_auramod_release():
    try:
        with urllib.request.urlopen(AURAMOD_GITHUB_API) as response:
            data = json.load(response)
            latest_version = data.get('tag_name')
            download_url = None
            for asset in data.get('assets', []):
                if asset.get('name', '').endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    break

            # Fallback: standard GitHub archive URL if no asset zip
            if not download_url and latest_version:
                download_url = f'https://github.com/SerpentDrago/skin.auramod/archive/refs/tags/{latest_version}.zip'

            log(f'Latest AuraMOD tag: {latest_version}, url: {download_url}')
            return latest_version, download_url
    except Exception as e:
        log(f'Failed to fetch latest AuraMOD release: {e}', xbmc.LOGERROR)
        return None, None


def get_installed_auramod_version():
    try:
        addon = xbmcaddon.Addon('skin.auramod')
        return addon.getAddonInfo('version')
    except Exception:
        return None


def auto_update_auramod():
    global restart_required

    latest_version, download_url = get_latest_auramod_release()
    installed_version = get_installed_auramod_version()
    log(f'AuraMOD installed: {installed_version}, latest: {latest_version}')

    if latest_version is None or download_url is None:
        log('Could not get latest AuraMOD release, skipping update...')
        return False

    if installed_version == latest_version:
        log('AuraMOD is already up-to-date.')
        return False

    notify(f'Installing/Updating AuraMOD to {latest_version}...', 5000)
    auramod_zip = os.path.join(TEMP_DIR, 'auramod.zip')

    if download(download_url, auramod_zip):
        if install_zip(auramod_zip):
            # wait for Kodi to actually register it
            if wait_for_addon('skin.auramod', 30):
                log(f'AuraMOD updated successfully to {latest_version}!')
                xbmcvfs.delete(xbmcvfs.translatePath(auramod_zip))
                restart_required = True
                return True
            else:
                log('AuraMOD zip installed but skin.auramod not visible.', xbmc.LOGERROR)
        else:
            log('Failed to install AuraMOD from zip.', xbmc.LOGERROR)
    else:
        log('Failed to download AuraMOD zip.', xbmc.LOGERROR)

    return False


# ---------- Netflix helpers ----------
def get_latest_netflix_release():
    try:
        with urllib.request.urlopen(NETFLIX_GITHUB_API) as response:
            data = json.load(response)
            latest_version = data.get('tag_name')
            download_url = None
            for asset in data.get('assets', []):
                if asset.get('name', '').endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    break

            log(f'Latest Netflix tag: {latest_version}, url: {download_url}')
            return latest_version, download_url
    except Exception as e:
        log(f'Failed to fetch latest Netflix release: {e}', xbmc.LOGERROR)
        return None, None


def get_installed_netflix_version():
    try:
        addon = xbmcaddon.Addon('plugin.video.netflix')
        return addon.getAddonInfo('version')
    except Exception:
        return None


def install_or_update_netflix():
    latest_version, download_url = get_latest_netflix_release()
    installed_version = get_installed_netflix_version()
    log(f'Netflix installed: {installed_version}, latest: {latest_version}')

    if latest_version is None or download_url is None:
        log('Could not get latest Netflix release, skipping...')
        notify('Install Netflix manually from GitHub releases.', 7000)
        return False

    if installed_version == latest_version:
        log('Netflix is already up-to-date.')
        return False

    notify(f'Installing/Updating Netflix to {latest_version}...', 5000)
    netflix_zip = os.path.join(TEMP_DIR, 'plugin.video.netflix.zip')

    if download(download_url, netflix_zip):
        if install_zip(netflix_zip):
            if wait_for_addon('plugin.video.netflix', 30):
                xbmcvfs.delete(xbmcvfs.translatePath(netflix_zip))
                log(f'Netflix installed/updated to {latest_version}.')
                return True
            else:
                log('Netflix zip installed but addon not visible yet.', xbmc.LOGWARNING)
        else:
            log('Failed to install Netflix from zip.', xbmc.LOGERROR)
    else:
        log('Failed to download Netflix zip.', xbmc.LOGERROR)

    return False


# ---------- Periodic updater ----------
def periodic_update_check():
    while True:
        try:
            log('Periodic check: AuraMOD update...')
            updated = auto_update_auramod()
            if updated:
                notify('AuraMOD updated! Restart Kodi to apply changes.', 7000)
        except Exception as e:
            log(f'Error during periodic update: {e}', xbmc.LOGERROR)
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)


# ---------- Main setup ----------
def main_setup():
    log('Starting Cooler Auto Setup...')
    notify('Setting up your perfect TV build... (2 min)', 10000)

    # Enable unknown sources
    xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

    # Force refresh to see bundled addons
    force_refresh_addons()

    # Install bundled addons first
    log('Installing bundled addons...')
    bundled = [
        'plugin.video.dstv.now',
        'samsung.tv.plus',
        'script.module.slyguy',
        'slyguy.dependencies',
        'script.module.inputstreamhelper',
    ]

    for addon in bundled:
        log(f'Installing {addon} from repository.myrepo...')
        xbmc.executebuiltin(f'InstallFromRepository(repository.myrepo, {addon})')
        if wait_for_addon(addon, 20):
            log(f'{addon} installed successfully')
        else:
            log(f'{addon} not detected – continuing', xbmc.LOGWARNING)

    # Install / update Netflix directly from GitHub
    install_or_update_netflix()

    # Install common official addons
    log('Installing official addons...')
    common_addons = [
        'plugin.video.youtube',
        'plugin.video.tubi',
        'plugin.video.crackle',
        'pvr.plutotv',
        'plugin.video.popcornflix',
        'plugin.video.internetarchive',
    ]
    for addon in common_addons:
        log(f'Installing official addon: {addon}')
        xbmc.executebuiltin(f'InstallAddon({addon})')
        wait_for_addon(addon, 10)

    # Initial AuraMOD install/update
    auto_update_auramod()

    # Switch to AuraMOD and configure widgets (only if really there)
    if wait_for_addon('skin.auramod', 20):
        xbmc.executebuiltin('ActivateWindow(Home)')
        time.sleep(5)
        xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
        time.sleep(10)
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows, true)')
    else:
        log('AuraMOD not installed – cannot switch skin.', xbmc.LOGWARNING)

    # Enable PVR/EPG/Library
    xbmc.executebuiltin('PVR.SetSetting(epg, true)')
    xbmc.executebuiltin('PVR.SetSetting(channelmanager, true)')
    xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

    # Activate live addons for EPG, but only if installed
    for addon in ['samsung.tv.plus', 'pvr.plutotv']:
        if xbmc.getCondVisibility(f'System.HasAddon({addon})'):
            log(f'Running live addon: {addon}')
            xbmc.executebuiltin(f'RunAddon({addon})')
            time.sleep(3)
            xbmc.executebuiltin('ActivateWindow(Home)')
        else:
            log(f'Skipping live addon (not installed): {addon}')

    # Drop self-start files to userdata
    userdata = xbmcvfs.translatePath('special://profile/')
    autoexec_content = (
        "import xbmc\n"
        "import time\n"
        "time.sleep(10)\n"
        "xbmc.executebuiltin('ActivateWindow(TVChannels)')\n"
    )
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

    with open(os.path.join(userdata, 'autoexec.py'), 'w', encoding='utf-8') as f:
        f.write(autoexec_content)
    with open(os.path.join(userdata, 'advancedsettings.xml'), 'w', encoding='utf-8') as f:
        f.write(advanced_content)

    log('Self-start files placed!')

    # Clean temp files
    for f in ['plugin.video.netflix.zip', 'auramod.zip']:
        temp_file = os.path.join(TEMP_DIR, f)
        translated = xbmcvfs.translatePath(temp_file)
        if xbmcvfs.exists(translated):
            xbmcvfs.delete(translated)

    log('Cooler Build complete!')


def cleanup_service():
    addon_path = xbmcvfs.translatePath(f'special://home/addons/{ADDON_ID}')
    if os.path.exists(addon_path):
        shutil.rmtree(addon_path)
    xbmc.executebuiltin(f'UninstallAddon({ADDON_ID})')
    log('Service cleanup done!')


def run_service():
    global restart_required

    main_setup()

    # Start periodic update checker in background
    updater_thread = threading.Thread(target=periodic_update_check, daemon=True)
    updater_thread.start()

    # Restart Kodi only if AuraMOD was updated
    if restart_required:
        notify('Restarting Kodi to apply AuraMOD update...', 5000)
        time.sleep(3)
        xbmc.executebuiltin('RestartApp')

    # Keep service alive
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(60):
            break


if __name__ == '__main__':
    run_service()
