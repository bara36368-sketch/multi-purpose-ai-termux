"""Device profiles: where to read CPU/thermal/battery data per device class."""
import os


def _read_float(path):
    try:
        with open(path, encoding="utf-8") as f:
            v = f.read().strip().split()[0]
        return float(v)
    except (OSError, ValueError):
        return None


def _read_mah(path):
    """Battery charge: read voltage + current to estimate mAh drain."""
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().strip().split()[0])
    except (OSError, ValueError):
        return None


class DeviceProfile:
    name = "generic"

    def cpu_model(self):
        return None

    def thermal_c(self):
        return None

    def charge_mah(self):
        return None

    def snapshot(self):
        return {"cpu": self.cpu_model(), "thermal_c": self.thermal_c(),
                "charge_mah": self.charge_mah()}


class HelioG85(DeviceProfile):
    """Redmi/Realme-class Helio G85 (4GB RAM phones)."""
    name = "g85"

    def cpu_model(self):
        return "MediaTek Helio G85"

    def thermal_c(self):
        for zone in range(8):
            v = _read_float(f"/sys/class/thermal/thermal_zone{zone}/temp")
            if v is not None:
                return round(v / 1000.0, 1)
        return None

    def charge_mah(self):
        cap = _read_mah("/sys/class/power_supply/battery/capacity")
        return cap


class TensorG4(DeviceProfile):
    name = "tensor-g4"

    def cpu_model(self):
        return "Google Tensor G4"

    def thermal_c(self):
        for zone in range(12):
            v = _read_float(f"/sys/class/thermal/thermal_zone{zone}/temp")
            if v is not None:
                return round(v / 1000.0, 1)
        return None

    def charge_mah(self):
        return _read_mah("/sys/class/power_supply/battery/capacity")


class Snapdragon8Elite(DeviceProfile):
    name = "sd-8elite"

    def cpu_model(self):
        return "Snapdragon 8 Elite"

    def thermal_c(self):
        for zone in range(16):
            v = _read_float(f"/sys/class/thermal/thermal_zone{zone}/temp")
            if v is not None:
                return round(v / 1000.0, 1)
        return None

    def charge_mah(self):
        return _read_mah("/sys/class/power_supply/battery/capacity")


PROFILES = {p.name: p for p in (HelioG85, TensorG4, Snapdragon8Elite)}


def get_profile(name=None):
    if name:
        return PROFILES.get(name, DeviceProfile)()
    return DeviceProfile()
