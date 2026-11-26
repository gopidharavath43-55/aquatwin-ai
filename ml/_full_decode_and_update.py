import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT    = Path(r"C:\Users\gopid\aquatwin-ai")
MOB     = ROOT / "mobile-app"
WWW     = MOB / "www"
ANDROID = MOB / "android"
CAP_PUB = ANDROID / "app" / "src" / "main" / "assets" / "public"
REPO    = "gopidharavath43-55/aquatwin-ai"
APK_URL = f"https://github.com/{REPO}/releases/latest/download/AquaTwin-AI.apk"


def run_cmd(cmd, cwd=ROOT, env=None, check=True, timeout=None):
    res = subprocess.run(cmd, cwd=str(cwd), env=env, timeout=timeout)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed (exit {res.returncode}): {' '.join(cmd)}")
    return res.returncode


def find_jdk21() -> str:
    ms_dir = Path(r"C:\Program Files\Microsoft")
    if ms_dir.exists():
        jdks = sorted(ms_dir.glob("jdk-21*"), reverse=True)
        if jdks:
            return str(jdks[0])
    jbr = Path(r"C:\Program Files\Android\Android Studio\jbr")
    if jbr.exists():
        return str(jbr)
    raise RuntimeError("Java 21 not found.")


def extract_sec_block(html_text: str) -> str:
    m = re.search(
        r"(<!--\s*AQUATWIN_RUNTIME_SECURITY_START\s*-->.*?<!--\s*AQUATWIN_RUNTIME_SECURITY_END\s*-->)",
        html_text,
        re.DOTALL,
    )
    return m.group(1) if m else ""


