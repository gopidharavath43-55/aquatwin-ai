import json, os, urllib.request
import ee

def try_init(pid):
    try:
        ee.Initialize(project=pid)
        return True
    except Exception:
        return False

found = None
candidates = []

try:
    cpath = ee.oauth.get_credentials_path()
    if os.path.exists(cpath):
        cdata = json.load(open(cpath, encoding="utf-8"))
        if cdata.get("project"):
            candidates.append(cdata["project"])
except Exception:
    pass

try:
    creds = ee.data.get_persistent_credentials()
    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
    except Exception:
        import google_auth_httplib2, httplib2
        creds.refresh(google_auth_httplib2.Request(httplib2.Http()))

    req = urllib.request.Request(
        "https://cloudresourcemanager.googleapis.com/v1/projects",
        headers={"Authorization": f"Bearer {creds.token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for p in data.get("projects", []):
        if p.get("lifecycleState") == "ACTIVE" and p["projectId"] not in candidates:
            candidates.append(p["projectId"])
except Exception:
    pass

if candidates:
    print("Checking your projects:", candidates)
    for pid in candidates:
        if try_init(pid):
            found = pid
            break

if not found:
    print("\nOpen https://code.earthengine.google.com/ and copy the exact Project ID in the top-right corner.")
    pid = input("Paste your real Project ID here and press Enter: ").strip()
    if pid and try_init(pid):
        found = pid
    else:
        raise SystemExit(f"Could not connect with '{pid}'. Check the exact Project ID in the top-right corner of Earth Engine.")

with open("gee_project.txt", "w", encoding="utf-8") as f:
    f.write(found)

print(f"\nGEE Live Connected! Saved real Project ID: {found}")
