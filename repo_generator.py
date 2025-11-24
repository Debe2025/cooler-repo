import os
import hashlib
import re

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = BASE_DIR                      # generates in root (perfect)
ADDONS_ROOT = BASE_DIR                     # now scans the ROOT for addon folders!
# --- End Configuration ---

def create_addons_xml():
    print("--- Generating addons.xml & addons.xml.md5 (scans ROOT) ---")
    addons_xml_content = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    addons_processed = 0

    for item in os.listdir(ADDONS_ROOT):
        item_path = os.path.join(ADDONS_ROOT, item)

        # Skip files and unwanted folders
        if not os.path.isdir(item_path):
            continue
        if item.startswith(('.', 'repo')) or item == 'addons':   # skip old junk
            continue

        addon_xml_path = os.path.join(item_path, 'addon.xml')
        if os.path.exists(addon_xml_path):
            print(f"  → Adding: {item}")
            try:
                with open(addon_xml_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                clean = re.sub(r'<\?xml.*?\?>', '', data, flags=re.DOTALL).strip()
                addons_xml_content += f"{clean}\n\n"
                addons_processed += 1
            except Exception as e:
                print(f"    Failed {item}: {e}")

    if addons_processed == 0:
        print("No addon folders found! Check structure.")
        return

    addons_xml_content += '</addons>\n'

    # Write to root
    xml_path = os.path.join(OUTPUT_DIR, 'addons.xml')
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(addons_xml_content)
    print(f"addons.xml created → {addons_processed} addons")

    generate_md5(xml_path)

def generate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    md5_path = file_path + '.md5'
    with open(md5_path, 'w', encoding='utf-8') as f:
        f.write(hash_md5.hexdigest())
    print(f"addons.xml.md5 created → {hash_md5.hexdigest()}")

if __name__ == '__main__':
    create_addons_xml()
    print("\nDone! Your repo now includes service.cooler.autosetup automatically.")