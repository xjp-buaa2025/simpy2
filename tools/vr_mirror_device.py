"""Inspect ADB mirror configuration; optionally enable it without reinstalling the APK."""
import argparse
import datetime
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB = Path('C:/AllUnitys/2021.3.45f2c1/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb.exe')
PACKAGE = 'com.xjp.enginefactory.vr'
REMOTE = f'/sdcard/Android/data/{PACKAGE}/files/simpy_connection.json'


def enabling_config(config):
    """Keep the working simulation URL and all unrelated device settings."""
    updated = dict(config)
    server = urllib.parse.urlsplit(updated.get('serverUrl', ''))
    if server.scheme not in ('http', 'https') or not server.hostname:
        raise ValueError('Existing serverUrl is missing/invalid; supply --server with the working PC URL.')
    mirror = urllib.parse.urlsplit(updated.get('mirrorServerUrl', ''))
    if mirror.scheme not in ('http', 'https') or not mirror.hostname:
        host = f'[{server.hostname}]' if ':' in server.hostname else server.hostname
        updated['mirrorServerUrl'] = f'{server.scheme}://{host}:8011'
    updated['vrMirrorEnabled'] = True
    updated['vrMirrorMode'] = 'auto'
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable', action='store_true')
    parser.add_argument('--serial')
    parser.add_argument('--server', help='Override simulation URL only when explicitly supplied.')
    args = parser.parse_args()
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out = ROOT / 'results/vr_mirror_device' / stamp
    out.mkdir(parents=True)

    def adb(*commands, check=True):
        result = subprocess.run([str(ADB), *commands], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result

    report = {'enabled_by_tool': False, 'device_connected': False}
    try:
        with urllib.request.urlopen('http://127.0.0.1:8011/vr-mirror/state', timeout=2) as response:
            report['pc_relay'] = json.load(response)
    except OSError as error:
        report['pc_relay_error'] = str(error)
    devices = adb('devices', '-l').stdout
    report['adb_devices'] = devices
    available = [line.split()[0] for line in devices.splitlines()[1:] if len(line.split()) > 1 and line.split()[1] == 'device']
    serial = args.serial or (available[0] if len(available) == 1 else None)
    if not serial or serial not in available:
        report['action'] = 'Connect/authorize one headset, or select it with --serial. No device configuration changed.'
    else:
        report.update(device_connected=True, serial=serial)
        def shell(*command, check=True):
            return adb('-s', serial, 'shell', *command, check=check)
        package = shell('dumpsys', 'package', PACKAGE).stdout
        report['package'] = [line.strip() for line in package.splitlines() if 'versionCode=' in line or 'versionName=' in line]
        if not report['package']:
            raise RuntimeError('Factory VR package is not installed; no configuration changed.')
        existing = shell('cat', REMOTE, check=False)
        if existing.returncode:
            # Do not replace a config that exists but could not be read.
            exists = shell('ls', REMOTE, check=False)
            if exists.returncode == 0 or not args.server:
                raise RuntimeError('Cannot read device connection config. Check permissions or supply --server when config is absent.')
            config = {}
        else:
            (out / 'simpy_connection.before.json').write_text(existing.stdout, encoding='utf-8')
            config = json.loads(existing.stdout)
        report['config_before'] = config
        if args.enable:
            if args.server:
                config = dict(config, serverUrl=args.server)
            updated = enabling_config(config)
            local = out / 'simpy_connection.enabled.json'
            local.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
            shell('mkdir', '-p', REMOTE.rsplit('/', 1)[0])
            adb('-s', serial, 'push', str(local), REMOTE)
            received = json.loads(shell('cat', REMOTE).stdout)
            if received != updated:
                raise RuntimeError('Device configuration read-back did not match.')
            report.update(enabled_by_tool=True, config_after=received)
            report['action'] = 'Restart the VR application. On PC press V, then select VR mirror. APK not reinstalled.'
        else:
            report['action'] = 'Read-only inspection. Use --enable to enable mirror, then restart the VR application.'
        logs = adb('-s', serial, 'logcat', '-d', '-t', '1000', check=False).stdout
        (out / 'unity_recent.log').write_text('\n'.join(line for line in logs.splitlines() if 'Unity' in line or 'SimPy' in line), encoding='utf-8')
    (out / 'diagnosis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f'Report: {out}')
    return 0 if report['device_connected'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
