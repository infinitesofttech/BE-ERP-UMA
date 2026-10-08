import os
import requests
import hashlib
import time
import re

USERNAME = 'umaERP'
PASSWORD = 'AAaa@123456@'
DOMAIN = 'umaERP.pythonanywhere.com'
REMOTE_BASE = '/home/umaERP/BE-ERP-UMA'
LOCAL_DIR = r'd:/UMA ERP/BE-ERP-UMA'

EXCLUDE_DIRS = {'.git', '__pycache__', 'env', 'venv', '.vscode', '.idea', 'staticfiles'}
EXCLUDE_EXTS = {'.pyc', '.log'}
EXCLUDE_FILES = {'db.sqlite3', 'db.sqlite3-journal'}

def log(msg):
    print(msg, flush=True)

def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    login_url = 'https://www.pythonanywhere.com/login/'
    r_login_page = session.get(login_url, timeout=15)
    csrf = session.cookies.get('csrftoken')
    login_data = {
        'auth-username': USERNAME,
        'auth-password': PASSWORD,
        'login_view-current_step': 'auth',
        'csrfmiddlewaretoken': csrf
    }
    r_login = session.post(login_url, data=login_data, headers={'Referer': login_url}, timeout=15)
    if r_login.status_code != 200:
        raise Exception(f"Login failed: status {r_login.status_code}")
    csrf_token = session.cookies.get('csrftoken')
    headers = {
        'X-CSRFToken': csrf_token,
        'Referer': 'https://www.pythonanywhere.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    return session, headers

def upload_file(session, rel_path, headers):
    local_path = os.path.join(LOCAL_DIR, rel_path.replace('/', os.sep))
    with open(local_path, 'rb') as f:
        content = f.read()

    remote_path = f"{REMOTE_BASE}/{rel_path}"
    upload_url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/files/path{remote_path}"
    
    for attempt in range(5):
        try:
            r = session.post(upload_url, files={'content': content}, headers=headers, timeout=30)
            if r.status_code in [200, 201]:
                return True, "OK"
            elif r.status_code == 429:
                wait_time = 3
                m = re.search(r'available in (\d+) seconds', r.text)
                if m:
                    wait_time = int(m.group(1)) + 1
                time.sleep(wait_time)
            else:
                return False, f"Status {r.status_code}: {r.text[:60]}"
        except Exception as e:
            time.sleep(2)
    return False, "Timed out after retries"

def main():
    log("=" * 80)
    log("UMA ERP - AUDIT & SYNC ALL BACKEND CODE TO PYTHONANYWHERE")
    log("=" * 80)
    
    session, headers = get_session()
    log("[1] Authentication successful! Connected to PythonAnywhere.")

    # List all important code files in apps/ and erp_backend/
    all_code_files = []
    for root, dirs, files in os.walk(LOCAL_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f in EXCLUDE_FILES or any(f.endswith(ext) for ext in EXCLUDE_EXTS):
                continue
            if f.startswith('scratch_') or f.startswith('audit_'):
                continue
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, LOCAL_DIR).replace('\\', '/')
            # Focus on app code, migrations, settings, urls, wsgi, manage
            if rel_path.startswith('apps/') or rel_path.startswith('erp_backend/') or rel_path in ['manage.py', 'requirements.txt', 'test_full_crud_operations.py']:
                all_code_files.append(rel_path)

    all_code_files.sort()
    log(f"[2] Auditing {len(all_code_files)} backend source files on PythonAnywhere...")

    missing_files = []
    outdated_files = []
    matching_files = []

    for idx, rel_path in enumerate(all_code_files, 1):
        local_path = os.path.join(LOCAL_DIR, rel_path.replace('/', os.sep))
        with open(local_path, 'rb') as f:
            local_bytes = f.read()
        local_hash = hashlib.md5(local_bytes.replace(b'\r\n', b'\n')).hexdigest()

        remote_path = f"{REMOTE_BASE}/{rel_path}"
        url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/files/path{remote_path}"
        
        try:
            r = session.get(url, headers=headers, timeout=15)
            if r.status_code == 404:
                missing_files.append(rel_path)
                log(f"  [{idx}/{len(all_code_files)}] [MISSING]  {rel_path}")
            elif r.status_code == 200:
                remote_bytes = r.content
                remote_hash = hashlib.md5(remote_bytes.replace(b'\r\n', b'\n')).hexdigest()
                if local_hash != remote_hash:
                    outdated_files.append(rel_path)
                    log(f"  [{idx}/{len(all_code_files)}] [OUTDATED] {rel_path}")
                else:
                    matching_files.append(rel_path)
            else:
                log(f"  [{idx}/{len(all_code_files)}] [ERR {r.status_code}] {rel_path}")
        except Exception as e:
            log(f"  [{idx}/{len(all_code_files)}] [EXC] {rel_path}: {e}")
        time.sleep(0.08)

    log("\n" + "=" * 80)
    log("AUDIT SUMMARY:")
    log(f"  Total source files checked : {len(all_code_files)}")
    log(f"  Matching & Up-to-date      : {len(matching_files)}")
    log(f"  Outdated / Needs Update    : {len(outdated_files)}")
    log(f"  Missing on PythonAnywhere  : {len(missing_files)}")
    log("=" * 80)

    to_sync = outdated_files + missing_files
    if to_sync:
        log(f"\n[3] Uploading {len(to_sync)} missing / outdated files to PythonAnywhere...")
        success_count = 0
        for idx, rel_path in enumerate(to_sync, 1):
            ok, msg = upload_file(session, rel_path, headers)
            if ok:
                log(f"  [{idx}/{len(to_sync)}] [SUCCESS] {rel_path}")
                success_count += 1
            else:
                log(f"  [{idx}/{len(to_sync)}] [FAILED]  {rel_path}: {msg}")
            time.sleep(0.3)
        log(f"\nSynced {success_count}/{len(to_sync)} files successfully.")

    log("\n[4] Reloading WebApp on PythonAnywhere...")
    reload_url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/webapps/{DOMAIN}/reload/"
    r_reload = session.post(reload_url, headers=headers, timeout=25)
    if r_reload.status_code == 200:
        log("[OK] WebApp reloaded successfully!")
    else:
        log(f"[WARN] WebApp reload status: {r_reload.status_code} - {r_reload.text[:100]}")

    log("\n[5] Verifying Live PythonAnywhere API Health...")
    time.sleep(4)
    endpoints = [
        '/api/auth/me/',
        '/api/crm/leads/',
        '/api/crm/quotations/',
        '/api/projects/',
        '/api/project-jobs/',
        '/api/designer/jobs/',
        '/api/designer/tasks/',
        '/api/boms/',
        '/api/bom-headers/',
        '/api/mrp/',
        '/api/goods-receipt-notes/',
        '/api/work-orders/',
        '/api/production-entries/',
        '/api/invoices/',
    ]
    for ep in endpoints:
        try:
            r = requests.get(f"https://{DOMAIN}{ep}", timeout=10)
            log(f"  Status {r.status_code} -> https://{DOMAIN}{ep}")
        except Exception as e:
            log(f"  Error -> https://{DOMAIN}{ep}: {e}")

    log("\n" + "=" * 80)
    log("PYTHONANYWHERE AUDIT & SYNC COMPLETE!")
    log("=" * 80)

if __name__ == '__main__':
    main()
