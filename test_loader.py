import datetime
import os
import tempfile
import time
import unittest

from systemd_boot_lifeboat import Config, Lifeboat, get_default_config


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.esp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.esp.name, 'loader', 'entries'), exist_ok=True)
        super().setUp()

    def tearDown(self) -> None:
        self.esp.cleanup()
        super().tearDown()

    def test_parse_config(self):
        tests = [('', {}),
                 ('onecolbad', {}),
                 ('three cols ok', {'three': 'cols ok'}),
                 ('mykey myval', {'mykey': 'myval'}),
                 ('k v\n#commentkey v2', {'k': 'v'}),
                 ('k v\n# commentkey v2', {'k': 'v'}),
                 ('k v\nk\tv2\n k3    v3', {'k': 'v2', 'k3': 'v3'}),
                 ]
        for i, test in enumerate(tests):
            with self.subTest(test[0]):
                conf_path = self.create_entry(f'test_parse_config_{i}.conf', test[0])
                c = Config(conf_path)
                self.assertDictEqual(test[1], c)

    def test_write_config(self):
        conf_name = os.path.join(self.esp.name, 'test_write_config.conf')
        c = Config(conf_name, {'k': 'v', 'k2': 'v2'}, ignore_missing=True)
        c.write()
        with open(conf_name, 'r', encoding='utf8') as fp:
            self.assertEqual('k\tv\nk2\tv2\n', fp.read())

    def test_get_default_config(self):
        self.create_entry('arch.conf', 'k v')
        self.create_loader('missingdefault notarch')
        self.assertEqual(None, get_default_config(self.esp.name))

        self.create_loader('default arch')
        self.assertEqual({'k': 'v'}, get_default_config(self.esp.name))

    def test_create_lifeboat(self):
        efi_path = os.path.join(self.esp.name, 'EFI', 'Arch', 'linux.efi')
        os.makedirs(os.path.dirname(efi_path), exist_ok=True)
        with open(efi_path, 'w', encoding='utf8') as fp:
            fp.write("my cool efi")
        entry_path = self.create_entry('arch.conf', f'title my cool arch\nefi {efi_path}')

        now = int(time.time())
        c = Config(entry_path)

        lifeboat = Lifeboat.from_default_config(c, now)

        now_date = datetime.datetime.fromtimestamp(lifeboat.timestamp()).strftime("%b %-d %Y")

        self.assertDictEqual({'title': f'my cool arch@{now_date}',
                             'efi': Lifeboat.lifeboat_path(efi_path, now)}, lifeboat)
        pass

    def test_create_lifeboat_cleans_up_if_writing_fails(self):
        efi_path = os.path.join(self.esp.name, 'EFI', 'Arch', 'linux.efi')
        os.makedirs(os.path.dirname(efi_path), exist_ok=True)
        with open(efi_path, 'w', encoding='utf8') as fp:
            fp.write("my cool efi")
        entry_path = self.create_entry('arch.conf', f'title my cool arch\nefi {efi_path}')
        c = Config(entry_path)
        now = int(time.time())

        # create the lifeboat file so that this will error out later
        self.create_entry(f'lifeboat_{now}_arch.conf', 'already exists')
        self.assertRaises(OSError, lambda: Lifeboat.from_default_config(c, now))
        # Make sure the lifeboat efi is cleaned up
        self.assertFalse(os.path.exists(os.path.join(self.esp.name, 'EFI', 'Arch', f'lifeboat_{now}_linux.efi')))
        pass

    def test_get_existing(self):
        now = int(time.time())
        past = int(time.time()) - 101
        self.create_entry('arch.conf', 'k v')
        now_conf_path = self.create_entry(Lifeboat.lifeboat_path('arch.conf', now), 'k now')
        past_conf_path = self.create_entry(Lifeboat.lifeboat_path('arch.conf', past), 'k past')

        actual = Lifeboat.get_existing(self.esp.name)
        expected = [Lifeboat(now_conf_path), Lifeboat(past_conf_path)]
        self.assertListEqual(sorted(expected), sorted(actual))

    def test_sort_by_timestamp(self):
        now = int(time.time())
        past = int(time.time()) - 1
        past2 = int(time.time()) - 2
        expected = [self.create_entry(Lifeboat.lifeboat_path('arch.conf', x), 'k v') for x in [past2, past, now]]
        actual = [x.filepath for x in Lifeboat.get_existing(self.esp.name)]
        self.assertListEqual(expected, actual)

    def create_loader(self, contents: str) -> str:
        loader_name = os.path.join(self.esp.name, 'loader', 'loader.conf')
        with open(loader_name, 'w', encoding='utf8') as fp:
            fp.write(contents)
        return loader_name

    def create_entry(self, name: str, contents: str) -> str:
        conf_name = os.path.join(self.esp.name, 'loader', 'entries', name)
        with open(conf_name, 'w', encoding='utf8') as fp:
            fp.write(contents)
        return conf_name


if __name__ == '__main__':
    unittest.main()
