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

# Track if an AuraMOD update happened during setup (to auto-restart once)
restart_required = False


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[{ADDON_ID}]: {msg}', level=level)


def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f'Notification(Cooler Build, {msg}, {time_ms})')


def download(url, local_path):
    try:
        target = xbmcvfs.translatePath(local_path)
        log(f'Downloading {url} -> {target}')
        urllib.request.urlretrieve(url, target)
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
    # zip_path should be a full local path
    if os.path.exists(zip_path):
        xbmc.executebuiltin(f'InstallFromZip({zip_path})')
        return True
    log(f'ZIP does not exist: {zip_path}', xbmc.LOGWARNING)
    return False


# ────── AuraMOD helpers ──────
def get_latest_auramod_release():
    """
    Fetch latest AuraMOD release from GitHub.
    Tries asset ZIP first; if none, builds a tag-based ZIP URL:
    https://github.com/SerpentDrago/skin.auramod/archive/refs/tags/{tag}.zip
    """
    try:
        with urllib.request.urlopen(AURAMOD_GITHUB_API) as response:
            data = json.load(response)
            tag = data.get('tag_name')  # e.g. 'v2.0.4'
            download_url = None

            # 1) Check release assets for a .zip
            for asset in data.get('assets', []):
                name = asset.get('name', '')
                if name.endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    break

            # 2) Fallback to tag-based source ZIP if no assets
            if not download_url and tag:
                download_url = f'https://github.com/SerpentDrago/skin.auramod/archive/refs/tags/{tag}.zip'

            log(f'Latest AuraMOD tag: {tag}, url: {download_url}')
            return tag, download_url
    except Exception as e:
        log(f'AuraMOD API failed: {e}', xbmc.LOGERROR)
        return None, None


def get_installed_auramod_version():
    try:
        return xbmcaddon.Addon('skin.auramod').getAddonInfo('version')
    except Exception:
        return None


def auto_update_auramod():
    """
    Install or update AuraMOD to the latest GitHub release.
    Returns True if an update/install happened.
    """
    global restart_required

    latest_tag, download_url = get_latest_auramod_release()
    current = get_installed_auramod_version()

    log(f'AuraMOD installed: {current}, latest: {latest_tag}')

    # If we couldn't get a valid latest or no download URL, bail
    if not latest_tag or not download_url:
        log('Could not get latest AuraMOD release, skipping update...', xbmc.LOGWARNING)
        return False

    # If same version, nothing to do
    if current == latest_tag:
        log('AuraMOD is already up-to-date.')
        return False

    # Otherwise, install/update
    notify(f'Installing/Updating AuraMOD to {latest_tag}...', 6000)
    auramod_zip = os.path.join(TEMP_DIR, 'auramod.zip')

    if download(download_url, auramod_zip) and install_zip(auramod_zip):
        log(f'AuraMOD updated successfully to {latest_tag}!')
        try:
            if xbmcvfs.exists(auramod_zip):
                xbmcvfs.delete(auramod_zip)
        except Exception:
            pass
        restart_required = True
        return True

    log('Failed to install AuraMOD from ZIP.', xbmc.LOGERROR)
    return False


# ────── Netflix helpers ──────
def install_or_update_netflix():
    """
    Installs/updates Netflix from its GitHub release ZIP.
    """
    try:
        with urllib.request.urlopen(NETFLIX_GITHUB_API) as r:
            data = json.load(r)
            tag = data.get('tag_name')
            zip_url = next(
                (a['browser_download_url'] for a in data.get('assets', [])
                 if a.get('name', '').endswith('.zip')),
                None
            )

            if not tag or not zip_url:
                raise Exception('No ZIP found in Netflix release')

            log(f'Latest Netflix tag: {tag}, url: {zip_url}')
    except Exception as e:
        log(f'Netflix API failed: {e}', xbmc.LOGERROR)
        notify('Netflix GitHub API failed. Install Netflix manually from releases.', 8000)
        return False

    # Get currently installed version (if any)
    current = None
    try:
        current = xbmcaddon.Addon('plugin.video.netflix').getAddonInfo('version')
    except Exception:
        pass

    if current == tag:
        log('Netflix is already up-to-date.')
        return False

    notify(f'Installing/Updating Netflix to {tag}...', 6000)
    netflix_zip = os.path.join(TEMP_DIR, 'plugin.video.netflix.zip')

    if download(zip_url, netflix_zip) and install_zip(netflix_zip):
        wait_for_addon('plugin.video.netflix', 30)
        try:
            if xbmcvfs.exists(netflix_zip):
                xbmcvfs.delete(netflix_zip)
        except Exception:
            pass
        log('Netflix install/update complete.')
        return True

    log('Failed to install/update Netflix from ZIP.', xbmc.LOGERROR)
    return False


