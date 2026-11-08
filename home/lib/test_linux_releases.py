import copy
import datetime as dt
import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from unittest import mock

from lib import linux_releases as releases


OLD = "a" * 40
NEW = "b" * 40
ASSET = "rex-linux-amd64.tar.gz"


def archive():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        data = b"binary"
        info = tarfile.TarInfo("rex")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return output.getvalue()


class SuperlogicalTests(unittest.TestCase):
    def setUp(self):
        self.blob = archive()
        self.entry = {"provider": "superlogical", "channel": "snapshot", "tag": OLD,
                      "version": "old", "published": "2020-01-01",
                      "asset": "rex-linux-{arch}.tar.gz", "arch": {"amd64": "amd64"}}
        self.url = f"https://blob.superlogical.com/download/rex/snapshot/{NEW}/{ASSET}"
        self.rel = {"commit": NEW, "version": "new", "createdAt": "2020-01-01T00:00:00Z",
                    "artifacts": [{"filename": ASSET, "sha256": hashlib.sha256(self.blob).hexdigest(),
                                   "downloadUrl": self.url}]}

    def fetch(self, url):
        if "/api/" in url:
            return json.dumps(self.rel).encode()
        return self.blob

    def test_keep_is_immutable_and_detects_archive_member(self):
        with mock.patch.object(releases, "download", return_value=self.blob) as download:
            releases.pin_one("rex", self.entry, True)
        download.assert_called_once_with(f"https://blob.superlogical.com/download/rex/snapshot/{OLD}/{ASSET}")
        self.assertEqual(self.entry["version"], "old")
        self.assertEqual(self.entry["members"], {"amd64": {"rex": "rex"}})
        self.assertEqual(self.entry["sha256"]["amd64"], hashlib.sha256(self.blob).hexdigest())

    def test_latest_and_explicit_current_override_cooldown(self):
        with mock.patch.object(releases, "download", side_effect=self.fetch):
            releases.pin_one("rex", self.entry, False)
            self.assertEqual(self.entry["tag"], NEW)
            self.rel["createdAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
            with self.assertRaisesRegex(SystemExit, "less than 7 days"):
                releases.pin_one("rex", self.entry, False)
            self.entry["tag"] = OLD
            releases.pin_one("rex", self.entry, False, requested_tag=NEW)
            self.assertEqual(self.entry["tag"], NEW)

    def test_explicit_existing_preserves_metadata_without_api(self):
        with mock.patch.object(releases, "download", return_value=self.blob) as download:
            releases.pin_one("rex", self.entry, False, requested_tag=OLD)
        self.assertEqual(download.call_count, 1)
        self.assertEqual((self.entry["version"], self.entry["published"]), ("old", "2020-01-01"))

    def test_unknown_commit_fails_without_mutation(self):
        before = copy.deepcopy(self.entry)
        with mock.patch.object(releases, "download", side_effect=self.fetch):
            with self.assertRaisesRegex(SystemExit, "historical metadata unavailable"):
                releases.pin_one("rex", self.entry, False, requested_tag="c" * 40)
        self.assertEqual(self.entry, before)

    def test_invalid_inputs(self):
        for channel in ("../snapshot", "unknown"):
            self.entry["channel"] = channel
            with self.assertRaisesRegex(SystemExit, "unknown Superlogical channel"):
                releases.pin_one("rex", self.entry, True)
        self.entry["channel"] = "snapshot"
        with self.assertRaisesRegex(SystemExit, "40 lowercase"):
            releases.pin_one("rex", self.entry, False, requested_tag="A" * 40)
        self.rel["commit"] = "bad"
        with mock.patch.object(releases, "download", side_effect=self.fetch):
            with self.assertRaisesRegex(SystemExit, "invalid commit"):
                releases.pin_one("rex", self.entry, False)

    def test_missing_asset_bad_checksum_and_url_fail_atomically(self):
        for field, value, message in (("filename", "missing", "expected one asset"),
                                      ("sha256", "0" * 64, "checksum mismatch"),
                                      ("downloadUrl", "https://example.com", "unexpected download URL")):
            with self.subTest(field=field):
                original = self.rel["artifacts"][0][field]
                self.rel["artifacts"][0][field] = value
                before = copy.deepcopy(self.entry)
                with mock.patch.object(releases, "download", side_effect=self.fetch):
                    with self.assertRaisesRegex(SystemExit, message):
                        releases.pin_one("rex", self.entry, False)
                self.assertEqual(self.entry, before)
                self.rel["artifacts"][0][field] = original

    def test_failure_does_not_write_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "linux.json")
            content = json.dumps({"linux": {"releases": {"rex": self.entry}}})
            with open(path, "w") as file:
                file.write(content)
            with mock.patch.object(releases, "MANIFEST", path), mock.patch.object(releases, "download", side_effect=self.fetch):
                with self.assertRaisesRegex(SystemExit, "historical metadata unavailable"):
                    releases.main(["pin", "--tag", "c" * 40, "rex"])
            with open(path) as file:
                self.assertEqual(file.read(), content)


class GithubTests(unittest.TestCase):
    def test_selection_and_tag_dispatch(self):
        old = {"tag_name": "v1", "published_at": "2020-01-01T00:00:00Z", "draft": False,
               "prerelease": False, "assets": [{"name": "tool-amd64"}]}
        new = dict(old, tag_name="v2", published_at=dt.datetime.now(dt.timezone.utc).isoformat())
        with mock.patch.object(releases, "gh_json", return_value=[new, old]):
            self.assertEqual(releases.pick_release("org/tool"), old)
        entry = {"repo": "org/tool", "asset": "tool-{arch}", "arch": {"amd64": "amd64"}, "tag": "v0"}
        with mock.patch.object(releases, "pick_release", return_value=old) as pick, mock.patch.object(releases, "download", return_value=b"binary"):
            releases.pin_one("tool", entry, False, requested_tag="v1")
        pick.assert_called_once_with("org/tool", "v1", True)
        self.assertEqual(entry["version"], "1")
        self.assertNotIn("members", entry)


if __name__ == "__main__":
    unittest.main()