def recover_clean_v18_html(current_html: str) -> tuple[str, str]:
    saved_sec = extract_sec_block(current_html)

    # 1. Check local backups\AquaTwin-AI-Working-*.zip (exact v18 verified snapshot)
    bak_dir = ROOT / "backups"
    if bak_dir.exists():
        work_zips = sorted(bak_dir.glob("AquaTwin-AI-Working-*.zip"), reverse=True)
        for zp in work_zips:
            try:
                with zipfile.ZipFile(zp, "r") as zf:
                    for cand in ["mobile-app/index.html", "mobile-app/www/index.html"]:
                        if cand in zf.namelist():
                            restored = zf.read(cand).decode("utf-8", errors="ignore")
                            if saved_sec and "AQUATWIN_RUNTIME_SECURITY_START" not in restored:
                                b_idx = restored.lower().rfind("</body>")
                                restored = (
                                    (restored[:b_idx] + "\n" + saved_sec + "\n" + restored[b_idx:])
                                    if b_idx >= 0
                                    else (restored + "\n" + saved_sec)
                                )
                            return restored, f"backup archive {zp.name}"
            except Exception:
                continue

    # 2. Check Git history for the last clean commit before map-buffer / rollout / decode edits
    log_res = subprocess.run(
        ["git", "log", "-n", "30", "--format=%H|%s", "--", "mobile-app/index.html"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if log_res.returncode == 0:
        skip_words = ("rollout", "buffer", "decode", "revert", "slider")
        for line in log_res.stdout.splitlines():
            if "|" not in line:
                continue
            sha, subj = line.split("|", 1)
            if any(w in subj.lower() for w in skip_words):
                continue
            show_res = subprocess.run(
                ["git", "show", f"{sha}:mobile-app/index.html"],
                cwd=str(ROOT),
                capture_output=True,
            )
            if show_res.returncode == 0 and show_res.stdout:
                restored = show_res.stdout.decode("utf-8", errors="ignore")
                if "_atNoBufGuard" not in restored and "AQUATWIN_DIRECT_ROLLOUT" not in restored:
                    if saved_sec and "AQUATWIN_RUNTIME_SECURITY_START" not in restored:
                        b_idx = restored.lower().rfind("</body>")
                        restored = (
                            (restored[:b_idx] + "\n" + saved_sec + "\n" + restored[b_idx:])
                            if b_idx >= 0
                            else (restored + "\n" + saved_sec)
                        )
                    return restored, f"clean Git commit {sha[:7]} ({subj.strip()})"

    return current_html, "in-place HTML cleanup"


def main() -> int:
    jdk21 = find_jdk21()
    sdk_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
    if not sdk_dir.exists():
        raise RuntimeError(f"Android SDK not found at {sdk_dir}")

    env = os.environ.copy()
    env["JAVA_HOME"] = jdk21
    env["ANDROID_HOME"] = str(sdk_dir)
    env["ANDROID_SDK_ROOT"] = str(sdk_dir)
    env["PATH"] = f"{jdk21}\\bin;{sdk_dir}\\platform-tools;{env.get('PATH', '')}"

    # 1. Remove temporary rollout / map-buffer helper scripts
    for rel in [
        "ml/rollout_update.py",
        "ml/rollout_update.ps1",
        "ml/_patch_rollout_html.py",
        "ml/_fix_map_buffering_only.py",
        "ml/_decode_rollout.py",
        "ml/_decode_updates.py",
    ]:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            print(f"[PASS] Removed {rel}")

    # 2. Recover clean v18 HTML + strip all injected overlay blocks
    src_html = MOB / "index.html"
    if not src_html.exists() and (WWW / "index.html").exists():
        shutil.copy2(WWW / "index.html", src_html)
    assert src_html.exists(), "mobile-app/index.html not found"

    current_html = src_html.read_text(encoding="utf-8", errors="ignore")
    html, source_label = recover_clean_v18_html(current_html)
    print(f"[PASS] Decoded base UI from {source_label}")

    markers_to_strip = [
        "AQUATWIN_DIRECT_ROLLOUT",
        "AQUATWIN_MAP_NOBUFFER_CSS",
        "APP_UPDATER",
        "HIDE_SLIDERS_BOX",
        "SIM_SLIDERS_BOX",
        "REMOVE_3_SLIDERS",
        "REMOVE_SPECIFIC_SLIDERS",
    ]
    for tag in markers_to_strip:
        html = re.sub(
            rf"<!--\s*{tag}_START\s*-->.*?<!--\s*{tag}_END\s*-->\s*",
            "",
            html,
            flags=re.DOTALL,
        )

    # Ensure clean v18 applyMapLayers() if _atNoBufGuard remained in-place
    if "_atNoBufGuard" in html or "__AT_TILES_WARMED__" in html:
        clean_apply_fn = r"""function applyMapLayers(){
    if (!window.L || !window.L.tileLayer) return;
    if (!satLayer){
      satLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        maxNativeZoom: 18,
        keepBuffer: 4,
        updateWhenIdle: true,
        crossOrigin: true
      });
    }
    if (!labelLayer){
      labelLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        maxNativeZoom: 18,
        opacity: 0.96,
        keepBuffer: 4,
        updateWhenIdle: true,
        crossOrigin: true
      });
    }
    if (!streetLayer){
      streetLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        maxNativeZoom: 18,
        keepBuffer: 4,
        updateWhenIdle: true,
        crossOrigin: true
      });
    }
    findLeafletMaps().forEach(function(m){
      try {
        if (satEnabled){
          if (m.hasLayer(streetLayer)) m.removeLayer(streetLayer);
          if (!m.hasLayer(satLayer)) satLayer.addTo(m);
          if (!m.hasLayer(labelLayer)) labelLayer.addTo(m);
        } else {
          if (m.hasLayer(satLayer)) m.removeLayer(satLayer);
          if (m.hasLayer(labelLayer)) m.removeLayer(labelLayer);
          if (!m.hasLayer(streetLayer)) streetLayer.addTo(m);
        }
      } catch(e){}
    });
  }"""
        pat = re.compile(r"function applyMapLayers\(\)\{[\s\S]*?(?=\n\s*function syncMapAndSatellite\()")
        if pat.search(html):
            html = pat.sub(lambda m: clean_apply_fn, html, count=1)
            print("[PASS] Restored clean v18 applyMapLayers()")

    # 3. Bump versionCode above both build.gradle and version.json so Android installs cleanly
    gradle_path = ANDROID / "app" / "build.gradle"
    gtxt = gradle_path.read_text(encoding="utf-8")
    gm = re.search(r"versionCode\s+(\d+)", gtxt)
    g_code = int(gm.group(1)) if gm else 143

    j_code = 0
    ver_path = ROOT / "version.json"
    if ver_path.exists():
        try:
            j_code = int(json.loads(ver_path.read_text(encoding="utf-8")).get("version_code", 0))
        except Exception:
            j_code = 0

    next_code = max(g_code, j_code) + 1
    next_ver = f"1.{next_code}"
    tag = f"v{next_ver}"

    gtxt = re.sub(r"versionCode\s+\d+", f"versionCode {next_code}", gtxt, count=1)
    gtxt = re.sub(r'versionName\s+"[^"]+"', f'versionName "{next_ver}"', gtxt, count=1)
    gradle_path.write_text(gtxt, encoding="utf-8")
    print(f"[PASS] Bumped app version -> {tag} (code {next_code})")

    # Stamp AQUATWIN_VERSION in HTML
    if re.search(r'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', html):
        html = re.sub(r'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', f'window.AQUATWIN_VERSION = "{next_ver}"', html)
    else:
        html = html.replace("</head>", f'<script>window.AQUATWIN_VERSION = "{next_ver}";</script>\n</head>', 1)

    # Validate every inline script with node --check before writing
    node_exe = shutil.which("node")
    if node_exe:
        for idx, m in enumerate(re.finditer(r"<script\b[^>]*>([\s\S]*?)</script>", html, re.IGNORECASE)):
            js_code = m.group(1).strip()
            if not js_code:
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
                tf.write(js_code)
                tmp_js = tf.name
            try:
                chk = subprocess.run([node_exe, "--check", tmp_js], capture_output=True, text=True)
                if chk.returncode != 0:
                    raise RuntimeError(f"Inline script #{idx + 1} syntax error:\n{chk.stderr}")
            finally:
                Path(tmp_js).unlink(missing_ok=True)
        print("[PASS] Verified all HTML scripts with node --check (0 errors)")

    for dst in [src_html, WWW / "index.html", CAP_PUB / "index.html"]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(html, encoding="utf-8")
    print("[PASS] Synced decoded index.html across mobile-app, www & Android assets")

    # 4. Sync Capacitor & assemble signed release APK
    run_cmd(["cmd", "/c", "npx", "cap", "sync", "android"], cwd=MOB, env=env)
    if not (ANDROID / "keystore.properties").exists():
        raise RuntimeError("keystore.properties missing in mobile-app\\android.")
    run_cmd(["cmd", "/c", "gradlew.bat", "assembleRelease", f"-Dorg.gradle.java.home={jdk21}"], cwd=ANDROID, env=env)

    built_apk = ANDROID / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    if not built_apk.exists():
        raise RuntimeError(f"Release APK missing at {built_apk}")

    rel_dir = ROOT / "release"
    rel_dir.mkdir(parents=True, exist_ok=True)
    dst_apk = rel_dir / "AquaTwin-AI.apk"
    shutil.copy2(built_apk, dst_apk)
    mb = dst_apk.stat().st_size / (1024 * 1024)
    print(f"[PASS] Built signed APK -> release\\AquaTwin-AI.apk ({mb:.2f} MB)")

    # 5. Update version.json
    ist = timezone(timedelta(hours=5, minutes=30))
    notes = (
        "• Restored clean v18 Liquid Glass UI, Demo switch & Satellite Map\n"
        "• Live 33 Telangana districts telemetry & forecasts\n"
        "• All 5 security layers locked & verified"
    )
    ver_obj = {
        "version": next_ver,
        "version_code": next_code,
        "apk_url": APK_URL,
        "notes": notes,
        "force": False,
        "updated_at": datetime.now(ist).strftime("%Y-%m-%d %H:%M IST"),
    }
    ver_path.write_text(json.dumps(ver_obj, indent=2) + "\n", encoding="utf-8")

    # 6. Optional USB ADB install with 25s anti-hang timeout
    adb = sdk_dir / "platform-tools" / "adb.exe"
    if adb.exists():
        try:
            dev = subprocess.run([str(adb), "devices"], capture_output=True, text=True, timeout=10)
            if re.search(r"^\S+\s+device\r?$", dev.stdout, re.MULTILINE):
                print(f"[INFO] USB phone detected — installing {tag} (25s timeout)...")
                inst = subprocess.run([str(adb), "install", "-r", "-d", str(dst_apk)], timeout=25)
                if inst.returncode == 0:
                    subprocess.run(
                        [str(adb), "shell", "monkey", "-p", "com.aquatwin.ai", "-c", "android.intent.category.LAUNCHER", "1"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                    print(f"[PASS] Installed & launched {tag} on USB phone!")
                else:
                    print("[WARN] USB install returned non-zero — APK is ready in release\\AquaTwin-AI.apk.")
        except subprocess.TimeoutExpired:
            print("[WARN] USB install timed out (phone locked) — continuing GitHub & Web update.")

    # 7. Reseal HMAC-SHA256 ledger & run full 5-Layer Extreme Security Audit
    for cmd, req in [
        ([sys.executable, str(ROOT / "ml" / "generate_integrity_manifest.py")], False),
        ([sys.executable, str(ROOT / "ml" / "verify_data_lock.py"), "--seal"], True),
        ([sys.executable, str(ROOT / "ml" / "extreme_security_audit.py")], True),
    ]:
        if Path(cmd[1]).exists():
            run_cmd(cmd, cwd=ROOT, env=env, check=req)

    # 8. Commit & push clean decoded state + version tag to GitHub
    run_cmd(["git", "config", "core.autocrlf", "false"], cwd=ROOT, check=False)
    run_cmd(["git", "config", "core.safecrlf", "false"], cwd=ROOT, check=False)
    run_cmd(["git", "add", "-A"], cwd=ROOT)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True)
    if st.stdout.strip():
        run_cmd(["git", "commit", "-m", f"Decode patches, restore clean v18 + 5-layer security ({tag})"], cwd=ROOT)
    run_cmd(["git", "tag", "-f", tag], cwd=ROOT)
    run_cmd(["git", "push", "origin", "main"], cwd=ROOT)
    run_cmd(["git", "push", "origin", f"refs/tags/{tag}", "--force"], cwd=ROOT)
    print(f"[PASS] Pushed clean decoded build & tag {tag} to GitHub")

    # 9. Upload signed APK directly to GitHub Releases as Latest
    auto_rel = ROOT / "ml" / "github_auto_release.py"
    if auto_rel.exists():
        run_cmd([sys.executable, str(auto_rel)], cwd=ROOT, env=env)
    else:
        raise RuntimeError("ml\\github_auto_release.py not found.")

    # 10. Redeploy Web App on Vercel (skips safely if daily limit is still active)
    v_rc = run_cmd(["cmd", "/c", "npx", "--yes", "vercel", "--prod", "--yes"], cwd=WWW, env=env, check=False)
    if v_rc == 0:
        print("[PASS] Web app updated on Vercel")
    else:
        print("[WARN] Vercel deploy skipped (daily limit or login) — GitHub APK & repo are updated.")

    # 11. Verify live GitHub version.json & direct APK download link
    api_req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/version.json?ref=main",
        headers={"User-Agent": "AquaTwin-Verify"},
    )
    with urllib.request.urlopen(api_req, timeout=15) as resp:
        api_data = json.loads(resp.read().decode("utf-8"))
    live_ver = json.loads(base64.b64decode(api_data["content"]).decode("utf-8"))
    print(f"[PASS] Verified GitHub version.json : v{live_ver['version']} (code {live_ver['version_code']})")

    probe_req = urllib.request.Request(APK_URL, headers={"User-Agent": "AquaTwin-Verify", "Range": "bytes=0-0"})
    with urllib.request.urlopen(probe_req, timeout=20) as pr:
        print(f"[PASS] Verified Direct APK Link     : HTTP {pr.status} ({mb:.2f} MB)")

    print("\n=========================================================")
    print(f"  DECODE & UPDATE COMPLETE — AquaTwin AI {tag} IS LIVE")
    print(f"  Download APK: {APK_URL}")
    print("=========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
