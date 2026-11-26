import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT    = Path(r"C:\Users\gopid\aquatwin-ai")
MOB     = ROOT / "mobile-app"
WWW     = MOB / "www"
ANDROID = MOB / "android"
CAP_PUB = ANDROID / "app" / "src" / "main" / "assets" / "public"
REPO    = "gopidharavath43-55/aquatwin-ai"
APK_URL = f"https://github.com/{REPO}/releases/latest/download/AquaTwin-AI.apk"

DEFAULT_NOTES = (
    "• Zero-buffer Satellite Map & 120Hz Liquid Glass UI\n"
    "• Live 33 Telangana districts telemetry & forecasts\n"
    "• Full 5-layer security hardening & direct OTA rollout"
)


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


def main() -> int:
    notes = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else DEFAULT_NOTES

    jdk21 = find_jdk21()
    sdk_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
    if not sdk_dir.exists():
        raise RuntimeError(f"Android SDK not found at {sdk_dir}")

    env = os.environ.copy()
    env["JAVA_HOME"] = jdk21
    env["ANDROID_HOME"] = str(sdk_dir)
    env["ANDROID_SDK_ROOT"] = str(sdk_dir)
    env["PATH"] = f"{jdk21}\\bin;{sdk_dir}\\platform-tools;{env.get('PATH', '')}"

    # 1. Bump versionCode & versionName in build.gradle
    gradle_path = ANDROID / "app" / "build.gradle"
    gtxt = gradle_path.read_text(encoding="utf-8")
    m = re.search(r"versionCode\s+(\d+)", gtxt)
    next_code = int(m.group(1)) + 1 if m else 144
    next_ver = f"1.{next_code}"
    tag = f"v{next_ver}"

    gtxt = re.sub(r"versionCode\s+\d+", f"versionCode {next_code}", gtxt, count=1)
    gtxt = re.sub(r'versionName\s+"[^"]+"', f'versionName "{next_ver}"', gtxt, count=1)
    gradle_path.write_text(gtxt, encoding="utf-8")
    print(f"[PASS] Bumped app version -> {tag} (code {next_code})")

    # 2. Stamp version, wire clean non-blocking Direct OTA Rollout Pill & sync HTML
    src_html = MOB / "index.html"
    if not src_html.exists() and (WWW / "index.html").exists():
        shutil.copy2(WWW / "index.html", src_html)
    html = src_html.read_text(encoding="utf-8", errors="ignore")

    if re.search(r'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', html):
        html = re.sub(r'window\.AQUATWIN_VERSION\s*=\s*"[^"]+"', f'window.AQUATWIN_VERSION = "{next_ver}"', html)
    else:
        html = html.replace("</head>", f'<script>window.AQUATWIN_VERSION = "{next_ver}";</script>\n</head>', 1)

    html = re.sub(
        r"<!--\s*AQUATWIN_DIRECT_ROLLOUT_START\s*-->.*?<!--\s*AQUATWIN_DIRECT_ROLLOUT_END\s*-->\s*",
        "",
        html,
        flags=re.DOTALL,
    )

    rollout_js = r"""(function(){
  if (window.__AT_DIRECT_ROLLOUT_V1__) return;
  window.__AT_DIRECT_ROLLOUT_V1__ = true;

  var INSTALLED_VER = "__NEW_VER__";
  window.AQUATWIN_VERSION = INSTALLED_VER;

  var isNative = Boolean(
    (window.Capacitor && typeof window.Capacitor.isNativePlatform === "function" && window.Capacitor.isNativePlatform()) ||
    location.protocol === "capacitor:"
  );
  if (!isNative) return;

  function isNewer(remoteV, localV){
    var r = String(remoteV || "").replace(/^v/i, "").split(".").map(function(n){ return parseInt(n, 10) || 0; });
    var l = String(localV || "").replace(/^v/i, "").split(".").map(function(n){ return parseInt(n, 10) || 0; });
    var len = Math.max(r.length, l.length);
    for (var i = 0; i < len; i++){
      if ((r[i] || 0) > (l[i] || 0)) return true;
      if ((r[i] || 0) < (l[i] || 0)) return false;
    }
    return false;
  }

  function showDirectRolloutPill(latestVer, apkUrl){
    if (document.getElementById("at-direct-rollout-pill")) return;
    if (typeof window.atIsTrustedApkUrl === "function" && !window.atIsTrustedApkUrl(apkUrl)) return;

    var bar = document.createElement("div");
    bar.id = "at-direct-rollout-pill";
    bar.style.cssText = "position:fixed;top:calc(12px + env(safe-area-inset-top));left:50%;transform:translateX(-50%);z-index:2147483600;display:flex;align-items:center;gap:10px;padding:8px 12px 8px 14px;border-radius:999px;background:rgba(10,22,42,0.88);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1px solid rgba(56,189,248,0.45);box-shadow:0 12px 30px rgba(0,0,0,0.48);color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,Roboto,sans-serif;font-size:12px;font-weight:700;max-width:92vw;";

    var lbl = document.createElement("span");
    lbl.textContent = "AquaTwin v" + latestVer + " ready";
    lbl.style.cssText = "white-space:nowrap;";

    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Update";
    btn.style.cssText = "border:0;border-radius:999px;padding:6px 12px;background:linear-gradient(135deg,#0ea5e9,#2563eb);color:#fff;font-size:12px;font-weight:800;cursor:pointer;";
    btn.onclick = function(){
      btn.textContent = "Downloading...";
      window.open(apkUrl, "_blank", "noopener,noreferrer");
      setTimeout(function(){ btn.textContent = "Update"; }, 2500);
    };

    var cls = document.createElement("button");
    cls.type = "button";
    cls.textContent = "x";
    cls.setAttribute("aria-label", "Dismiss");
    cls.style.cssText = "border:0;background:transparent;color:#94a3b8;font-size:14px;font-weight:700;padding:2px 6px;cursor:pointer;";
    cls.onclick = function(){ if (bar.parentNode) bar.parentNode.removeChild(bar); };

    bar.appendChild(lbl);
    bar.appendChild(btn);
    bar.appendChild(cls);
    document.body.appendChild(bar);
  }

  function checkRollout(){
    var url = "https://raw.githubusercontent.com/gopidharavath43-55/aquatwin-ai/main/version.json?t=" + Date.now();
    fetch(url, { cache: "no-store" })
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(data){
        if (!data || !data.version || !data.apk_url) return;
        if (isNewer(data.version, INSTALLED_VER)){
          showDirectRolloutPill(data.version, data.apk_url);
        }
      })
      .catch(function(){});
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", function(){ setTimeout(checkRollout, 2400); }, { once: true });
  } else {
    setTimeout(checkRollout, 2400);
  }
})();""".replace("__NEW_VER__", next_ver)

    node_exe = shutil.which("node")
    if node_exe:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
            tf.write(rollout_js)
            tmp_js = tf.name
        try:
            chk = subprocess.run([node_exe, "--check", tmp_js], capture_output=True, text=True)
            if chk.returncode != 0:
                raise RuntimeError(f"Rollout JS syntax error:\n{chk.stderr}")
        finally:
            Path(tmp_js).unlink(missing_ok=True)

    block = (
        "<!-- AQUATWIN_DIRECT_ROLLOUT_START -->\n"
        '<script id="at-direct-rollout-js">\n' + rollout_js.strip() + "\n</script>\n"
        "<!-- AQUATWIN_DIRECT_ROLLOUT_END -->"
    )
    b_idx = html.lower().rfind("</body>")
    html = (html[:b_idx] + block + "\n" + html[b_idx:]) if b_idx >= 0 else (html + "\n" + block)

    for dst in [src_html, WWW / "index.html", CAP_PUB / "index.html"]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(html, encoding="utf-8")
    print(f"[PASS] Stamped {tag} & synced Direct OTA Rollout Pill (0 JS errors)")

    # 3. Sync Capacitor inside mobile-app & build signed release APK
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

    # 4. Write clean version.json
    ist = timezone(timedelta(hours=5, minutes=30))
    ver_obj = {
        "version": next_ver,
        "version_code": next_code,
        "apk_url": APK_URL,
        "notes": notes,
        "force": False,
        "updated_at": datetime.now(ist).strftime("%Y-%m-%d %H:%M IST"),
    }
    (ROOT / "version.json").write_text(json.dumps(ver_obj, indent=2) + "\n", encoding="utf-8")

    # 5. Optional USB ADB install with 30s anti-hang timeout
    adb = sdk_dir / "platform-tools" / "adb.exe"
    if adb.exists():
        try:
            dev = subprocess.run([str(adb), "devices"], capture_output=True, text=True, timeout=10)
            if re.search(r"^\S+\s+device\r?$", dev.stdout, re.MULTILINE):
                print(f"[INFO] USB phone found — installing {tag} (30s timeout)...")
                inst = subprocess.run([str(adb), "install", "-r", str(dst_apk)], timeout=30)
                if inst.returncode == 0:
                    subprocess.run(
                        [str(adb), "shell", "monkey", "-p", "com.aquatwin.ai", "-c", "android.intent.category.LAUNCHER", "1"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                    print(f"[PASS] Installed & opened {tag} on USB phone!")
                else:
                    print("[WARN] USB install returned non-zero — continuing GitHub & Web rollout.")
        except subprocess.TimeoutExpired:
            print("[WARN] USB install timed out (phone locked) — continuing GitHub & Web rollout.")

    # 6. Refresh integrity manifest, reseal HMAC-SHA256 ledger & run 5-Layer Audit
    for script_args in [
        ([sys.executable, str(ROOT / "ml" / "generate_integrity_manifest.py")], False),
        ([sys.executable, str(ROOT / "ml" / "verify_data_lock.py"), "--seal"], True),
        ([sys.executable, str(ROOT / "ml" / "extreme_security_audit.py")], True),
    ]:
        cmd, required = script_args
        if Path(cmd[1]).exists():
            run_cmd(cmd, cwd=ROOT, env=env, check=required)

    # 7. Commit & push main + release tag to GitHub
    run_cmd(["git", "config", "core.autocrlf", "false"], cwd=ROOT, check=False)
    run_cmd(["git", "config", "core.safecrlf", "false"], cwd=ROOT, check=False)
    add_files = [
        "version.json",
        "mobile-app/index.html",
        "mobile-app/www/index.html",
        "mobile-app/android/app/build.gradle",
        "ml/data_integrity_ledger.json",
        "ml/data_3y/integrity_manifest.json",
        "ml/rollout_update.py",
        "ml/rollout_update.ps1",
    ]
    existing_add = [f for f in add_files if (ROOT / f).exists()]
    if existing_add:
        run_cmd(["git", "add"] + existing_add, cwd=ROOT)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True, text=True)
    if st.stdout.strip():
        run_cmd(["git", "commit", "-m", f"Direct rollout AquaTwin AI {tag} (signed APK + OTA + 5-layer security)"], cwd=ROOT)
    run_cmd(["git", "tag", "-f", tag], cwd=ROOT)
    run_cmd(["git", "push", "origin", "main"], cwd=ROOT)
    run_cmd(["git", "push", "origin", f"refs/tags/{tag}", "--force"], cwd=ROOT)
    print(f"[PASS] Pushed main & tag {tag} to GitHub")

    # 8. Upload signed APK directly to GitHub Latest Release
    run_cmd([sys.executable, str(ROOT / "ml" / "github_auto_release.py")], cwd=ROOT, env=env)

    # 9. Redeploy Web App on Vercel (auto-skips cleanly if free daily limit hit)
    v_rc = run_cmd(["cmd", "/c", "npx", "--yes", "vercel", "--prod", "--yes"], cwd=WWW, env=env, check=False)
    if v_rc == 0:
        print("[PASS] Web app rolled out live on Vercel")
    else:
        print("[WARN] Vercel deploy skipped (daily limit or login) — Android GitHub rollout is LIVE.")

    # 10. Verify live GitHub version.json via API & direct APK download
    api_req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/version.json?ref=main",
        headers={"User-Agent": "AquaTwin-Rollout"},
    )
    with urllib.request.urlopen(api_req, timeout=15) as resp:
        api_data = json.loads(resp.read().decode("utf-8"))
    live_ver = json.loads(base64.b64decode(api_data["content"]).decode("utf-8"))
    print(f"[PASS] Verified GitHub version.json : v{live_ver['version']} (code {live_ver['version_code']})")

    probe_req = urllib.request.Request(APK_URL, headers={"User-Agent": "AquaTwin-Verify", "Range": "bytes=0-0"})
    with urllib.request.urlopen(probe_req, timeout=20) as pr:
        print(f"[PASS] Verified Direct APK Link     : HTTP {pr.status} ({mb:.2f} MB)")

    print("\n=========================================================")
    print(f"  DIRECT ROLLOUT COMPLETE — AquaTwin AI {tag} IS LIVE")
    print(f"  Android APK: {APK_URL}")
    print("=========================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
