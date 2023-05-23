import unittest

from webtest import TestApp

from dtos import V1ResponseBase, STATUS_OK
import flaresolverr
import utils


def _find_obj_by_key(key: str, value: str, _list: list) -> dict | None:
    for obj in _list:
        if obj[key] == value:
            return obj
    return None


def asset_cloudflare_solution(self, res, site_url, site_text):
    self.assertEqual(res.status_code, 200)

    body = V1ResponseBase(res.json)
    self.assertEqual(STATUS_OK, body.status)
    self.assertEqual("Challenge solved!", body.message)
    self.assertGreater(body.startTimestamp, 10000)
    self.assertGreaterEqual(body.endTimestamp, body.startTimestamp)
    self.assertEqual(utils.get_flaresolverr_version(), body.version)

    solution = body.solution
    self.assertIn(site_url, solution.url)
    self.assertEqual(solution.status, 200)
    self.assertIs(len(solution.headers), 0)
    self.assertIn(site_text, solution.response)
    self.assertGreater(len(solution.cookies), 0)
    self.assertIn("Chrome/", solution.userAgent)

    cf_cookie = _find_obj_by_key("name", "cf_clearance", solution.cookies)
    self.assertIsNotNone(cf_cookie, "Cloudflare cookie not found")
    self.assertGreater(len(cf_cookie["value"]), 30)


class TestFlareSolverr(unittest.TestCase):
    app = TestApp(flaresolverr.app)
    # wait until the server is ready
    app.get('/')

    def test_v1_endpoint_request_get_cloudflare(self):
        sites_get = [
            ('nowsecure', 'https://nowsecure.nl', '<title>nowSecure</title>'),
            ('0magnet', 'https://0magnet.com/search?q=2022', 'Torrent Search - ØMagnet'),
            ('1337x', 'https://1337x.unblockit.cat/cat/Movies/time/desc/1/', ''),
            ('avistaz', 'https://avistaz.to/api/v1/jackett/torrents?in=1&type=0&search=',
             '<title>Access denied</title>'),
            ('badasstorrents', 'https://badasstorrents.com/torrents/search/720p/date/desc',
             '<title>Latest Torrents - BadassTorrents</title>'),
            ('bt4g', 'https://bt4g.org/search/2022', '<title>Download 2022 Torrents - BT4G</title>'),
            ('cinemaz', 'https://cinemaz.to/api/v1/jackett/torrents?in=1&type=0&search=',
             '<title>Access denied</title>'),
            ('epublibre', 'https://epublibre.unblockit.cat/catalogo/index/0/nuevo/todos/sin/todos/--/ajax',
             '<title>epublibre - catálogo</title>'),
            ('ext', 'https://ext.to/latest/?order=age&sort=desc',
             '<title>Download Latest Torrents - EXT Torrents</title>'),
            ('extratorrent', 'https://extratorrent.st/search/?srt=added&order=desc&search=720p&new=1&x=0&y=0',
             'Page 1 - ExtraTorrent'),
            ('idope', 'https://idope.se/browse.html', '<title>Recent Torrents</title>'),
            ('limetorrents', 'https://limetorrents.unblockninja.com/latest100',
             '<title>Latest 100 torrents - LimeTorrents</title>'),
            ('privatehd', 'https://privatehd.to/api/v1/jackett/torrents?in=1&type=0&search=',
             '<title>Access denied</title>'),
            ('torrentcore', 'https://torrentcore.xyz/index', '<title>Torrent[CORE] - Torrent community.</title>'),
            ('torrentqq223', 'https://torrentqq223.com/torrent/newest.html', 'https://torrentqq223.com/ads/'),
            ('36dm', 'https://www.36dm.club/1.html', 'https://www.36dm.club/yesterday-1.html'),
            ('erai-raws', 'https://www.erai-raws.info/feed/?type=magnet', '403 Forbidden'),
            ('teamos', 'https://www.teamos.xyz/torrents/?filename=&freeleech=',
             '<title>Log in | Team OS : Your Only Destination To Custom OS !!</title>'),
            ('yts', 'https://yts.unblockninja.com/api/v2/list_movies.json?query_term=&limit=50&sort=date_added',
             '{"movie_count":')
        ]
        for site_name, site_url, site_text in sites_get:
            with self.subTest(msg=site_name):
                res = self.app.post_json('/v1', {
                    "cmd": "request.get",
                    "url": site_url
                })
                asset_cloudflare_solution(self, res, site_url, site_text)

    def test_v1_endpoint_request_post_cloudflare(self):
        sites_post = [
            ('nnmclub', 'https://nnmclub.to/forum/tracker.php', '<title>Трекер :: NNM-Club</title>',
             'prev_sd=0&prev_a=0&prev_my=0&prev_n=0&prev_shc=0&prev_shf=1&prev_sha=1&prev_shs=0&prev_shr=0&prev_sht=0&f%5B%5D=-1&o=1&s=2&tm=-1&shf=1&sha=1&ta=-1&sns=-1&sds=-1&nm=&pn=&submit=%CF%EE%E8%F1%EA')
        ]

        for site_name, site_url, site_text, post_data in sites_post:
            with self.subTest(msg=site_name):
                res = self.app.post_json('/v1', {
                    "cmd": "request.post",
                    "url": site_url,
                    "postData": post_data
                })
                asset_cloudflare_solution(self, res, site_url, site_text)


if __name__ == '__main__':
    unittest.main()
