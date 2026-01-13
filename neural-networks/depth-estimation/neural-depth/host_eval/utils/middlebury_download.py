import os
import requests
import zipfile
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def download_and_process_zips(target_url, download_root_folder, calibration=None, max_scenes=None):
    try:
        response = requests.get(target_url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].endswith('.zip')]

    if not links:
        print("No zip files found on the page.")
        return

    if calibration:
        filtered_links = []
        for link in links:
            if 'imperfect.zip' in link and 'imperfect' in calibration:
                filtered_links.append(link)
            elif 'perfect.zip' in link and 'perfect' in calibration:
                filtered_links.append(link)
        links = filtered_links

    if max_scenes:
        links = links[:max_scenes]

    print(f"Found {len(links)} zip files to download. Starting process...\n")

    for link in links:
        filename = os.path.basename(link)
        full_url = urljoin(target_url, link)

        if 'imperfect.zip' in filename:
            subfolder = 'imperfect'
        elif 'perfect.zip' in filename:
            subfolder = 'perfect'
        else:
            subfolder = 'others'

        target_dir = os.path.join(download_root_folder, subfolder)
        os.makedirs(target_dir, exist_ok=True)

        local_zip_path = os.path.join(target_dir, filename)

        try:
            with requests.get(full_url, stream=True) as r:
                r.raise_for_status()
                with open(local_zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            print(f"    Extracting...")
            with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)

            print(f"    Deleting zip file...")
            os.remove(local_zip_path)

        except Exception as e:
            print(f"    Error processing {filename}: {e}")

    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--calibration', nargs='+', choices=['perfect', 'imperfect'], default=['perfect', 'imperfect'])
    parser.add_argument('--max_scenes', type=int, default=None)
    parser.add_argument('--output', type=str, default='../data')
    args = parser.parse_args()

    URL = "https://vision.middlebury.edu/stereo/data/scenes2014/zip/"

    download_and_process_zips(URL, args.output, calibration=args.calibration, max_scenes=args.max_scenes)