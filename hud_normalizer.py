#!/usr/bin/env python3
"""
TF2 HUD Cross Platform Updater

Converts TF2 HUDs to work on both Windows and Linux using explicit paths:
- Lowercases all filenames and folders
- Normalizes font path references in clientscheme files
- Converts resource paths to explicit ../../custom/hud_name/resource/ format
- Normalizes cfg paths to use correct depth based ../ counts

Based on my understanding after reviewing m0rehud.
"""

import sys
import re
from pathlib import Path


# files need (depth + 2) levels of ../ to reach tf/cfg/
CFG_DEPTH_OFFSET = 2


def extract_path_after_parents(path):
    # slighty tism way of stripping all leading '../' ('../../../cfg/file.txt' -> 'cfg/file.txt')
    while path.startswith('../'):
        path = path[3:]
    return path


def normalize_filenames(hud_dir):
    # recursively rename all files and folders to lowercase
    print("\nNormalizing filenames to lowercase...")

    # depth first to avoid conflicts
    all_paths = sorted(hud_dir.rglob('*'), key=lambda p: len(p.parts), reverse=True)
    rename_count = 0
    for item in all_paths:
        original_name = item.name
        lowercase_name = original_name.lower()
        if original_name != lowercase_name:
            target = item.parent / lowercase_name
            if not target.exists():
                item.rename(target)
                rename_count += 1

    if rename_count > 0:
        print(f"    Lowercased {rename_count} file(s)")
    else:
        print("    No files need to be lowercased")


def normalize_clientscheme_font_paths(file):
    # lowercase font file paths in a clientscheme file
    content = file.read_text(encoding='utf-8', errors='ignore')
    original = content
    content = re.sub(
        r'("font"\s+")(.*?)(")',
        lambda m: f'{m.group(1)}{m.group(2).replace("\\", "/").lower()}{m.group(3)}',
        content
    )
    if content != original:
        file.write_text(content, encoding='utf-8')
        return True
    return False


def process_clientscheme(file, visited, modified_count=0):
    # recursively process a clientscheme file and all its #base includes
    file = file.resolve()

    if file in visited or not file.exists():
        return modified_count

    visited.add(file)
    if normalize_clientscheme_font_paths(file):
        modified_count += 1

    content = file.read_text(encoding='utf-8', errors='ignore')
    base_pattern = re.compile(r'^#base\s+"([^"]+)"', re.MULTILINE)
    for match in base_pattern.finditer(content):
        base_path = match.group(1)
        included_file = (file.parent / base_path).resolve()
        modified_count = process_clientscheme(included_file, visited, modified_count)

    return modified_count


def normalize_clientschemes(hud_dir):
    # entry point for clientscheme normalization
    print("\nNormalizing font path references...")

    start_file = hud_dir / "resource" / "clientscheme.res"
    if not start_file.exists():
        print("    No clientscheme.res found")
        return

    visited = set()
    modified_count = process_clientscheme(start_file, visited)
    if modified_count > 0:
        print(f"    Modified {modified_count} clientscheme file(s)")
    else:
        print("    No clientscheme files need modification")


def normalize_cfg_echo_paths(content, hud_name):
    # normalize echo #base commands in .cfg files to use explicit paths
    def normalize_echo_path(match):
        prefix = match.group(1)# echo #base
        path = match.group(2) # the file path
        suffix = match.group(3) # rest of line
        path = path.replace('\\', '/')

        # normalize resource paths to explicit format
        if '/resource/' in path and f'/custom/{hud_name}/resource/' not in path:
            path = re.sub(r'(\.\./)+resource/', f'../../custom/{hud_name}/resource/', path)

        # normalize scripts paths to explicit format
        if '/scripts/' in path and f'/custom/{hud_name}/scripts/' not in path:
            path = re.sub(r'(\.\./)+scripts/', f'../../custom/{hud_name}/scripts/', path)

        path = path.lower()
        return f'{prefix}{path}{suffix}'

    return re.sub(
        r'(echo\s+["\']?#base["\']?\s+["\']?)(.*?\.(?:res|vmt))(["\']?.*)',
        normalize_echo_path,
        content,
        flags=re.IGNORECASE
    )


