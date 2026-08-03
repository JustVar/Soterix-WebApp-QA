import os
import sys
import zipfile


def zip_reports_folder(folder_path, zip_file_name):
    with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))


if __name__ == "__main__":
    # argv[0] is the script name; the actual arguments start at argv[1].
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} <folder_to_zip> <output_zip>")
        raise SystemExit(2)
    reports_folder = sys.argv[1]
    zip_file_name = sys.argv[2]
    print(f"Zip folder path is {reports_folder}")
    print(f"Zip file path is {zip_file_name}")
    zip_reports_folder(reports_folder, zip_file_name)