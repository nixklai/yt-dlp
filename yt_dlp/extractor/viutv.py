from .common import InfoExtractor
from ..utils import traverse_obj
from urllib.request import Request
import json
from datetime import datetime
from random import choices


class ViuTVBaseIE(InfoExtractor):
    # _GEO_COUNTRIES = ['HK']

    def _fetch_program_api(self, program_slug):
        return self._download_json('https://api.viu.tv/production/programmes/%s' % program_slug, program_slug)

    def _generate_identifier(self):
        return ''.join(choices('1234567890abcdef', k=18))


class ViuTVProgramIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/encore/(?P<id>[a-z0-9\-]+)$'
    IE_NAME = 'ViuTV:Programme'

    def _real_extract(self, url):
        program_slug = self._match_id(url)
        program_object = self._fetch_program_api(program_slug=program_slug)

        program_name = traverse_obj(program_object, ('programme', 'programmeMeta', 'seriesTitle'))
        episodes = traverse_obj(program_object, ('programme', 'episodes'))

        return {
            '_type': 'playlist',
            'id': program_slug,
            'display_id': program_slug,
            'title': program_name,
            'series_id': program_slug,
            'series': program_name,
            'entries': [{'_type': 'url', 'url': 'https://viu.tv/encore/%s/%s' % (program_slug, episode.get('slug'))} for episode in episodes]
        }


class ViuTVProductIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/(?:[\w\-/]+)#(?P<id>20[0-9]+)$'
    IE_NAME = 'ViuTV:Product'

    def _real_extract(self, url):
        product_id = self._match_id(url)
        identifier = self._generate_identifier()

        manifest_json = self._download_json('https://api.viu.now.com/p8/3/getVodURL', data=bytes(json.dumps({
            'callerReferenceNo': datetime.now().strftime('%Y%m%d%H%M%S'),
            'productId': product_id,
            'contentId': product_id,
            'contentType': 'Vod',
            'mode': 'prod',
            'PIN': 'password',
            'cookie': identifier,
            'deviceId': identifier,
            'deviceType': 'ANDROID_WEB',
            'format': 'HLS'
        }), encoding='utf-8'), video_id=product_id)

        if manifest_json.get('responseCode') != 'SUCCESS':
            self.report_warning(f'Product not found', video_id=product_id)
            return

        manifest_url = traverse_obj(manifest_json, ('asset', 0))
        print(f"{manifest_url=}")

        return {
            'id': product_id,
            'title': product_id,
            'formats': self._extract_mpd_formats(manifest_url, video_id=product_id),
        }


class ViuTVEpisodeIE(ViuTVBaseIE):
    _VALID_URL = r'^https?://(?:www\.)?viu\.tv/encore/(?P<program_id>[a-z0-9\-]+)/(?P<id>[a-z0-9\-]+)$'
    IE_NAME = 'ViuTV:Episode'

    def _real_extract(self, url):
        identifier = self._generate_identifier()
        episode_slug = self._match_id(url)
        program_slug = self._search_regex(self._VALID_URL, url, 'program_id', group='program_id')

        programme = self._fetch_program_api(program_slug=program_slug)
        episode = [episode for episode in traverse_obj(programme, ('programme', 'episodes')) if episode.get('slug') == episode_slug][0]
        product_id = episode.get('productId')
        
        print(f"{product_id=}")

        manifest_request_data = bytes(json.dumps({
            'callerReferenceNo': datetime.now().strftime('%Y%m%d%H%M%S'),
            'productId': product_id,
            'contentId': product_id,
            'contentType': 'Vod',
            'mode': 'prod',
            'PIN': 'password',
            'cookie': identifier,
            'deviceId': identifier,
            'deviceType': 'ANDROID_WEB',
            'format': 'HLS'
        }), encoding='utf-8')

        manifest_json = self._download_json('https://api.viu.now.com/p8/3/getVodURL', data=manifest_request_data, video_id=episode_slug)
        manifest_url = traverse_obj(manifest_json, ('asset', 0))
        
        print(f"{manifest_url}")

        return {
            'id': product_id,
            'display_id': episode_slug,
            'title': episode.get('episodeNameU3'),
            'propgram': traverse_obj(episode, ('programmeMeta', 'seriesTitle')),
            'series': traverse_obj(episode, ('programmeMeta', 'seriesTitle')),
            'series_id': traverse_obj(programme, ('programme', 'slug')),
            'season_number': int(traverse_obj(episode, ('programmeMeta', 'seasonNo'))),
            'episode': episode.get('episodeNameU3'),
            'episode_number': episode.get('episodeNum'),
            'formats': self._extract_mpd_formats(manifest_url, video_id=episode_slug),
        }
