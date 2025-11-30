#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hardened service.cooler.autosetup
- Installs AuraMOD and Netflix safely
- Skips AddonSignals until Netflix is installed
- Switches skin after installation instead of restarting Kodi
"""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import os
import time
import json
import shutil
import threading
import urllib.request
import urllib.error
import zipfile

ADDON_ID = 'service.cooler.autosetup'
TEMP_DIR = xbmcvfs.translatePath('special://temp/')
ADDONS_DIR = xbmcvfs.translatePath('special://home/addons/')
UPDATE_INTERVAL_HOURS = 6

AURAMOD_GITHUB_API = 'https://api.github.com/repos/SerpentDrago/skin.auramod/releases/latest'
NETFLIX_GITHUB_API = 'https://api.github.com/repos/CastagnaIT/plugin.video.netflix/releases/latest'

restart_required = False

# ---------- Logging & notifications ----------
def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level=level)

def notify(msg, time_ms=5000):
    xbmc.executebuiltin(f"Notification(Cooler Build, {msg}, {time_ms})")

# ---------- Utility ----------
def translate(p):
    return xbmcvfs.translatePath(p)

def download(url, local_special_path):
    try:
        local_real = translate(local_special_path)
        os.makedirs(os.path.dirname(local_real), exist_ok=True)
        log(f"Downloading {url} -> {local_real}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(local_real, 'wb') as f:
                shutil.copyfileobj(resp, f)
        log("Download complete")
        return local_real
    except Exception as e:
        log(f"Download failed: {e}", xbmc.LOGERROR)
        return None

def wait_for_addon(addon_id, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        if xbmc.getCondVisibility(f"System.HasAddon({addon_id})"):
            return True
        time.sleep(1)
    return False

def refresh_addons():
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.executebuiltin('UpdateAddonRepos')
    time.sleep(2)

def install_from_zip(zip_real_path):
    if os.path.exists(zip_real_path):
        xbmc.executebuiltin(f"InstallFromZip({zip_real_path})")
        return True
    log(f"Zip not found: {zip_real_path}", xbmc.LOGWARNING)
    return False

def unzip_direct_to_addons(zip_real_path):
    try:
        log(f"Fallback extract {zip_real_path} -> {ADDONS_DIR}")
        with zipfile.ZipFile(zip_real_path, 'r') as zf:
            tmp_extract = os.path.join(TEMP_DIR.replace('special://', ''), 'extract_tmp')
            os.makedirs(tmp_extract, exist_ok=True)
            zf.extractall(tmp_extract)
            for entry in os.listdir(tmp_extract):
                src = os.path.join(tmp_extract, entry)
                dst = os.path.join(translate(ADDONS_DIR), entry)
                if os.path.exists(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.move(src, dst)
            shutil.rmtree(tmp_extract, ignore_errors=True)
        refresh_addons()
        return True
    except Exception as e:
        log(f"Fallback unzip failed: {e}", xbmc.LOGERROR)
        return False

def fix_github_folder_prefix(expected_id):
    try:
        addons_real = translate(ADDONS_DIR)
        if os.path.isdir(os.path.join(addons_real, expected_id)):
            return True
        for entry in os.listdir(addons_real):
            if entry.startswith(expected_id + '-') or entry.startswith(expected_id + '_'):
                src = os.path.join(addons_real, entry)
                dst = os.path.join(addons_real, expected_id)
                if os.path.exists(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                os.rename(src, dst)
                refresh_addons()
                return True
        return False
    except Exception as e:
        log(f"fix_github_folder_prefix error: {e}", xbmc.LOGERROR)
        return False

# ---------- AuraMOD ----------
def get_latest_auramod_release():
    try:
        with urllib.request.urlopen(AURAMOD_GITHUB_API) as resp:
            data = json.load(resp)
            tag = data.get('tag_name')
            url = next((a.get('browser_download_url') for a in data.get('assets', []) if a.get('name','').endswith('.zip')), None)
            if not url and tag:
                url = f"https://github.com/SerpentDrago/skin.auramod/archive/refs/tags/{tag}.zip"
            return tag, url
    except Exception as e:
        log(f"AuraMOD fetch error: {e}", xbmc.LOGERROR)
        return None, None

def get_installed_auramod_version():
    try:
        addon = xbmcaddon.Addon('skin.auramod')
        return addon.getAddonInfo('version')
    except Exception:
        return None

def auto_update_auramod():
    global restart_required
    latest_version, url = get_latest_auramod_release()
    installed = get_installed_auramod_version()
    if not url or installed == latest_version:
        return False
    notify(f"Installing AuraMOD {latest_version}...", 5000)
    zip_special = os.path.join(TEMP_DIR, "auramod.zip")
    zip_real = download(url, zip_special)
    if not zip_real:
        return False
    install_from_zip(zip_real)
    time.sleep(2)
    refresh_addons()
    if wait_for_addon('skin.auramod', 20):
        xbmcvfs.delete(translate(zip_special))
        restart_required = True
        return True
    # fallback
    if unzip_direct_to_addons(zip_real):
        fix_github_folder_prefix('skin.auramod')
        if wait_for_addon('skin.auramod', 20):
            xbmcvfs.delete(translate(zip_special))
            restart_required = True
            return True
    return False

# ---------- Netflix ----------
def get_latest_netflix_release():
    try:
        with urllib.request.urlopen(NETFLIX_GITHUB_API) as resp:
            data = json.load(resp)
            tag = data.get('tag_name')
            url = next((a.get('browser_download_url') for a in data.get('assets', []) if a.get('name','').endswith('.zip')), None)
            return tag, url
    except Exception as e:
        log(f"Netflix fetch error: {e}", xbmc.LOGERROR)
        return None, None

def get_installed_netflix_version():
    try:
        addon = xbmcaddon.Addon('plugin.video.netflix')
        return addon.getAddonInfo('version')
    except Exception:
        return None

def install_or_update_netflix():
    tag, url = get_latest_netflix_release()
    installed = get_installed_netflix_version()
    if not url or installed == tag:
        return False
    notify(f"Installing Netflix {tag}...", 5000)
    zip_special = os.path.join(TEMP_DIR, "plugin.video.netflix.zip")
    zip_real = download(url, zip_special)
    if not zip_real:
        return False
    install_from_zip(zip_real)
    time.sleep(2)
    refresh_addons()
    if wait_for_addon('plugin.video.netflix', 30):
        xbmcvfs.delete(translate(zip_special))
        return True
    # fallback
    if unzip_direct_to_addons(zip_real):
        fix_github_folder_prefix('plugin.video.netflix')
        if wait_for_addon('plugin.video.netflix', 20):
            xbmcvfs.delete(translate(zip_special))
            return True
    return False

# ---------- Main Setup ----------
def main_setup():
    log("Starting Cooler Auto Setup...")
    notify("Setting up your TV build...", 10000)

    # Enable unknown sources
    xbmc.executebuiltin("SetSetting(addons.unknownsources, true)")
    refresh_addons()

    # Install bundled addons
    for addon in [
        'plugin.video.dstv.now',
        'samsung.tv.plus',
        'script.module.slyguy',
        'slyguy.dependencies',
        'script.module.inputstreamhelper',
    ]:
        xbmc.executebuiltin(f"InstallFromRepository(repository.myrepo, {addon})")
        wait_for_addon(addon, 20)

    # Install Netflix safely
    install_or_update_netflix()

    # Install AuraMOD
    auto_update_auramod()

    # Switch to AuraMOD skin if installed
    if wait_for_addon('skin.auramod', 20):
        xbmc.executebuiltin('Skin.SetString(Skin.Current, skin.auramod)')
        time.sleep(5)
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetLiveTV, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetMovies, true)')
        xbmc.executebuiltin('Skin.SetBool(HomeWidgetTVShows, true)')

def run_service():
    main_setup()
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        monitor.waitForAbort(60)

if __name__ == "__main__":
    run_service()