# ────── Periodic updater ──────
def periodic_update_check():
    """
    Background thread: periodically checks for AuraMOD updates (no auto-restart here).
    User can restart manually when they want.
    """
    while True:
        try:
            log('Periodic check: AuraMOD update...')
            updated = auto_update_auramod()
            if updated:
                notify('AuraMOD updated! Restart Kodi to apply changes.', 7000)
        except Exception as e:
            log(f'Error during periodic AuraMOD update: {e}', xbmc.LOGERROR)
        time.sleep(UPDATE_INTERVAL_HOURS * 3600)


# ────── Main setup ──────
def main_setup():
    log('Starting Cooler Auto Setup...')
    notify('Setting up your perfect TV build... (2–3 min)', 10000)

    # Enable unknown sources
    xbmc.executebuiltin('SetSetting(addons.unknownsources, true)')

    # 1. Install bundled addons from your repo FIRST
    # These should all exist in repository.myrepo
    bundled = [
        'plugin.video.dstv.now',
        'samsung.tv.plus',
        'script.module.slyguy',
        'slyguy.dependencies',
        'script.module.inputstreamhelper'
    ]
    for addon_id in bundled:
        try:
            log(f'Installing bundled addon from repository.myrepo: {addon_id}')
            xbmc.executebuiltin(f'InstallFromRepository(repository.myrepo, {addon_id})')
            if not wait_for_addon(addon_id, 15):
                log(f'Bundled addon did not install or not found: {addon_id}', xbmc.LOGWARNING)
        except Exception as e:
            log(f'Error installing bundled addon {addon_id}: {e}', xbmc.LOGERROR)

    # 2. Install/update Netflix from GitHub
    install_or_update_netflix()

    # 3. Official addons from Kodi repo
    official_addons = [
        'plugin.video.youtube',
        'plugin.video.tubi',
        'plugin.video.crackle',
        'pvr.plutotv',
        'plugin.video.popcornflix',
        'plugin.video.internetarchive'
    ]
    for addon_id in official_addons:
        try:
            log(f'Installing official addon: {addon_id}')
            xbmc.executebuiltin(f'InstallAddon({addon_id})')
            wait_for_addon(addon_id, 10)
        except Exception as e:
            log(f'Error installing official addon {addon_id}: {e}', xbmc.LOGERROR)

    # 4. AuraMOD (initial install / update)
    auto_update_auramod()

    # 5. Switch to AuraMOD and configure basic widgets
    if wait_for_addon('skin.auramod', 20):
        log('Switching to AuraMOD skin...')
        xbmc.executebuiltin('ActivateWindow(Home)')
        time.sleep(5)
        xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
        time.sleep(8)
        for setting in ['HomeWidgetLiveTV', 'HomeWidgetMovies', 'HomeWidgetTVShows']:
            xbmc.executebuiltin(f'Skin.SetBool({setting}, true)')
    else:
        log('AuraMOD not installed – cannot switch skin.', xbmc.LOGWARNING)

    # 6. PVR / EPG / library
    xbmc.executebuiltin('PVR.SetSetting(epg, true)')
    xbmc.executebuiltin('SetSetting(videolibrary.updateonstartup, true)')

    # 7. Activate live addons for EPG (only if installed)
    for addon_id in ['samsung.tv.plus', 'pvr.plutotv']:
        if xbmc.getCondVisibility(f'System.HasAddon({addon_id})'):
            log(f'Running live addon: {addon_id}')
            xbmc.executebuiltin(f'RunAddon({addon_id})')
            time.sleep(3)
        else:
            log(f'Skipping live addon (not installed): {addon_id}')

    # 8. Self-start: boot straight to TV Channels
    userdata = xbmcvfs.translatePath('special://profile/')
    try:
        autoexec_path = os.path.join(userdata, 'autoexec.py')
        with open(autoexec_path, 'w', encoding='utf-8') as f:
            f.write(
                'import xbmc, time\n'
                'time.sleep(10)\n'
                'xbmc.executebuiltin("ActivateWindow(TVChannels)")\n'
            )

        advanced_path = os.path.join(userdata, 'advancedsettings.xml')
        with open(advanced_path, 'w', encoding='utf-8') as f:
            f.write(
                '<advancedsettings>'
                '<lookandfeel><startupwindow>tvchannels</startupwindow></lookandfeel>'
                '<epg><epgupdate>5</epgupdate></epg>'
                '<video><libraryautoupdate>true</libraryautoupdate></video>'
                '</advancedsettings>'
            )
        log('Self-start files placed!')
    except Exception as e:
        log(f'Failed to write self-start files: {e}', xbmc.LOGERROR)

    log('Cooler Build complete!')


# ────── Service runner ──────
def run_service():
    global restart_required

    main_setup()

    # Start periodic AuraMOD updater
    threading.Thread(target=periodic_update_check, daemon=True).start()

    # If AuraMOD was installed/updated during setup, restart once
    if restart_required:
        notify('Restarting Kodi to apply AuraMOD update...', 5000)
        time.sleep(4)
        xbmc.executebuiltin('RestartApp')

    # Keep service alive (periodic thread will run as daemon)
    while True:
        time.sleep(60)


if __name__ == '__main__':
    run_service()
