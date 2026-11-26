import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\gopid\aquatwin-ai")
REPO = "gopidharavath43-55/aquatwin-ai"
APK_PATH = ROOT / "release" / "AquaTwin-AI.apk"
VER_PATH = ROOT / "version.json"
ASSET_NAME = "AquaTwin-AI.apk"
API_VERSION = "2026-03-10"


def get_github_token() -> str:
    # 1. Environment variable (if set)
    for env_key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val

    # 2. GitHub CLI cached token (if gh is installed & logged in)
    if shutil.which("gh"):
        try:
            r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass

    # 3. Windows Git Credential Manager token (already used by git push)
    try:
        r = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=15,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith("password="):
                    tok = line.split("=", 1)[1].strip()
                    if tok:
                        return tok
    except Exception:
        pass

    return ""


def api_request(url: str, token: str, method: str = "GET", payload=None, raw_bytes: bytes = None, content_type: str = "application/json"):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "AquaTwin-AutoRelease",
        "X-GitHub-Api-Version": API_VERSION,
    }
    data = None
    if raw_bytes is not None:
        data = raw_bytes
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(raw_bytes))
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"message": err_body}
        return e.code, err_json


def main() -> int:
    if not APK_PATH.exists():
        print(f"[FAIL] APK not found at {APK_PATH}")
        return 1

    ver = "1.142"
    notes = "Latest AquaTwin AI signed Android release."
    if VER_PATH.exists():
        meta = json.loads(VER_PATH.read_text(encoding="utf-8"))
        ver = str(meta.get("version", ver)).strip()
        notes = str(meta.get("notes", notes)).strip() or notes
    tag = f"v{ver}"

    # Ensure Git tag exists on GitHub before releasing
    subprocess.run(["git", "tag", "-f", tag], cwd=str(ROOT), check=False, capture_output=True)
    subprocess.run(["git", "push", "origin", f"refs/tags/{tag}", "--force"], cwd=str(ROOT), check=False, capture_output=True)

    token = get_github_token()
    if not token:
        print("[FAIL] No GitHub login token found in Git Credential Manager or GitHub CLI.")
        print("Run: winget install --id GitHub.cli -e ; gh auth login -h github.com -p https -w")
        return 2

    # 1. Get existing release for tag, or create it automatically
    tag_url = f"https://api.github.com/repos/{REPO}/releases/tags/{tag}"
    code, rel = api_request(tag_url, token, method="GET")

    if code == 404:
        print(f"[INFO] Creating new GitHub Release {tag}...")
        create_url = f"https://api.github.com/repos/{REPO}/releases"
        code, rel = api_request(
            create_url,
            token,
            method="POST",
            payload={
                "tag_name": tag,
                "target_commitish": "main",
                "name": f"AquaTwin AI {tag}",
                "body": notes,
                "draft": False,
                "prerelease": False,
                "make_latest": "true",
            },
        )
        if code not in (200, 201):
            print(f"[FAIL] Could not create release {tag} (HTTP {code}): {rel.get('message', rel)}")
            return 1
    elif code != 200:
        print(f"[FAIL] GitHub API auth/access failed (HTTP {code}): {rel.get('message', rel)}")
        return 1

    rel_id = rel["id"]
    print(f"[PASS] Release {tag} ready on GitHub (ID: {rel_id})")

    # 2. Delete any stale or broken AquaTwin-AI.apk asset on this release before uploading
    for asset in rel.get("assets", []):
        if asset.get("name") == ASSET_NAME or asset.get("state") == "starter":
            del_url = f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}"
            api_request(del_url, token, method="DELETE")
            print(f"[INFO] Removed previous asset '{asset.get('name')}' before re-uploading")

    # 3. Upload AquaTwin-AI.apk directly via GitHub Releases upload endpoint
    apk_bytes = APK_PATH.read_bytes()
    mb = len(apk_bytes) / (1024 * 1024)
    upload_base = re.sub(r"\{.*\}$", "", rel.get("upload_url", f"https://uploads.github.com/repos/{REPO}/releases/{rel_id}/assets"))
    upload_url = f"{upload_base}?name={ASSET_NAME}"
    print(f"[INFO] Uploading {ASSET_NAME} ({mb:.2f} MB) directly to GitHub Release {tag}...")

    up_code, up_res = api_request(
        upload_url,
        token,
        method="POST",
        raw_bytes=apk_bytes,
        content_type="application/vnd.android.package-archive",
    )
    if up_code not in (200, 201):
        print(f"[FAIL] APK upload failed (HTTP {up_code}): {up_res.get('message', up_res)}")
        return 1

    # 4. Ensure release is published (not draft) and marked Latest
    patch_url = f"https://api.github.com/repos/{REPO}/releases/{rel_id}"
    api_request(
        patch_url,
        token,
        method="PATCH",
        payload={"name": f"AquaTwin AI {tag}", "body": notes, "draft": False, "prerelease": False, "make_latest": "true"},
    )
    print(f"[PASS] Uploaded {ASSET_NAME} ({mb:.2f} MB) and set {tag} as Latest Release!")

    # 5. Verify public direct download link works without 404 (1-byte range probe)
    public_url = f"https://github.com/{REPO}/releases/latest/download/{ASSET_NAME}"
    probe_req = urllib.request.Request(public_url, headers={"User-Agent": "AquaTwin-Verify", "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(probe_req, timeout=20) as pr:
            if pr.status in (200, 206):
                print(f"\n[PASS] DIRECT DOWNLOAD LINK VERIFIED LIVE (HTTP {pr.status}):")
                print(public_url)
                return 0
    except Exception as e:
        print(f"[WARN] Upload succeeded, but public probe returned: {e}")
        print(f"Direct link: {public_url}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
