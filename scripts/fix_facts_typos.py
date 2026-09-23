#!/usr/bin/env python
"""Fix the typos a proofread found in 17 temple-facts sections (23 Sep 2026).

Evan asked for every typo on the site fixed. A full read of all 45 facts
sections found three wrong words, two British spellings and 17 dates missing
the comma after the year. Each edit is fixed in the temple's
temple-facts.html (the source of truth, so the next rebuild keeps it) and in
the live product descriptions. Dates sit inside <time> tags, so the patterns
allow for them. Every pattern must match exactly once or that temple is
skipped and reported.

    fix_facts_typos.py                      # dry run, tees and crews
    fix_facts_typos.py --apply              # tees and crews (done 23 Sep)
    fix_facts_typos.py --apply --hoodie     # after the Eden Green rollout

Hoodies wait because each rollout swap copies the old hoodie's description and
then checks the copy matches. Already-fixed text is skipped, so re-running is
safe. Afterwards run scripts/mirror_facts.py and commit artifacts/temple-facts.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shopify_client import ShopifyClient                     # noqa: E402

APPLY = "--apply" in sys.argv
PREFIXES = (["ultra-soft-oversized-temple-hoodie-"] if "--hoodie" in sys.argv
            else ["essential-heavyweight-temple-tee-", "ultra-soft-temple-sweatshirt-"])
TEMPLES = ROOT.parent.parent / "Temples"
Y=lambda year,nxt: (rf"({year}(?:</time>)?) ({re.escape(nxt)})", r"\1, \2")
W=lambda a,b: (re.escape(a), b)
EDITS={
 ("Boise","boise"):[Y("2011","for a 15-month")],
 ("Brigham City","brigham-city"):[Y("2012","and drew nearly")],
 ("Manhattan","manhattan"):[Y("2024","for a renovation the First"),Y("2002","and wrote in his journal")],
 ("Mexico City","mexico-city"):[Y("1983","and drew more than 120,000")],
 ("Oakland","oakland"):[Y("1964","and was extended")],
 ("Ogden","ogden"):[Y("1971","and drew more than 150,000"),Y("2014","and drew roughly")],
 ("Ogden (original)","ogden-original"):[Y("1971","and drew more than 150,000"),Y("2014","with a completely new exterior")],
 ("Vernal","vernal"):[Y("1907","by President Joseph F. Smith"),Y("1997","and drew about")],
 ("Washington DC","washington-dc"):[Y("1968","and the site broken"),Y("1974","and called the visit"),Y("2018","for a renovation lasting")],
 ("West Jordan*","west-jordan"):[Y("2024","brought the Church")],
 ("Billings","billings"):[Y("1999","and drew more than 68,450")],
 ("Taylorsville","taylorsville"):[Y("2020","the city council passed")],
 ("Provo City Center","provo-city-center"):[W("recovered from the fire burned through, except","recovered from the fire, burned through except")],
 ("Provo","provo"):[W("aluminum grills","aluminum grilles")],
 ("Red Cliffs","red-cliffs"):[W("great grandfather","great-grandfather")],
 ("Albuquerque","albuquerque"):[W("a colour the","a color the")],
 ("Burley","burley"):[W("The colour palette","The color palette")],
}
sc=ShopifyClient()
def fix(text,edits,label):
    for pat,rep in edits:
        n=len(re.findall(pat,text))
        if n==0 and re.sub(pat,rep,re.sub(r"\\(.)",r"\1",pat)) and _done(text,pat,rep): continue
        if n!=1: return None, f"{label}: pattern {pat[:50]!r} matched {n}x"
        text=re.sub(pat,rep,text)
    return text,None

def _done(text,pat,rep):
    """True when the fixed form is already there, so a re-run skips it."""
    if rep.startswith("\\1"):                                  # year comma
        year, nxt = re.match(r"\((\d{4})\(\?:</time>\)\?\) \((.*)\)$", pat).groups()
        return re.search(rf"{year}(?:</time>)?, {nxt}", text) is not None
    return rep in text
problems=[]; done=0
for (folder,slug),edits in EDITS.items():
    f=TEMPLES/folder/"Working files"/"temple-facts.html"
    new,err=fix(f.read_text(),edits,f"file {folder}")
    if err: problems.append(err); continue
    targets=[]
    for h in (pre + slug for pre in PREFIXES):
        p=sc.gql('{ productByHandle(handle:"%s"){ id descriptionHtml } }'%h)["productByHandle"]
        if not p: problems.append(f"no product {h}"); break
        d,err=fix(p["descriptionHtml"],edits,h)
        if err: problems.append(err); break
        targets.append((h,p["id"],d))
    else:
        if APPLY:
            if new != f.read_text():
                f.write_text(new)
            for h,pid,d in targets:
                sc.update_product(pid, descriptionHtml=d)
                back=sc.gql('{ productByHandle(handle:"%s"){ descriptionHtml } }'%h)["productByHandle"]["descriptionHtml"]
                if back!=d: problems.append(f"{h}: read-back differs")
        done+=1
        print("ok" if APPLY else "would fix", folder, len(edits), "edit(s):", ", ".join(t[0] for t in targets))
print("temples:",done,"problems:",problems)