def normalize_cfg_paths_in_res(content, file_depth):
    # normalize #base paths to cfg files in .res files
    def normalize_cfg_path(match):
        prefix = match.group(1) # #base "
        path = match.group(2) # the file path
        suffix = match.group(3)# closing "
        path = path.replace('\\', '/')
        if '/cfg/' in path:
            current_ups = path.count('../')
            needed_ups = file_depth + CFG_DEPTH_OFFSET # need uppies :3 >w<

            # only normalize if depth is wrong
            if current_ups != needed_ups:
                path_after_ups = extract_path_after_parents(path)
                path = '../' * needed_ups + path_after_ups

        path = path.lower()
        return f'{prefix}{path}{suffix}'

    return re.sub(
        r'(#base\s+")(.*?cfg[^"]+)(")',
        normalize_cfg_path,
        content,
        flags=re.IGNORECASE
    )


def normalize_res_base_paths(content):
    # normalize #base directives pointing to .res files (but not cfg paths)
    def normalize_res_path(match):
        prefix = match.group(1) # #base "
        path = match.group(2) # the file path
        suffix = match.group(3)# closing "
        path = path.replace('\\', '/').lower()
        return f'{prefix}{path}{suffix}'

    return re.sub(
        r'(#base\s+")((?:(?!cfg)[^"])+\.res)(")',
        normalize_res_path,
        content,
        flags=re.IGNORECASE
    )


def normalize_schema_declarations(content):
    # normalize schema declarations
    def normalize_schema(match):
        quote = match.group(1)
        path = match.group(2)
        path = path.replace('\\', '/').lower()
        return f'{quote}{path}'

    return re.sub(
        r'(")((?:resource|scripts)[/\\][^"]+)',
        normalize_schema,
        content,
        flags=re.IGNORECASE
    )


def process_cfg_files(hud_dir, hud_name):
    # process .cfg files to normalize echo #base paths
    cfg_folder = hud_dir / "cfg"
    if not cfg_folder.exists():
        print("    No cfg folder found")
        return

    cfg_files = list(cfg_folder.rglob("*.cfg"))
    modified_count = 0
    for file in cfg_files:
        content = file.read_text(encoding='utf-8', errors='ignore')
        original = content
        content = normalize_cfg_echo_paths(content, hud_name)
        if content != original:
            modified_count += 1
            file.write_text(content, encoding='utf-8')

    if modified_count > 0:
        print(f"    Modified {modified_count} .cfg file(s)")
    else:
        print("    No .cfg files need modification")


def process_res_files(hud_dir):
    # rocess .res files to normalize #base paths and references
    res_files = list(hud_dir.rglob("*.res"))
    modified_count = 0
    for file in res_files:
        content = file.read_text(encoding='utf-8', errors='ignore')
        original = content

        # calculate file dept
        try:
            relative_path = file.relative_to(hud_dir)
            file_depth = len(relative_path.parts) - 1  # subtract the file itself
        except ValueError:
            file_depth = 0

        # apply all normalizations
        content = normalize_cfg_paths_in_res(content, file_depth)
        content = normalize_res_base_paths(content)
        content = normalize_schema_declarations(content)

        if content != original:
            modified_count += 1
            file.write_text(content, encoding='utf-8')

    if modified_count > 0:
        print(f"    Modified {modified_count} .res file(s)")
    else:
        print("    No .res files need modification")


def normalize_logbase_paths(hud_dir):
    # normalize all logbase paths to use explicit paths
    print("\nNormalizing logbase paths...")

    hud_name = hud_dir.name
    process_cfg_files(hud_dir, hud_name)
    process_res_files(hud_dir)


def main():
    if len(sys.argv) < 2:
        print("Usage: hud_normalizer.py <HUD_FOLDER>")
        print("\nConverts TF2 HUDs to work cross-platform (Windows + Linux)")
        sys.exit(1)

    hud_folder_name = sys.argv[1]
    hud_path = Path(hud_folder_name)

    if not hud_path.exists():
        print(f"Error: Folder '{hud_folder_name}' not found")
        sys.exit(1)

    if not hud_path.is_dir():
        print(f"Error: '{hud_folder_name}' is not a directory")
        sys.exit(1)

    print(f"Target HUD -> {hud_folder_name}")

    # lowercase the HUD folder name itself
    lower_folder_name = hud_folder_name.lower()
    if hud_folder_name != lower_folder_name:
        print(f"Renaming HUD folder: {hud_folder_name} -> {lower_folder_name}")
        lower_hud_path = Path(lower_folder_name)
        hud_path.rename(lower_hud_path)
        hud_path = lower_hud_path

    # run all normalization operations
    hud_path = hud_path.resolve()
    normalize_filenames(hud_path)
    normalize_clientschemes(hud_path)
    normalize_logbase_paths(hud_path)

    print("\nConversion Complete!")
    print(f"HUD ready for cross-platform use: {hud_path}\n")


if __name__ == "__main__":
    main()
