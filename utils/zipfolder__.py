import zipfile
import os

def zip_reports_folder(folder_path, zip_file_name):
    with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
                
if __name__ == "__main__":
    reports_folder = sys.argv[0]
    zip_file_name = sys.argv[1]
    print(f"Zip folder path is {sys.argv[0]}")
    print(f"Zip file path is {sys.argv[1]}")
    zip_reports_folder(reports_folder, zip_file_name)