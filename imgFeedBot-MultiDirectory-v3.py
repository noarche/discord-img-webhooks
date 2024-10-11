import os
import time
import requests
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Supported image extensions
image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".webm"]

# Global counters for statistics
files_sent = 0
bandwidth_used = 0

# Load config from config.txt
def load_config(config_file="config.txt"):
    directories_to_watch = {}
    if not os.path.exists(config_file):
        print(Fore.RED + "Config file not found!")
        return directories_to_watch

    with open(config_file, 'r') as file:
        for line in file:
            if not line.strip() or line.startswith('#'):
                continue
            try:
                directory, webhook_url = line.split(',', 1)  # Use comma as separator
                directories_to_watch[directory.strip()] = webhook_url.strip()
            except ValueError:
                print(Fore.RED + f"Invalid line in config: {line.strip()}")
    return directories_to_watch

class ImageHandler(FileSystemEventHandler):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url
        self.processed_files = set()

    def on_created(self, event):
        global files_sent, bandwidth_used
        if not event.is_directory and os.path.splitext(event.src_path)[1].lower() in image_extensions:
            time.sleep(8)  # Ensure the file is completely written

            if event.src_path not in self.processed_files:
                self.processed_files.add(event.src_path)
                file_size = os.path.getsize(event.src_path)
                if self.send_image(event.src_path):
                    files_sent += 1
                    bandwidth_used += file_size

    def send_image(self, image_path):
        with open(image_path, "rb") as image_file:
            files = {"file": image_file}
            data = {"content": f"{os.path.basename(image_path)}"}

            try:
                response = requests.post(self.webhook_url, files=files, data=data)

                # Treat both 200 and 204 status codes as successful responses
                if response.status_code in [200, 204]:
                    print(Fore.GREEN + f"Image '{os.path.basename(image_path)}' sent successfully!")
                    return True
                else:
                    print(Fore.RED + f"Failed to send image '{os.path.basename(image_path)}'. Status code: {response.status_code}")
                    print(Fore.RED + f"Response: {response.text}")
                    return False
            except Exception as e:
                print(Fore.RED + f"Error sending image '{os.path.basename(image_path)}': {str(e)}")
                return False

def print_summary(directories, files_sent, bandwidth_used):
    sys.stdout.write('\r')  # Return to the start of the line
    summary = (
        f"{Fore.CYAN}Summary: "
        f"{Fore.YELLOW}Directories watched: {len(directories)} | "
        f"Files sent: {files_sent} | "
        f"Bandwidth used: {bandwidth_used / (1024 * 1024):.2f} MB"
    )
    sys.stdout.write(summary)
    sys.stdout.flush()

if __name__ == "__main__":
    config_file = "config.txt"
    directories_to_watch = load_config(config_file)

    if not directories_to_watch:
        print(Fore.RED + "No directories to watch. Please check your config file.")
        exit(1)

    observers = []
    
    print(Fore.CYAN + f"Starting to watch {len(directories_to_watch)} directories...\n")

    for directory, webhook_url in directories_to_watch.items():
        if not os.path.exists(directory):
            print(Fore.RED + f"Directory {directory} does not exist, skipping...")
            continue

        event_handler = ImageHandler(webhook_url)
        observer = Observer()
        observer.schedule(event_handler, path=directory, recursive=False)
        observer.start()
        observers.append(observer)

    try:
        while True:
            time.sleep(5)  # Poll every 5 seconds
            print_summary(directories_to_watch, files_sent, bandwidth_used)
    except KeyboardInterrupt:
        for observer in observers:
            observer.stop()

    for observer in observers:
        observer.join()
