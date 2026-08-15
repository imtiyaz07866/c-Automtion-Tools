import json, os

raw_json = """[{"domain":".gw.conversionsapigateway.com","expirationDate":1789196681.849358,"hostOnly":false,"httpOnly":true,"name":"browser_tags","path":"/events/83179e012a501034babcf8ee7e443d9f42f3fc658663354028c31784afccbc37","sameSite":"no_restriction","secure":true,"session":false,"storeId":"0","value":"QgrEUktVn%2FodMOzaayGc%2BtdN5Q46g8F4VxfD5x%2Bspkw%3D.%7B%22fbclid%22%3A%22fb.0.1781420668302.IwZXh0bgNhZW0CMTEAYnJpZBExajVUaVdIY2didzZrUmY4d3NydGMGYXBwX2lkATAAAR4PoY2SAfsIWmT_JAoSQEmaK9J3expztf5iwkpFU0J9bC_W8sWciSmr6pokgQ_aem_B-Xd8o3GCB3Z_pZPFNPC2g%22%7D"},{"domain":".gw.conversionsapigateway.com","expirationDate":1789196681.849799,"hostOnly":false,"httpOnly":true,"name":"cee","path":"/events/83179e012a501034babcf8ee7e443d9f42f3fc658663354028c31784afccbc37","sameSite":"no_restriction","secure":true,"session":false,"storeId":"0","value":"G7OEribE5tCJsoL0LNhaTLsj4CVem%2B2zyHM7eizemtU%3D.%7B%7D"},{"domain":".capig.gatherone.cn","expirationDate":1790579385.287707,"hostOnly":false,"httpOnly":true,"name":"cee","path":"/events/6005a6b8fa443d0b7622c354b06ba520260ec8149da0a5241c0deb535dd6c65f","sameSite":"no_restriction","secure":true,"session":false,"storeId":"0","value":"EvbHeY7wyzR6Kkb6lrNzcfkqk7aoDL1uXIs1sGb9oHg%3D.%7B%22zp%22%3A%2239e5b4830d4d9c14db7368a95b65d5463ea3d09520373723430c03a5a453b5df%22%7D"},{"domain":".youtube.com","expirationDate":1810020653.958395,"hostOnly":false,"httpOnly":true,"name":"LOGIN_INFO","path":"/","sameSite":"no_restriction","secure":true,"session":false,"storeId":"0","value":"AFmmF2swRQIgYoYO3eIwYUypm5tNMiYo_gs-xl7a1DHaJAQZiyJM5rYCIQCz7zoDpIn1L3voARzIUDocpfTkZPHb8Zy1SiVMr6C1CQ:QUQ3MjNmeVRISW1XNWZfb2cyZUllS0pjaW9lR3poQlEtVEZsQkk2SDJqb2hDSVZ4UnJtdEFfVXNiSXpvU2lieGFITGczamQyeUFwOVJPS2g4WDREX3FsWWFJVVROeVBzNlFMNDR6X1o4Qm5YTlRQMktXX1JvVXh1cFliNEw1Q2hkNkZLYTdIQTR2R0pERlhDTkpzSWZZdXB2dEU2YjVFNHZn"},{"domain":".youtube.com","expirationDate":1792498296.3864,"hostOnly":false,"httpOnly":true,"name":"__Secure-BUCKET","path":"/","sameSite":"lax","secure":true,"session":false,"storeId":"0","value":"CBY"},{"domain":".youtube.com","expirationDate":1821344115.418803,"hostOnly":false,"httpOnly":false,"name":"PREF","path":"/","sameSite":"unspecified","secure":true,"session":false,"storeId":"0","value":"tz=Asia.Calcutta"}]"""

def convert(json_str):
    try:
        cookies = json.loads(json_str)
    except Exception as e:
        print("Invalid JSON:", e)
        return
    lines = ["# Netscape HTTP Cookie File", "# https://curl.haxx.se/rfc/cookie_spec.html", "# This is a generated file!  Do not edit.", ""]
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
    
    with open("c:\\Automtion Tools\\cookies.txt", "w", encoding="utf-8") as f:
        f.write(netscape_content)
    print(f"Successfully converted {len(cookies)} cookies to Netscape format in cookies.txt!")

convert(raw_json)
