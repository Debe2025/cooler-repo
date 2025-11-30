#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hardened service.cooler.autosetup
- robust download/install for GitHub release zips (Netflix + AuraMOD)
- fallback extract+rename if InstallFromZip doesn't make addon visible
- forces Kodi to rescan addons and waits for addon visibility
"""
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import time
import urllib.request
import urllib.error
import urllib.parse
import json
import shutil
import threading
import zipfile

ADDON_ID = 'service.cooler.autosetup'
NETFLIX_GITHUB_API = 'https://api.github.com/repos/CastagnaIT/plugin.video.netflix/releases/latest'
AURAMOD_GITHUB_API = 'https://api.github.com/repos/SerpentDrago/skin.auramod/releases/latest'
TEMP_DIR = xbmcvfs.translatePath('special://temp/')
ADDONS_DIR = xbmcvfs.translatePath('special://home/addons/')
UPDATE_INTERVAL_HOURS = 6


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}]: {msg}', level=level)


def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f'Notification(Cooler Build, {msg}, {time_ms})')


def translate(p):
    return xbmcvfs.translatePath(p)


def download(url, local_path_special):
    """
    Download URL to local special:// path. Returns translated real path or None.
    """
    try:
        translated = translate(local_path_special)
        parent = os.path.dirname(translated)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        log(f'Downloading {url} -> {translated}')
        # ensure URL is well encoded
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(translated, 'wb') as out:
                shutil.copyfileobj(resp, out)
        log(f'Download complete: {translated}')
        return translated
    except urllib.error.HTTPError as e:
        log(f'HTTPError {e.code} for {url}', xbmc.LOGERROR)
    except urllib.error.URLError as e:
        log(f'URLError {e.reason} for {url}', xbmc.LOGERROR)
    except Exception as e:
        log(f'Download failed: {e}', xbmc.LOGERROR)
    return None


def wait_for_addon(addon_id, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            return True
        time.sleep(1)
    return False


def install_from_zip_path(zip_real_path):
    """
    Call Kodi InstallFromZip with a real path. Return True if called.
    """
    try:
        if os.path.exists(zip_real_path):
            xbmc.executebuiltin(f'InstallFromZip({zip_real_path})')
            return True
        log(f'install_from_zip_path: zip not found {zip_real_path}', xbmc.LOGWARNING)
    except Exception as e:
        log(f'install_from_zip_path error: {e}', xbmc.LOGERROR)
    return False


def refresh_addons():
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.executebuiltin('UpdateAddonRepos')
    time.sleep(2)


def unzip_direct_to_addons(zip_real_path):
    """
    Fallback: extract the zip directly to special://home/addons/
    (useful when InstallFromZip doesn't register the addon)
    """
    try:
        log(f'Fallback-extracting {zip_real_path} -> {ADDONS_DIR}')
        with zipfile.ZipFile(zip_real_path, 'r') as zf:
            # extract into a temporary folder then move to addons dir to avoid partial state
            tmp_extract_real = os.path.join(os.path.dirname(translate(ADDONS_DIR)), 'tmp_extract_service')
            if os.path.isdir(tmp_extract_real):
                shutil.rmtree(tmp_extract_real, ignore_errors=True)
            os.makedirs(tmp_extract_real, exist_ok=True)
            zf.extractall(tmp_extract_real)
            # move each top-level extracted folder into ADDONS_DIR
            addons_real = translate(ADDONS_DIR)
            for entry in os.listdir(tmp_extract_real):
                src = os.path.join(tmp_extract_real, entry)
                if os.path.isdir(src):
                    dst = os.path.join(addons_real, entry)
                    if os.path.exists(dst):
                        shutil.rmtree(dst, ignore_errors=True)
                    shutil.move(src, dst)
                    log(f'Moved extracted folder {entry} -> addons/{entry}')
            shutil.rmtree(tmp_extract_real, ignore_errors=True)
        refresh_addons()
        return True
    except Exception as e:
        log(f'unzip_direct_to_addons failed: {e}', xbmc.LOGERROR)
        return False


def fix_github_folder_prefix(expected_id):
    """
    GitHub zips often create folders with suffixes like '-master' or '-v1.2.3'.
    Rename any folder that startswith expected_id + '-' to exactly expected_id.
    Returns True if rename performed or expected_id is already present.
    """
    try:
        addons_real = translate(ADDONS_DIR)
        if not os.path.isdir(addons_real):
            return False
        # if already exists, nothing to do
        if os.path.isdir(os.path.join(addons_real, expected_id)):
            return True
        # find candidate
        for entry in os.listdir(addons_real):
            if entry.startswith(expected_id + '-') or entry.startswith(expected_id + '_') or entry.startswith(expected_id + '.'):
                src = os.path.join(addons_real, entry)
                dst = os.path.join(addons_real, expected_id)
                if os.path.exists(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                log(f'Renaming {entry} -> {expected_id}')
                os.rename(src, dst)
                refresh_addons()
                return True
        # also try entries that contain expected_id as prefix but with different punctuation
        for entry in os.listdir(addons_real):
            if expected_id in entry and entry != expected_id:
                src = os.path.join(addons_real, entry)
                dst = os.path.join(addons_real, expected_id)
                if os.path.isdir(src):
                    log(f'Also renaming {entry} -> {expected_id}')
                    if os.path.exists(dst):
                        shutil.rmtree(dst, ignore_errors=True)
                    os.rename(src, dst)
                    refresh_addons()
                    return True
        return False
    except Exception as e:
        log(f'fix_github_folder_prefix error: {e}', xbmc.LOGERROR)
        return False


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
    auramod_zip_special = os.path.join(TEMP_DIR, 'auramod.zip')
    auramod_zip_real = download(download_url, auramod_zip_special)
    if not auramod_zip_real:
        log('Failed to download AuraMOD zip.', xbmc.LOGERROR)
        return False

    # 1) try install via InstallFromZip
    install_from_zip_path(auramod_zip_real)
    time.sleep(1)
    refresh_addons()
    if wait_for_addon('skin.auramod', 30):
        log(f'AuraMOD updated successfully to {latest_version}!')
        xbmcvfs.delete(translate(auramod_zip_special))
        return True

    # 2) fallback: extract directly to addons folder + fix folder prefix
    log('InstallFromZip did not register skin.auramod; extracting directly as fallback.')
    if unzip_direct_to_addons(auramod_zip_real):
        fix_github_folder_prefix('skin.auramod')
        if wait_for_addon('skin.auramod', 20):
            log(f'AuraMOD updated successfully (fallback) to {latest_version}!')
            xbmcvfs.delete(translate(auramod_zip_special))
            return True

    log('Failed to install AuraMOD (both InstallFromZip and fallback).', xbmc.LOGERROR)
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
    netflix_zip_special = os.path.join(TEMP_DIR, 'plugin.video.netflix.zip')
    netflix_zip_real = download(download_url, netflix_zip_special)
    if not netflix_zip_real:
        log('Failed to download Netflix zip.', xbmc.LOGERROR)
        return False

    # 1) attempt InstallFromZip
    install_from_zip_path(netflix_zip_real)
    time.sleep(1)
    refresh_addons()
    if wait_for_addon('plugin.video.netflix', 30):
        xbmcvfs.delete(translate(netflix_zip_special))
        log(f'Netflix installed/updated to {latest_version}.')
        return True

    # 2) fallback_extract
    log('InstallFromZip did not register plugin.video.netflix; extracting directly as fallback.')
    if unzip_direct_to_addons(netflix_zip_real):
        fix_github_folder_prefix('plugin.video.netflix')
        if wait_for_addon('plugin.video.netflix', 20):
            xbmcvfs.delete(translate(netflix_zip_special))
            log(f'Netflix installed/updated (fallback) to {latest_version}.')
            return True

    log('Failed to install Netflix (both InstallFromZip and fallback).', xbmc.LOGERROR)
    return False


# ---------- Periodic updater ----------
def periodic_update_check():
    while True:
        try:
            log('Periodic check: AuraMOD update...')
            updated = auto_update_auramod()
            if updated:
                notify('AuraMOD updated! You may need to reload the skin.', 7000)
        except Exception as e:
            log(f'Error during periodic update: {e}', xbmc.LOGERROR)
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)


# ---------- Main setup ----------
def main_setup():
    log('Starting Cooler Auto Setup...')
    notify('Setting up your perfect TV build... (2 min)', 10000)

    # Enable unknown sources
    xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

    # Force refresh to see bundled addons (important)
    refresh_addons()

    # Install bundled addons first (from your repository)
    log('Installing bundled addons...')
    bundled = [
        'plugin.video.dstv.now',
        'samsung.tv.plus',
        'script.module.slyguy',
        'slyguy.dependencies',
        'script.module.inputstreamhelper',
        'script.module.addonsignals',
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
    auramod_changed = auto_update_auramod()

    # Switch to AuraMOD and configure widgets (only if present)
    if wait_for_addon('skin.auramod', 30):
        log('AuraMOD installed, loading skin...')
        notify('Switching to AuraMOD skin...', 5000)

        # Proper Kodi command to change skin
        xbmc.executebuiltin('LoadSkin("skin.auramod")')

        # Let the skin fully load
        xbmc.sleep(8000)

        xbmc.executebuiltin('ActivateWindow(Home)')
        xbmc.sleep(2000)

        # Set AuraMOD-specific flags/widgets
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows, true)')

        log('AuraMOD skin loaded and widgets configured.')
    else:
        log('AuraMOD not installed – cannot switch skin.', xbmc.LOGWARNING)

    # Enable PVR/EPG/Library
    xbmc.executebuiltin('PVR.SetSetting(epg, true)')
    xbmc.executebuiltin('PVR.SetSetting(channelmanager, true)')
    xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

    # Activate live addons for EPG only if installed
    for addon in ['samsung.tv.plus', 'pvr.plutotv']:
        if xbmc.getCondVisibility(f'System.HasAddon({addon})'):
            log(f'Running live addon: {addon}')
            xbmc.executebuiltin(f'RunAddon({addon})')
            time.sleep(3)
            xbmc.executebuiltin('ActivateWindow(Home)')
        else:
            log(f'Skipping live addon (not installed): {addon}')

    # Drop self-start files to userdata
    userdata = translate('special://profile/')
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

    try:
        with open(os.path.join(userdata, 'autoexec.py'), 'w', encoding='utf-8') as f:
            f.write(autoexec_content)
        with open(os.path.join(userdata, 'advancedsettings.xml'), 'w', encoding='utf-8') as f:
            f.write(advanced_content)
        log('Self-start files placed!')
    except Exception as e:
        log(f'Failed writing self-start files: {e}', xbmc.LOGERROR)

    # Clean temp files
    for f in ['plugin.video.netflix.zip', 'auramod.zip']:
        temp_file_special = os.path.join(TEMP_DIR, f)
        try:
            translated = translate(temp_file_special)
            if os.path.exists(translated) or xbmcvfs.exists(translated):
                xbmcvfs.delete(translated)
        except Exception:
            pass

    log('Cooler Build complete!')


def cleanup_service():
    addon_path = translate(f'special://home/addons/{ADDON_ID}')
    if os.path.exists(addon_path):
        shutil.rmtree(addon_path)
    xbmc.executebuiltin(f'UninstallAddon({ADDON_ID})')
    log('Service cleanup done!')


def run_service():
    main_setup()

    # Start periodic update checker in background
    updater_thread = threading.Thread(target=periodic_update_check, daemon=True)
    updater_thread.start()

    # Keep service alive
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        if monitor.waitForAbort(60):
            break


if __name__ == '__main__':
    run_service()
