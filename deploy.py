import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

# === ANSI COLORS ===
YELLOW = "\033[38;5;220m"
RESET = "\033[0m"
BOLD = "\033[1m"

def run(cmd, cwd=None, silent=False):
    try:
        if silent:
            return subprocess.check_output(cmd, cwd=cwd, shell=True, text=True)
        else:
            subprocess.check_call(cmd, cwd=cwd, shell=True)
            return ""
    except subprocess.CalledProcessError as e:
        print(f"{YELLOW}Command failed:{RESET}", cmd)
        raise e

temp_dir = Path(__file__).parent / "git-temp"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIT_EMAIL = os.getenv("GIT_EMAIL")
GIT_USERNAME = os.getenv("GIT_USERNAME")
GIT_BRANCH = os.getenv("GIT_BRANCH")
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN")
CLOUDFLARE_TOKEN = os.getenv("CLOUDFLARE_TOKEN")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
DOMAIN = os.getenv("DOMAIN")
COMMIT_MESSAGE = os.getenv("COMMIT_MESSAGE", "Auto Commit")

# === YELLOW ASCII ART ===
print(YELLOW + r"""
______  ___                  ______        ______         
___   |/  /_____________________  / ______ ___  /_________
__  /|_/ /_  __ \  __ \_  __ \_  /  _  __ `/_  __ \_  ___/
_  /  / / / /_/ / /_/ /  / / /  /___/ /_/ /_  /_/ /(__  ) 
/_/  /_/  \____/\____//_/ /_//_____/\__,_/ /_.___//____/
                                  Github: Yudzx-xnxx
""" + RESET)

print(BOLD + YELLOW + "=== Auto GitHub + Vercel + Cloudflare Deploy ===\n" + RESET)

print(YELLOW + "[1]" + RESET + " Add/Update files to repo")
print(YELLOW + "[2]" + RESET + " Delete all files in repo\n")

choice = input(YELLOW + "Select action (1/2): " + RESET).strip()
if choice not in ["1", "2"]:
    print("Invalid choice.")
    exit()

repo_url = input(YELLOW + "Enter the repository URL: " + RESET).strip()

print(YELLOW + "Setting up global Git configuration..." + RESET)
run('git config --global --add safe.directory "*"')

if GIT_EMAIL:
    run(f'git config --global user.email "{GIT_EMAIL}"')
if GIT_USERNAME:
    run(f'git config --global user.name "{GIT_USERNAME}"')

if temp_dir.exists():
    shutil.rmtree(temp_dir)
temp_dir.mkdir()

print(YELLOW + "Initializing temporary repo..." + RESET)
run("git init", cwd=temp_dir)
run(f"git branch -M {GIT_BRANCH}", cwd=temp_dir)

repo_with_token = repo_url.replace("https://", f"https://{GITHUB_TOKEN}@")

try:
    run(f'git remote add origin "{repo_with_token}"', cwd=temp_dir)
except:
    print(YELLOW + "Failed to add remote. Check your token." + RESET)
    exit()

if choice == "2":
    print(YELLOW + "Deleting all files in repo..." + RESET)
    (temp_dir / ".gitkeep").write_text("")
    run("git add .", cwd=temp_dir)
    run('git commit -m "Delete all files by AutoDeploy"', cwd=temp_dir)
    run(f"git push origin {GIT_BRANCH} --force", cwd=temp_dir)
    print(YELLOW + "All files deleted." + RESET)
    exit()

file_path = Path(input(YELLOW + "Enter folder/file path: " + RESET).strip())
if not file_path.exists():
    print("Path not found.")
    exit()

print(YELLOW + "Copying files..." + RESET)

def copy_recursive(src, dest):
    if src.is_file():
        shutil.copy(src, dest)
    else:
        dest.mkdir(exist_ok=True)
        for item in src.iterdir():
            copy_recursive(item, dest / item.name)

for item in file_path.iterdir():
    copy_recursive(item, temp_dir / item.name)

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(YELLOW + "Committing & Pushing..." + RESET)

run("git add .", cwd=temp_dir)

try:
    run(f'git commit -m "{COMMIT_MESSAGE} - {timestamp}"', cwd=temp_dir)
except:
    print(YELLOW + "No changes to commit." + RESET)

run(f"git push -u origin {GIT_BRANCH} --force", cwd=temp_dir)

print(YELLOW + "Push completed." + RESET)

# === Vercel deploy ===
if input(YELLOW + "Deploy to Vercel? (y/n): " + RESET).lower() != "y":
    exit()

if not VERCEL_TOKEN:
    print(YELLOW + "Vercel token not found in .env" + RESET)
    exit()

vercel_dir = temp_dir / ".vercel"
project_json = vercel_dir / "project.json"

if project_json.exists():
    print(YELLOW + "Existing Vercel configuration found. Deploying old project..." + RESET)
    vercel_cmd = f"npx --yes vercel --prod --confirm --token {VERCEL_TOKEN}"
else:
    print(YELLOW + "No Vercel configuration found." + RESET)
    name = input(YELLOW + "Project name: " + RESET).strip()
    if not name:
        name = f"autodeploy-{int(datetime.now().timestamp())}"

    vercel_dir.mkdir(exist_ok=True)
    run(f"npx vercel link --project {name} --token {VERCEL_TOKEN} --confirm", cwd=temp_dir)
    vercel_cmd = f"npx --yes vercel --prod --confirm --token {VERCEL_TOKEN} --name {name}"

print(YELLOW + "Deploying to Vercel..." + RESET)
output = run(vercel_cmd, cwd=temp_dir, silent=True)

urls = [x for x in output.split() if x.startswith("http")]
deployment_url = urls[0] if urls else None

if deployment_url:
    print(YELLOW + "Deployment successful: " + deployment_url + RESET)
else:
    print(YELLOW + "Failed to get deployment URL." + RESET)

# === Cloudflare Domain ===
if input(YELLOW + "Setup custom Cloudflare domain? (y/n): " + RESET).lower() != "y":
    exit()

if not CLOUDFLARE_TOKEN or not CLOUDFLARE_ZONE_ID or not DOMAIN:
    print(YELLOW + "Incomplete Cloudflare data." + RESET)
    exit()

sub = input(YELLOW + "Enter subdomain: " + RESET).strip()
full_sub = f"{sub}.{DOMAIN}"

target = deployment_url.replace("https://", "").split("/")[0] if deployment_url else "cname.vercel-dns.com"

print(YELLOW + f"Creating DNS CNAME {full_sub} -> {target}" + RESET)

resp = requests.post(
    f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records",
    headers={
        "Authorization": f"Bearer {CLOUDFLARE_TOKEN}",
        "Content-Type": "application/json"
    },
    json={
        "type": "CNAME",
        "name": full_sub,
        "content": target,
        "ttl": 3600,
        "proxied": False
    }
)

if resp.json().get("success"):
    print(YELLOW + "DNS record successfully created!" + RESET)
else:
    print("Failed to create DNS:", resp.text)

print(YELLOW + "Done." + RESET)