import shutil
from pathlib import Path

from fuzzywuzzy import fuzz, process

# Install fuzzywuzzy and python-Levenshtein for better performance:
# pip install fuzzywuzzy[accelerated]

# Define paths
source_dir = Path(__file__).parents[1] / "assets/static/media/thank_you_banners"
dest_base_dir = Path(__file__).parents[1] / "content/sponsors/"

# Load PNG filenames (remove extension and lowercase for matching)
png_names = [x for x in source_dir.glob("*") if x.is_file()]

# Load sponsor directories
sponsor_dirs = [x.name for x in dest_base_dir.glob("*") if x.is_dir()]

# Go through each PNG file and match to a sponsor directory
matched_files = []
clean_names = [x.stem.lower() for x in png_names]
for f in sponsor_dirs:
    best_match, score = process.extractOne(f, clean_names, scorer=fuzz.token_sort_ratio)

    if best_match and score >= 40:
        source_file = source_dir / f"{best_match}.png"
        dest_dir = dest_base_dir / f
        dest_file = dest_dir / "social_card.png"

        if dest_file.exists():
            print(
                f"⚠️ File already exists: {dest_file} -  will not replace existing files"
            )
            continue

        if source_file.exists():
            shutil.copyfile(source_file, dest_file)
            print(
                f"✅ Copied '{source_file.name}' → '{dest_file}' (match: {best_match}, score: {score})"
            )
            matched_files.append((f, best_match, score))
        else:
            print(f"⚠️ File not found: {source_file}")
    else:
        print(f"❌ No suitable match for '{f}' (best: '{best_match}', score: {score})")

for l in matched_files:
    print(l)
