"""Post files to Shopify staged-upload storage. stdin: one line per file:
<local path> <content-type> <x-goog-date> <key> <signature> <policy>"""
import subprocess, sys
for line in sys.stdin:
    if not line.strip(): continue
    f, ct, date, key, sig, pol = line.split()
    r = subprocess.run(['curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', 'https://shopify-staged-uploads.storage.googleapis.com/',
        '-F', 'Content-Type=' + ct, '-F', 'success_action_status=201', '-F', 'acl=private', '-F', 'key=' + key,
        '-F', 'x-goog-date=' + date, '-F', 'x-goog-credential=merchant-assets@shopify-tiers.iam.gserviceaccount.com/' + date[:8] + '/auto/storage/goog4_request',
        '-F', 'x-goog-algorithm=GOOG4-RSA-SHA256', '-F', 'x-goog-signature=' + sig, '-F', 'policy=' + pol, '-F', f'file=@{f};type={ct}'], capture_output=True, text=True)
    print(f, r.stdout, r.stderr.strip())
