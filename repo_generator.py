import os
import hashlib
import re

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'repo')

# Define the directories to scan for add-ons (including 'addons' folder)
# The script will scan the root (BASE_DIR) and the 'addons' sub-directory.
SCAN_DIRS = [BASE_DIR, os.path.join(BASE_DIR, 'addons')]
# --- End Configuration ---

def create_addons_xml():
    """
    Scans the defined directories for add-on folders, reads their addon.xml,
    and generates the main addons.xml file.
    """
    print("--- Starting Repository Index Generation ---")
    
    addons_xml_content = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'
    addons_processed = 0

    # 1. Iterate through all defined scanning directories
    for scan_dir in SCAN_DIRS:
        if not os.path.exists(scan_dir):
            continue

        # 2. Iterate through all items in the current scanning directory
        for item in os.listdir(scan_dir):
            item_path = os.path.join(scan_dir, item)
            
            # Check if the item is a directory and not the output/hidden directories
            if os.path.isdir(item_path) and item not in ('repo', 'addons') and not item.startswith('.'):
                addon_xml_path = os.path.join(item_path, 'addon.xml')
                
                # Check if addon.xml exists in the folder
                if os.path.exists(addon_xml_path):
                    print(f"Processing add-on: {item}")
                    try:
                        with open(addon_xml_path, 'r', encoding='utf-8') as f:
                            addon_xml_data = f.read()
                            
                        # Remove the XML header and clean up
                        clean_data = re.sub(r'<\?xml.*?\?>', '', addon_xml_data, flags=re.DOTALL)
                        clean_data = clean_data.strip()
                        
                        addons_xml_content += f'{clean_data}\n'
                        addons_processed += 1
                        
                    except Exception as e:
                        print(f"Error reading addon.xml for {item}: {e}")
    
    # 3. Finalize and write the output files
    if addons_processed == 0:
        print("\n⚠️ Warning: No add-on folders with an addon.xml file were found. Check your directory structure.")
        return

    addons_xml_content += '</addons>\n'
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    output_xml_path = os.path.join(OUTPUT_DIR, 'addons.xml')
    try:
        with open(output_xml_path, 'w', encoding='utf-8') as f:
            f.write(addons_xml_content)
        print(f"\nSuccessfully created addons.xml at: {output_xml_path}")
        
        generate_md5(output_xml_path)
        
    except Exception as e:
        print(f"Error writing output files: {e}")

def generate_md5(file_path):
    """Generates an MD5 checksum for a given file and writes it to a new file."""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        md5_hash = hashlib.md5(data).hexdigest()
        
        md5_path = f"{file_path}.md5"
        with open(md5_path, 'w', encoding='utf-8') as f:
            f.write(md5_hash)
            
        print(f"Successfully created addons.xml.md5 at: {md5_path}")
        
    except Exception as e:
        print(f"Error generating MD5 checksum: {e}")

if __name__ == '__main__':
    create_addons_xml()
