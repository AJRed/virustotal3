#!/usr/bin/env python2
import os
import sys
import json
import urllib
import urllib.request
import urllib.parse
import hashlib
import argparse

VIRUSTOTAL_FILE_URL = 'https://www.virustotal.com/vtapi/v2/file/report'
API_KEY = ''
CONFIG_FILE = 'virustotal.conf'
CONFIG_GLOBAL_PATH = '/etc/' + CONFIG_FILE
CONFIG_HOME_PATH = f"{os.getenv("HOME")}/.config/virustotal/{CONFIG_FILE}"
print(CONFIG_HOME_PATH)

TPL_SECTION = "[*] ({0}):"
TPL_MATCH = "\t_ Results: {0}/{1} {2}\n\t   SHA256: {3}\n\t   Scan Date: {4}"
TPL_SIGNATURES = "\t   Signatures:\n\t\t{0}"


def config():
    if os.path.exists(CONFIG_HOME_PATH):
        config_path = CONFIG_HOME_PATH
    elif os.path.exists(CONFIG_GLOBAL_PATH):
        config_path = CONFIG_GLOBAL_PATH
    else:
        print("[!] ERROR: no config file")
        exit(1)
    configfile = open(config_path, "r")
    content = configfile.read()
    lines = content.split('\n')
    for line in lines:
        line = line.replace(" ", "")
        line = line.split("=")
        if line[0] == "API_KEY":
            if len(line) < 2:
                print("[!] ERROR: You specified no API-Key in the config")
                exit(1)
            if len(line[1]) > 65:
                print("[!] ERROR: the API-Key is not valid")
                exit(1)
            try:
                int(line[1], 16)
            except:
                print("[!] ERROR: the API-Key is not valid")
                exit(1)
            return line[1]


def color(text, color_code):
    if sys.platform == "win32" and os.getenv("TERM") != "xterm":
        return text

    return '\x1b[%dm%s\x1b[0m' % (color_code, text)


def red(text):
    return color(text, 31)


def yellow(text):
    return color(text, 33)


class Hash(object):
    def __init__(self, path):
        self.path = path
        self.md5 = ''
        self.sha256 = ''

    def get_chunks(self):
        fd = open(self.path, 'rb')
        while True:
            chunk = fd.read(16 * 1024)
            if not chunk:
                break

            yield chunk
        fd.close()

    def calculate(self):
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()

        for chunk in self.get_chunks():
            md5.update(chunk)
            sha256.update(chunk)

        self.md5 = md5.hexdigest()
        self.sha256 = sha256.hexdigest()


class Scanner(object):
    def __init__(self, key, path):
        self.key = key
        self.path = path
        self.list = []

    def populate(self):
        paths = []

        if os.path.isfile(self.path):
            paths.append(self.path)
        else:
            for root, folders, files in os.walk(self.path):
                for file_name in files:
                    # Skip hidden files, might need an option for this.
                    if file_name.startswith('.'):
                        continue

                    file_path = os.path.join(root, file_name)
                    if os.path.exists(file_path):
                        paths.append(file_path)

        for path in paths:
            hashes = Hash(path)
            hashes.calculate()

            self.list.append({
                'path': path,
                'md5': hashes.md5,
                'sha256': hashes.sha256
            })

    def scan(self):
        hashes = []
        for entry in self.list:
            if entry['sha256'] not in hashes:
                hashes.append(entry['sha256'])

        data = urllib.parse.urlencode({
            'resource': ','.join(hashes),
            'apikey': self.key
        }).encode()

        try:
            # request = urllib2.Request(VIRUSTOTAL_FILE_URL, data)
            request = urllib.request.Request(VIRUSTOTAL_FILE_URL, data)
            # response = urllib2.urlopen(request)
            response = urllib.request.urlopen(request)
            report = json.loads(response.read())
        except Exception as e:
            print(
                red("[!] ERROR: Cannot obtain results from VirusTotal: {0}\n".format(e)))
            return

        results = []
        if type(report) is dict:
            results.append(report)
        elif type(report) is list:
            results = report

        for entry in results:
            sha256 = entry['resource']

            entry_paths = []
            for item in self.list:
                if item['sha256'] == sha256:
                    if item['path'] not in entry_paths:
                        entry_paths.append(item['path'])

            print(TPL_SECTION.format('\n     '.join(entry_paths))),

            if entry['response_code'] == 0:
                print('NOT FOUND')
            else:
                print(yellow('FOUND'))

                signatures = []
                for av, scan in entry['scans'].items():
                    if scan['result']:
                        signatures.append(scan['result'])

                if entry['positives'] > 0:
                    print(TPL_MATCH.format(
                        entry['positives'],
                        entry['total'],
                        red('DETECTED'),
                        entry['resource'],
                        entry['scan_date']
                    ))

                    if entry['positives'] > 0:
                        print(TPL_SIGNATURES.format('\n\t\t'.join(signatures)))

    def run(self):
        if not self.key:
            print(
                red("[!] ERROR: You didn't specify a valid VirusTotal API key.\n"))
            return

        if not os.path.exists(self.path):
            print(
                red("[!] ERROR: The target path {0} does not exist.\n".format(self.path)))
            return

        self.populate()
        self.scan()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'path', type=str, help='Path to the file or folder to lookup on VirusTotal')
    parser.add_argument('--key', type=str, action='store',
                        default=API_KEY, help='VirusTotal API key')

    try:
        args = parser.parse_args()
        if args.key == "":
            args.key = config()
    except IOError as e:
        parser.error(e)
        sys.exit()

    scan = Scanner(args.key, args.path)
    scan.run()
