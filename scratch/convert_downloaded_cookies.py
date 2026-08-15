import json, os

src_json_path = r"c:\Users\imd35\Downloads\www.youtube.com_cookies.json"
dest_txt_path = r"c:\Automtion Tools\cookies.txt"

with open(src_json_path, "r", encoding="utf-8") as f:
    cookies = json.load(f)

lines = [
    "# Netscape HTTP Cookie File",
    "# https://curl.haxx.se/rfc/cookie_spec.html",
    "# This is a generated file!  Do not edit.",
    ""
]

for c in cookies:
    domain = c.get("domain", "")
    flag = "TRUE" if domain.startswith(".") else "FALSE"
    path = c.get("path", "/")
    secure = "TRUE" if c.get("secure", False) else "FALSE"
    exp = str(int(c.get("expirationDate", 0)))
    name = c.get("name", "")
    value = c.get("value", "")
    if domain and name:
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{exp}\t{name}\t{value}")

netscape_content = "\n".join(lines)

with open(dest_txt_path, "w", encoding="utf-8") as f:
    f.write(netscape_content)

print(f"SUCCESSFULLY converted all {len(cookies)} YouTube authentication cookies from {src_json_path} to Netscape {dest_txt_path}!")
