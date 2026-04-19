import glob

# Path where your generated .rst files live
rst_path = "source/src/*.rst"

for filename in glob.glob(rst_path):
    with open(filename, "r") as f:
        print(f"Cleaning {filename}.")
        lines = f.readlines()

    if lines:
        # Strip the 'planar_map.' prefix (both escaped and normal) and
        # ' module' suffix
        lines[0] = (
            lines[0]
            .replace("planar_map.", "")
            # Catches Sphinx's escaped underscores
            .replace("planar\\_map.", "")
            .replace(" module", "")
        )

        # Adjust the underline (===) to match the new shorter title length
        # (Sphinx requires the underline to be at least as long as the text)
        lines[1] = "=" * (len(lines[0].strip())) + "\n"

        with open(filename, "w") as f:
            f.writelines(lines)
