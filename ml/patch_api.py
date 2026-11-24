import re
with open("api_server.py", "r", encoding="utf-8") as f:
    src = f.read()

helper = '''
def _norm_district(name: str) -> str:
    s = re.sub(r"\\s*(digital\\s*twin|twin|district)\\s*$", "", str(name or ""), flags=re.I)
    return re.sub(r"\\s+", " ", s).strip().lower()
'''

if "def _norm_district" not in src:
    src = src.replace("class SimRequest(BaseModel):", helper + "\n\nclass SimRequest(BaseModel):", 1)

src = src.replace('key = name.strip().lower()', 'key = _norm_district(name)')
src = src.replace('item["district"].lower() == key', '_norm_district(item["district"]) == key')
src = src.replace('df["district"].str.lower() == key', 'df["district"].apply(_norm_district) == key')
src = src.replace('key = req.district.strip().lower()', 'key = _norm_district(req.district)')

with open("api_server.py", "w", encoding="utf-8") as f:
    f.write(src)
print("Updated api_server.py district matching cleanly.")
