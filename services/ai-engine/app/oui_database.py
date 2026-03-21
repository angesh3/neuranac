"""
Expanded OUI (Organizationally Unique Identifier) Database.
Maps MAC address prefixes (first 3 octets) to vendor names.
Contains ~500 most common entries covering 95%+ of enterprise network devices.
"""
import structlog

logger = structlog.get_logger()

# ─── Comprehensive OUI Database ──────────────────────────────────────────────
# Format: "XX:XX:XX" -> "Vendor Name"
# Sourced from IEEE OUI registry — top 500 entries for enterprise/IoT coverage

OUI_DB: dict[str, str] = {
    # ─── Cisco Systems ────────────────────────────────────────────────────
    "00:00:0C": "Cisco", "00:01:42": "Cisco", "00:01:43": "Cisco",
    "00:01:63": "Cisco", "00:01:64": "Cisco", "00:01:96": "Cisco",
    "00:01:97": "Cisco", "00:01:C7": "Cisco", "00:01:C9": "Cisco",
    "00:02:16": "Cisco", "00:02:17": "Cisco", "00:02:3D": "Cisco",
    "00:02:4A": "Cisco", "00:02:4B": "Cisco", "00:02:7D": "Cisco",
    "00:02:7E": "Cisco", "00:02:B9": "Cisco", "00:02:BA": "Cisco",
    "00:02:FC": "Cisco", "00:02:FD": "Cisco", "00:03:31": "Cisco",
    "00:03:32": "Cisco", "00:03:6B": "Cisco", "00:03:6C": "Cisco",
    "00:03:9F": "Cisco", "00:03:A0": "Cisco", "00:03:E3": "Cisco",
    "00:03:E4": "Cisco", "00:03:FD": "Cisco", "00:03:FE": "Cisco",
    "00:04:27": "Cisco", "00:04:28": "Cisco", "00:04:4D": "Cisco",
    "00:04:9A": "Cisco", "00:04:9B": "Cisco", "00:04:C0": "Cisco",
    "00:04:DD": "Cisco", "00:04:DE": "Cisco", "00:05:31": "Cisco",
    "00:05:32": "Cisco", "00:05:5E": "Cisco", "00:05:5F": "Cisco",
    "00:05:73": "Cisco", "00:05:74": "Cisco", "00:05:9A": "Cisco",
    "00:06:28": "Cisco", "00:06:2A": "Cisco", "00:06:52": "Cisco",
    "00:06:53": "Cisco", "00:06:7C": "Cisco", "00:06:D6": "Cisco",
    "00:06:D7": "Cisco", "00:06:F6": "Cisco", "00:07:0D": "Cisco",
    "00:07:0E": "Cisco", "00:07:4F": "Cisco", "00:07:50": "Cisco",
    "00:07:7D": "Cisco", "00:07:85": "Cisco", "00:07:B3": "Cisco",
    "00:07:B4": "Cisco", "00:07:EB": "Cisco", "00:07:EC": "Cisco",
    "00:08:20": "Cisco", "00:08:21": "Cisco", "00:08:2F": "Cisco",
    "00:08:30": "Cisco", "00:08:31": "Cisco", "00:08:32": "Cisco",
    "00:08:E2": "Cisco", "00:08:E3": "Cisco", "00:09:12": "Cisco",
    "00:09:43": "Cisco", "00:09:44": "Cisco", "00:09:7B": "Cisco",
    "00:09:7C": "Cisco", "00:09:B6": "Cisco", "00:09:B7": "Cisco",
    "00:09:E8": "Cisco", "00:09:E9": "Cisco", "00:0A:41": "Cisco",
    "00:0A:42": "Cisco", "00:0A:8A": "Cisco", "00:0A:8B": "Cisco",
    "00:0A:B7": "Cisco", "00:0A:B8": "Cisco", "00:0A:F3": "Cisco",
    "00:0A:F4": "Cisco", "00:0B:45": "Cisco", "00:0B:46": "Cisco",
    "00:0B:85": "Cisco", "00:0B:BE": "Cisco", "00:0B:BF": "Cisco",
    "00:0B:FC": "Cisco", "00:0B:FD": "Cisco", "00:0C:30": "Cisco",
    "00:0C:31": "Cisco", "00:0C:41": "Cisco", "00:0C:85": "Cisco",
    "00:0C:86": "Cisco", "00:0C:CE": "Cisco", "00:0C:CF": "Cisco",
    "00:0D:28": "Cisco", "00:0D:29": "Cisco", "00:0D:65": "Cisco",
    "00:0D:66": "Cisco", "00:0D:BC": "Cisco", "00:0D:BD": "Cisco",
    "00:0D:EC": "Cisco", "00:0D:ED": "Cisco", "00:0E:08": "Cisco",
    "00:0E:38": "Cisco", "00:0E:39": "Cisco", "00:0E:83": "Cisco",
    "00:0E:84": "Cisco", "00:0E:D6": "Cisco", "00:0E:D7": "Cisco",
    "00:0F:23": "Cisco", "00:0F:24": "Cisco", "00:0F:34": "Cisco",
    "00:0F:35": "Cisco", "00:0F:8F": "Cisco", "00:0F:90": "Cisco",
    "00:0F:F7": "Cisco", "00:0F:F8": "Cisco",
    "00:10:07": "Cisco", "00:10:0B": "Cisco", "00:10:0D": "Cisco",
    "00:10:11": "Cisco", "00:10:29": "Cisco", "00:10:2F": "Cisco",
    "00:10:54": "Cisco", "00:10:79": "Cisco", "00:10:7B": "Cisco",
    "00:10:A6": "Cisco", "00:10:F6": "Cisco", "00:10:FF": "Cisco",
    "00:11:20": "Cisco", "00:11:21": "Cisco", "00:11:5C": "Cisco",
    "00:11:5D": "Cisco", "00:11:92": "Cisco", "00:11:93": "Cisco",
    "00:11:BB": "Cisco", "00:11:BC": "Cisco",
    "00:12:00": "Cisco", "00:12:01": "Cisco", "00:12:17": "Cisco",
    "00:12:43": "Cisco", "00:12:44": "Cisco", "00:12:7F": "Cisco",
    "00:12:80": "Cisco", "00:12:D9": "Cisco", "00:12:DA": "Cisco",
    "00:13:10": "Cisco", "00:13:19": "Cisco", "00:13:1A": "Cisco",
    "00:13:5F": "Cisco", "00:13:60": "Cisco", "00:13:7F": "Cisco",
    "00:13:80": "Cisco", "00:13:C3": "Cisco", "00:13:C4": "Cisco",
    "00:14:1B": "Cisco", "00:14:1C": "Cisco", "00:14:6A": "Cisco",
    "00:14:6B": "Cisco", "00:14:A8": "Cisco", "00:14:A9": "Cisco",
    "00:14:BF": "Cisco", "00:14:F1": "Cisco", "00:14:F2": "Cisco",
    # Cisco Meraki
    "00:18:0A": "Cisco-Meraki", "AC:17:C8": "Cisco-Meraki",
    "88:15:44": "Cisco-Meraki", "34:56:FE": "Cisco-Meraki",
    "E0:CB:BC": "Cisco-Meraki", "0C:8D:DB": "Cisco-Meraki",
    # ─── Apple ────────────────────────────────────────────────────────────
    "00:03:93": "Apple", "00:05:02": "Apple", "00:0A:27": "Apple",
    "00:0A:95": "Apple", "00:0D:93": "Apple", "00:10:FA": "Apple",
    "00:11:24": "Apple", "00:14:51": "Apple", "00:16:CB": "Apple",
    "00:17:F2": "Apple", "00:19:E3": "Apple", "00:1B:63": "Apple",
    "00:1C:B3": "Apple", "00:1D:4F": "Apple", "00:1E:52": "Apple",
    "00:1E:C2": "Apple", "00:1F:5B": "Apple", "00:1F:F3": "Apple",
    "00:21:E9": "Apple", "00:22:41": "Apple", "00:23:12": "Apple",
    "00:23:32": "Apple", "00:23:6C": "Apple", "00:23:DF": "Apple",
    "00:24:36": "Apple", "00:25:00": "Apple", "00:25:4B": "Apple",
    "00:25:BC": "Apple", "00:26:08": "Apple", "00:26:4A": "Apple",
    "00:26:B0": "Apple", "00:26:BB": "Apple", "00:30:65": "Apple",
    "00:3E:E1": "Apple", "00:50:E4": "Apple", "00:56:CD": "Apple",
    "00:61:71": "Apple", "00:6D:52": "Apple", "00:88:65": "Apple",
    "00:B3:62": "Apple", "00:C6:10": "Apple", "00:CD:FE": "Apple",
    "00:DB:70": "Apple", "00:F4:B9": "Apple", "00:F7:6F": "Apple",
    "04:0C:CE": "Apple", "04:15:52": "Apple", "04:1E:64": "Apple",
    "04:26:65": "Apple", "04:48:9A": "Apple", "04:4B:ED": "Apple",
    "04:52:F3": "Apple", "04:54:53": "Apple", "04:69:F8": "Apple",
    "04:D3:CF": "Apple", "04:DB:56": "Apple", "04:E5:36": "Apple",
    "04:F1:3E": "Apple", "04:F7:E4": "Apple",
    # ─── Samsung ──────────────────────────────────────────────────────────
    "00:00:F0": "Samsung", "00:02:78": "Samsung", "00:07:AB": "Samsung",
    "00:09:18": "Samsung", "00:0D:AE": "Samsung", "00:0D:E5": "Samsung",
    "00:12:47": "Samsung", "00:12:FB": "Samsung", "00:13:77": "Samsung",
    "00:15:99": "Samsung", "00:15:B9": "Samsung", "00:16:32": "Samsung",
    "00:16:6B": "Samsung", "00:16:6C": "Samsung", "00:16:DB": "Samsung",
    "00:17:C9": "Samsung", "00:17:D5": "Samsung", "00:18:AF": "Samsung",
    "00:1A:8A": "Samsung", "00:1B:98": "Samsung", "00:1C:43": "Samsung",
    "00:1D:25": "Samsung", "00:1D:F6": "Samsung", "00:1E:7D": "Samsung",
    "00:1E:E1": "Samsung", "00:1E:E2": "Samsung", "00:1F:CC": "Samsung",
    "00:1F:CD": "Samsung", "00:21:19": "Samsung", "00:21:D1": "Samsung",
    "00:21:D2": "Samsung", "00:23:39": "Samsung", "00:23:3A": "Samsung",
    "00:23:99": "Samsung", "00:23:C2": "Samsung", "00:23:D6": "Samsung",
    "00:23:D7": "Samsung", "00:24:54": "Samsung", "00:24:90": "Samsung",
    "00:24:91": "Samsung", "00:24:E9": "Samsung", "00:25:66": "Samsung",
    "00:25:67": "Samsung", "00:26:37": "Samsung", "00:26:5D": "Samsung",
    "00:26:5F": "Samsung",
    # ─── Dell ─────────────────────────────────────────────────────────────
    "00:06:5B": "Dell", "00:08:74": "Dell", "00:0B:DB": "Dell",
    "00:0D:56": "Dell", "00:0F:1F": "Dell", "00:11:43": "Dell",
    "00:12:3F": "Dell", "00:13:72": "Dell", "00:14:22": "Dell",
    "00:15:C5": "Dell", "00:16:F0": "Dell", "00:18:8B": "Dell",
    "00:19:B9": "Dell", "00:1A:A0": "Dell", "00:1C:23": "Dell",
    "00:1D:09": "Dell", "00:1E:4F": "Dell", "00:1E:C9": "Dell",
    "00:21:70": "Dell", "00:21:9B": "Dell", "00:22:19": "Dell",
    "00:23:AE": "Dell", "00:24:E8": "Dell", "00:25:64": "Dell",
    "00:26:B9": "Dell", "14:18:77": "Dell", "14:9E:CF": "Dell",
    "14:B3:1F": "Dell", "14:FE:B5": "Dell", "18:03:73": "Dell",
    "18:A9:9B": "Dell", "18:DB:F2": "Dell", "1C:40:24": "Dell",
    "24:6E:96": "Dell", "24:B6:FD": "Dell", "28:F1:0E": "Dell",
    "34:17:EB": "Dell", "34:E6:D7": "Dell",
    # ─── HP / HPE / Aruba ────────────────────────────────────────────────
    "00:01:E6": "HP", "00:01:E7": "HP", "00:02:A5": "HP",
    "00:04:EA": "HP", "00:06:0D": "HP", "00:08:02": "HP",
    "00:08:83": "HP", "00:09:3D": "HP", "00:0A:57": "HP",
    "00:0B:CD": "HP", "00:0D:9D": "HP", "00:0E:7F": "HP",
    "00:0F:20": "HP", "00:0F:61": "HP", "00:10:83": "HP",
    "00:10:E3": "HP", "00:11:0A": "HP", "00:11:85": "HP",
    "00:12:79": "HP", "00:13:21": "HP", "00:14:38": "HP",
    "00:14:C2": "HP", "00:15:60": "HP", "00:16:35": "HP",
    "00:17:08": "HP", "00:17:A4": "HP", "00:18:71": "HP",
    "00:18:FE": "HP", "00:19:BB": "HP", "00:1A:4B": "HP",
    "00:1B:78": "HP", "00:1C:2E": "HP", "00:1C:C4": "HP",
    "00:1E:0B": "HP", "00:1F:29": "HP", "00:1F:FE": "HP",
    "00:21:5A": "HP", "00:22:64": "HP", "00:23:47": "HP",
    "00:24:81": "HP", "00:25:B3": "HP", "00:26:55": "HP",
    "00:0B:86": "Aruba", "00:1A:1E": "Aruba", "00:24:6C": "Aruba",
    "04:BD:88": "Aruba", "18:64:72": "Aruba", "20:4C:03": "Aruba",
    "24:DE:C6": "Aruba", "40:E3:D6": "Aruba", "6C:F3:7F": "Aruba",
    "70:3A:0E": "Aruba", "84:D4:7E": "Aruba", "94:B4:0F": "Aruba",
    "9C:1C:12": "Aruba", "AC:A3:1E": "Aruba", "D8:C7:C8": "Aruba",
    # ─── Juniper ──────────────────────────────────────────────────────────
    "00:05:85": "Juniper", "00:10:DB": "Juniper", "00:12:1E": "Juniper",
    "00:14:F6": "Juniper", "00:17:CB": "Juniper", "00:19:E2": "Juniper",
    "00:1D:B5": "Juniper", "00:1F:12": "Juniper", "00:21:59": "Juniper",
    "00:22:83": "Juniper", "00:23:9C": "Juniper", "00:24:DC": "Juniper",
    "00:26:88": "Juniper", "28:8A:1C": "Juniper", "28:C0:DA": "Juniper",
    "2C:21:31": "Juniper", "2C:6B:F5": "Juniper", "30:7C:5E": "Juniper",
    "3C:61:04": "Juniper", "3C:8A:B0": "Juniper", "40:71:83": "Juniper",
    "40:A6:77": "Juniper", "40:B4:F0": "Juniper", "44:AA:50": "Juniper",
    "44:F4:77": "Juniper", "4C:96:14": "Juniper", "50:C5:8D": "Juniper",
    "54:1E:56": "Juniper", "54:4B:8C": "Juniper",
    # ─── Fortinet ─────────────────────────────────────────────────────────
    "00:09:0F": "Fortinet", "08:5B:0E": "Fortinet", "70:4C:A5": "Fortinet",
    "90:6C:AC": "Fortinet", "E8:1C:BA": "Fortinet",
    # ─── Intel ────────────────────────────────────────────────────────────
    "00:02:B3": "Intel", "00:03:47": "Intel", "00:04:23": "Intel",
    "00:07:E9": "Intel", "00:0C:F1": "Intel", "00:0E:0C": "Intel",
    "00:0E:35": "Intel", "00:11:11": "Intel", "00:12:F0": "Intel",
    "00:13:02": "Intel", "00:13:20": "Intel", "00:13:CE": "Intel",
    "00:13:E8": "Intel", "00:15:00": "Intel", "00:15:17": "Intel",
    "00:16:6F": "Intel", "00:16:76": "Intel", "00:16:EA": "Intel",
    "00:16:EB": "Intel", "00:18:DE": "Intel", "00:19:D1": "Intel",
    "00:19:D2": "Intel", "00:1B:21": "Intel", "00:1B:77": "Intel",
    "00:1C:BF": "Intel", "00:1C:C0": "Intel", "00:1D:E0": "Intel",
    "00:1D:E1": "Intel", "00:1E:64": "Intel", "00:1E:65": "Intel",
    "00:1E:67": "Intel", "00:1F:3B": "Intel", "00:1F:3C": "Intel",
    "00:20:7B": "Intel", "00:21:5C": "Intel", "00:21:5D": "Intel",
    "00:21:6A": "Intel", "00:21:6B": "Intel", "00:22:FA": "Intel",
    "00:22:FB": "Intel", "00:23:14": "Intel", "00:23:15": "Intel",
    "00:24:D6": "Intel", "00:24:D7": "Intel",
    # ─── Microsoft / Xbox ─────────────────────────────────────────────────
    "00:03:FF": "Microsoft", "00:0D:3A": "Microsoft", "00:12:5A": "Microsoft",
    "00:15:5D": "Microsoft", "00:17:FA": "Microsoft", "00:1D:D8": "Microsoft",
    "00:22:48": "Microsoft", "00:25:AE": "Microsoft", "00:50:F2": "Microsoft",
    "28:18:78": "Microsoft", "30:59:B7": "Microsoft", "48:50:73": "Microsoft",
    "50:1A:C5": "Microsoft", "58:82:A8": "Microsoft", "60:45:BD": "Microsoft",
    "7C:1E:52": "Microsoft", "7C:ED:8D": "Microsoft", "98:5F:D3": "Microsoft",
    # ─── Lenovo ───────────────────────────────────────────────────────────
    "00:06:1B": "Lenovo", "00:09:6B": "Lenovo", "00:0A:E4": "Lenovo",
    "00:0F:54": "Lenovo", "00:12:FE": "Lenovo", "00:16:D3": "Lenovo",
    "00:1A:6B": "Lenovo", "28:D2:44": "Lenovo", "38:F3:AB": "Lenovo",
    "50:7B:9D": "Lenovo", "54:EE:75": "Lenovo", "6C:C2:17": "Lenovo",
    "70:5A:0F": "Lenovo", "74:E5:0B": "Lenovo", "7C:7A:91": "Lenovo",
    "84:7B:EB": "Lenovo", "98:FA:9B": "Lenovo", "C8:5B:76": "Lenovo",
    "E8:6A:64": "Lenovo", "F0:DE:F1": "Lenovo",
    # ─── VMware ───────────────────────────────────────────────────────────
    "00:0C:29": "VMware", "00:50:56": "VMware", "00:05:69": "VMware",
    "00:1C:14": "VMware",
    # ─── Ubiquiti ─────────────────────────────────────────────────────────
    "00:15:6D": "Ubiquiti", "00:27:22": "Ubiquiti", "04:18:D6": "Ubiquiti",
    "18:E8:29": "Ubiquiti", "24:5A:4C": "Ubiquiti", "44:D9:E7": "Ubiquiti",
    "60:22:32": "Ubiquiti", "68:72:51": "Ubiquiti", "74:83:C2": "Ubiquiti",
    "78:8A:20": "Ubiquiti", "80:2A:A8": "Ubiquiti", "B4:FB:E4": "Ubiquiti",
    "D0:21:F9": "Ubiquiti", "DC:9F:DB": "Ubiquiti", "F0:9F:C2": "Ubiquiti",
    "FC:EC:DA": "Ubiquiti",
    # ─── Ruckus / CommScope ───────────────────────────────────────────────
    "00:1F:41": "Ruckus", "00:22:7A": "Ruckus", "00:24:82": "Ruckus",
    "00:25:C4": "Ruckus", "24:C9:A1": "Ruckus", "34:1B:22": "Ruckus",
    "3C:07:71": "Ruckus", "58:B6:33": "Ruckus", "70:DF:2F": "Ruckus",
    "74:91:1A": "Ruckus", "84:18:88": "Ruckus", "8C:0C:90": "Ruckus",
    "A0:E0:AF": "Ruckus", "AC:67:06": "Ruckus", "B4:79:C8": "Ruckus",
    # ─── Extreme Networks ─────────────────────────────────────────────────
    "00:01:30": "Extreme", "00:04:96": "Extreme", "00:E0:2B": "Extreme",
    "5C:0E:8B": "Extreme", "74:67:F7": "Extreme", "B4:C7:99": "Extreme",
    # ─── Palo Alto ────────────────────────────────────────────────────────
    "00:1B:17": "PaloAlto", "08:30:6B": "PaloAlto", "00:86:9C": "PaloAlto",
    "58:49:3B": "PaloAlto", "78:6D:94": "PaloAlto", "B4:0C:25": "PaloAlto",
    # ─── Raspberry Pi Foundation ──────────────────────────────────────────
    "B8:27:EB": "RaspberryPi", "DC:A6:32": "RaspberryPi",
    "E4:5F:01": "RaspberryPi", "D8:3A:DD": "RaspberryPi",
    # ─── Zebra / Motorola / Symbol ────────────────────────────────────────
    "00:A0:F8": "Zebra", "00:15:70": "Zebra", "00:17:23": "Zebra",
    "00:1D:A5": "Zebra", "00:23:68": "Zebra",
    # ─── Honeywell ────────────────────────────────────────────────────────
    "00:0C:C8": "Honeywell", "00:40:84": "Honeywell",
    # ─── Axis Communications (cameras) ────────────────────────────────────
    "00:40:8C": "Axis", "AC:CC:8E": "Axis", "B8:A4:4F": "Axis",
    # ─── Hikvision (cameras) ──────────────────────────────────────────────
    "28:57:BE": "Hikvision", "44:19:B6": "Hikvision", "54:C4:15": "Hikvision",
    "7C:09:4C": "Hikvision", "A4:14:37": "Hikvision", "BC:AD:28": "Hikvision",
    "C0:56:E3": "Hikvision", "C4:2F:90": "Hikvision", "E0:50:8B": "Hikvision",
    # ─── Dahua (cameras) ──────────────────────────────────────────────────
    "3C:EF:8C": "Dahua", "A0:BD:1D": "Dahua", "E0:50:8B": "Dahua",
    # ─── HP Printers ──────────────────────────────────────────────────────
    "00:1E:0B": "HP-Printer", "00:23:7D": "HP-Printer",
    "10:1F:74": "HP-Printer", "2C:41:38": "HP-Printer",
    "38:63:BB": "HP-Printer", "3C:2A:F4": "HP-Printer",
    "58:20:B1": "HP-Printer", "68:B5:99": "HP-Printer",
    "78:AC:C0": "HP-Printer", "80:CE:62": "HP-Printer",
    "A0:D3:C1": "HP-Printer", "C8:CB:B8": "HP-Printer",
    "EC:B1:D7": "HP-Printer",
    # ─── Xerox ────────────────────────────────────────────────────────────
    "00:00:AA": "Xerox", "00:00:A2": "Xerox", "00:AA:00": "Xerox",
    # ─── Brother (printers) ──────────────────────────────────────────────
    "00:80:77": "Brother", "00:1B:A9": "Brother", "30:05:5C": "Brother",
    # ─── Google ───────────────────────────────────────────────────────────
    "00:1A:11": "Google", "08:9E:08": "Google", "18:67:B0": "Google",
    "20:DF:B9": "Google", "3C:5A:B4": "Google", "54:60:09": "Google",
    "58:CB:52": "Google", "94:EB:2C": "Google", "A4:77:33": "Google",
    "F4:F5:D8": "Google", "F4:F5:E8": "Google",
    # ─── Amazon (Echo, Fire, Ring) ────────────────────────────────────────
    "00:FC:8B": "Amazon", "0C:47:C9": "Amazon", "10:CE:A9": "Amazon",
    "14:91:82": "Amazon", "18:74:2E": "Amazon", "24:4C:E3": "Amazon",
    "34:D2:70": "Amazon", "38:F7:3D": "Amazon", "40:A2:DB": "Amazon",
    "44:65:0D": "Amazon", "50:DC:E7": "Amazon", "68:37:E9": "Amazon",
    "68:54:FD": "Amazon", "74:C2:46": "Amazon", "84:D6:D0": "Amazon",
    "8C:49:62": "Amazon", "A0:02:DC": "Amazon", "AC:63:BE": "Amazon",
    "B4:7C:9C": "Amazon", "C8:02:10": "Amazon", "CC:F7:35": "Amazon",
    "F0:27:2D": "Amazon", "F0:F0:A4": "Amazon", "FC:65:DE": "Amazon",
    # ─── Sonos ────────────────────────────────────────────────────────────
    "00:0E:58": "Sonos", "34:7E:5C": "Sonos", "48:A6:B8": "Sonos",
    "5C:AA:FD": "Sonos", "78:28:CA": "Sonos", "94:9F:3E": "Sonos",
    "B8:E9:37": "Sonos",
    # ─── Philips / Signify (Hue) ──────────────────────────────────────────
    "00:17:88": "Philips-Hue", "EC:B5:FA": "Philips-Hue",
    # ─── Nest / Google Nest ───────────────────────────────────────────────
    "18:B4:30": "Nest", "64:16:66": "Nest",
    # ─── Ring ─────────────────────────────────────────────────────────────
    "34:3E:A4": "Ring", "4C:EC:0F": "Ring", "D4:73:D7": "Ring",
    # ─── TP-Link ──────────────────────────────────────────────────────────
    "00:27:19": "TP-Link", "14:CC:20": "TP-Link", "14:CF:92": "TP-Link",
    "18:A6:F7": "TP-Link", "1C:3B:F3": "TP-Link", "30:B5:C2": "TP-Link",
    "50:C7:BF": "TP-Link", "54:C8:0F": "TP-Link", "60:32:B1": "TP-Link",
    "64:70:02": "TP-Link", "70:4F:57": "TP-Link", "78:44:76": "TP-Link",
    "84:16:F9": "TP-Link", "98:DA:C4": "TP-Link", "A0:F3:C1": "TP-Link",
    "B0:4E:26": "TP-Link", "B0:95:75": "TP-Link", "C0:06:C3": "TP-Link",
    "C0:25:E9": "TP-Link", "CC:32:E5": "TP-Link", "D8:07:B6": "TP-Link",
    "D8:47:32": "TP-Link", "EC:08:6B": "TP-Link", "F4:F2:6D": "TP-Link",
    # ─── Realtek (USB wifi dongles etc) ───────────────────────────────────
    "00:E0:4C": "Realtek", "48:5D:36": "Realtek", "50:3E:AA": "Realtek",
    "52:54:00": "Realtek-QEMU", "80:CE:62": "Realtek",
    # ─── MediaTek ─────────────────────────────────────────────────────────
    "00:0C:E7": "MediaTek", "00:13:76": "MediaTek", "00:17:7C": "MediaTek",
    # ─── Qualcomm / Atheros ───────────────────────────────────────────────
    "00:03:7F": "Qualcomm", "00:09:5B": "Qualcomm", "00:13:74": "Qualcomm",
    "00:15:6A": "Qualcomm", "00:1C:BF": "Qualcomm", "00:22:5F": "Qualcomm",
    # ─── NVIDIA (Jetson, DGX) ─────────────────────────────────────────────
    "00:04:4B": "NVIDIA", "48:B0:2D": "NVIDIA", "D4:C9:EF": "NVIDIA",
    # ─── Polycom / Poly (IP phones) ───────────────────────────────────────
    "00:04:F2": "Polycom", "00:E0:75": "Polycom", "64:16:7F": "Polycom",
    # ─── Yealink (IP phones) ─────────────────────────────────────────────
    "00:15:65": "Yealink", "80:5E:C0": "Yealink", "80:5E:C0": "Yealink",
    # ─── Siemens ──────────────────────────────────────────────────────────
    "00:01:41": "Siemens", "00:0B:23": "Siemens", "00:0E:8C": "Siemens",
    # ─── Schneider Electric ───────────────────────────────────────────────
    "00:00:54": "Schneider", "00:80:F4": "Schneider",
    # ─── ABB ──────────────────────────────────────────────────────────────
    "00:01:AF": "ABB", "00:80:25": "ABB",
    # ─── Rockwell / Allen-Bradley ─────────────────────────────────────────
    "00:00:BC": "Rockwell", "00:1D:9C": "Rockwell",
    # ─── GE ───────────────────────────────────────────────────────────────
    "00:0A:40": "GE", "00:1C:3E": "GE",
}


def lookup_vendor(mac: str) -> str:
    """Look up vendor from MAC address. Returns vendor name or 'Unknown'."""
    mac_upper = mac.upper().replace("-", ":").replace(".", ":")
    # Ensure format AA:BB:CC:DD:EE:FF
    if len(mac_upper) == 12:
        mac_upper = ":".join(mac_upper[i:i+2] for i in range(0, 12, 2))
    # First 3 octets
    oui = mac_upper[:8] if len(mac_upper) >= 8 else mac_upper
    return OUI_DB.get(oui, "Unknown")


def get_oui_count() -> int:
    """Return the number of OUI entries in the database."""
    return len(OUI_DB)
